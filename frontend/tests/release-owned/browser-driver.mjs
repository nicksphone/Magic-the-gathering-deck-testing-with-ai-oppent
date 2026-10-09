import {createCDPTrace} from './cdp-diagnostic-trace.mjs';

export async function waitForApiState(url, predicate, timeoutMs = 15000) {
  const deadline = Date.now() + timeoutMs;
  let state;
  while (Date.now() < deadline) {
    let response;
    try {
      response = await fetch(url, { signal: AbortSignal.timeout(Math.max(1, Math.min(5000, deadline - Date.now()))) });
    } catch (error) {
      // Only retry read timeouts, within the original overall deadline.
      if (error.name === 'TimeoutError' && Date.now() < deadline) continue;
      throw new Error(`State read failed; last state: ${JSON.stringify({ revision: state?.revision, priority: state?.priority_player, stack: state?.stack?.length })}`, { cause: error });
    }
    if (!response.ok) throw new Error(`State request failed: ${response.status}`);
    state = await response.json();
    if (predicate(state)) return state;
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error(`API state condition timed out: ${JSON.stringify({ priority: state?.priority_player, stack: state?.stack, step: state?.step })}`);
}

function navigationChanged(error) {
  return /Inspected target navigated or closed|Execution context was destroyed|Cannot find context with specified id/
    .test(String(error.cause?.message ?? error.message));
}

export async function initializeOwnedIframeSession(send, sessionId, patterns, waitingForDebugger = true) {
  await send('Network.enable', {}, sessionId);
  await send('Page.enable', {}, sessionId);
  await send('Page.setLifecycleEventsEnabled', {enabled: true}, sessionId);
  await send('Fetch.enable', {patterns}, sessionId);
  if (waitingForDebugger) await send('Runtime.runIfWaitingForDebugger', {}, sessionId);
}

export async function openBrowser(url) {
  const origin = process.env.MTG_BROWSER_ORIGIN || 'http://127.0.0.1:19222';
  if (process.env.MTG_FRONTEND_ORIGIN) url = url.replace('http://127.0.0.1:15173', process.env.MTG_FRONTEND_ORIGIN);
  const page = await (await fetch(`${origin}/json/new?${url}`, { method: 'PUT', signal: AbortSignal.timeout(15000) })).json();
  const socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('Chromium WebSocket connection timed out')), 15000);
    socket.onopen = () => { clearTimeout(timer); resolve(); };
    socket.onerror = () => { clearTimeout(timer); reject(new Error('Chromium WebSocket connection failed')); };
  });
  let sequence = 0;
  const pending = new Map();
  const consumptive = new Set();
  const iframeInitializations = new Set();
  let iframePatterns, iframeFailure;
  const iframeSessions = new Set();
  let intercept;
  const trace = createCDPTrace({directory: process.env.MTG_CDP_DIAGNOSTIC_DIR, targetId: page.id});
  assertCDPTraceInterface(trace);
  socket.onmessage = ({ data }) => {
    const message = JSON.parse(data);
    try { trace.received(message); } catch (error) {
      iframeFailure ??= error;
      for (const [id, waiter] of pending) { pending.delete(id); waiter.reject(error); }
      return;
    }
    if (message.method === 'Target.attachedToTarget') {
      const {sessionId, targetInfo} = message.params;
      if (!iframePatterns || targetInfo.type !== 'iframe' || typeof message.params.waitingForDebugger !== 'boolean' || iframeSessions.size >= 16) {
        iframeFailure ??= new Error('Unexpected or unbounded owned iframe attachment');
        return;
      }
      iframeSessions.add(sessionId);
      const initialization = initializeOwnedIframeSession(rawCommand, sessionId, iframePatterns, message.params.waitingForDebugger);
      iframeInitializations.add(initialization);
      initialization.then(() => iframeInitializations.delete(initialization), error => {
        iframeInitializations.delete(initialization); iframeFailure ??= error;
      });
      return;
    }
    if (message.method === 'Target.detachedFromTarget') iframeSessions.delete(message.params.sessionId);
    if (message.method === 'Fetch.requestPaused') { void intercept?.({...message.params, sessionId: message.sessionId}); return; }
    const waiter = pending.get(message.id);
    if (!waiter) return;
    pending.delete(message.id);
    message.error ? waiter.reject(new Error(JSON.stringify(message.error))) : waiter.resolve(message.result);
  };
  function rawCommand(method, params = {}, sessionId) {
    const promise = new Promise((resolve, reject) => {
      const id = ++sequence;
      trace.sent(id, method, params, sessionId);
      const timer = setTimeout(() => { trace.timeout(id); pending.delete(id); reject(new Error(`Chromium command timed out: ${method}`)); }, 15000);
      pending.set(id, { resolve: result => { clearTimeout(timer); resolve(result); }, reject: error => { clearTimeout(timer); reject(error); } });
      socket.send(JSON.stringify({ id, method, params, ...(sessionId ? {sessionId} : {}) }));
    });
    if (/^Fetch\.(continueRequest|continueResponse|failRequest|fulfillRequest)$/.test(method)) {
      consumptive.add(promise);
      promise.then(() => consumptive.delete(promise), () => consumptive.delete(promise));
    }
    return promise;
  }
  function assertInterceptionHealthy() { if (iframeFailure) throw iframeFailure; }
  function command(method, params = {}, sessionId) {
    assertInterceptionHealthy();
    return method === 'Page.reload' && !sessionId ? reload(params) : rawCommand(method, params, sessionId);
  }
  async function enableOwnedIframeInterception(patterns) {
    assertInterceptionHealthy();
    iframePatterns = structuredClone(patterns);
    await command('Target.setAutoAttach', {autoAttach: true, waitForDebuggerOnStart: true,
      flatten: true, filter: [{type: 'iframe', exclude: false}, {exclude: true}]});
  }
  async function waitForInterceptions(minimumOwnedIframeSessions = 0) {
    assertInterceptionHealthy();
    const end = Date.now() + 5000;
    while (iframeSessions.size < minimumOwnedIframeSessions) {
      assertInterceptionHealthy();
      if (Date.now() >= end) throw new Error('Owned iframe session did not attach before its action');
      await new Promise(resolve => setTimeout(resolve, 10));
    }
    await drainConsumptiveCommands(iframeInitializations);
    await drainConsumptiveCommands(consumptive);
    assertInterceptionHealthy();
  }
  async function evaluate(expression) {
    const response = await command('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })
      .catch(error => { throw new Error(`Browser evaluation failed: ${expression}`, { cause: error }); });
    if (response.exceptionDetails) throw new Error(JSON.stringify(response.exceptionDetails));
    return response.result.value;
  }
  async function waitFor(expression, timeoutMs = 15000) {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      // Await before coercion: an unresolved Promise is truthy, not readiness.
      try {
        if (await evaluate(`(async () => Boolean(document.body && await (${expression})))()`)) return;
      } catch (error) {
        // Readiness can be polled between the old and new navigation contexts.
        if (!navigationChanged(error)) throw error;
      }
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    let body = 'Navigation context unavailable';
    try { body = await evaluate('document.body?.innerText'); }
    catch (error) { if (!navigationChanged(error)) throw error; }
    throw new Error(`Browser condition timed out: ${expression}\n${body}`);
  }
  async function click(prefix) {
    await waitFor(`[...document.querySelectorAll('button')].some(b => b.textContent.trim().startsWith(${JSON.stringify(prefix)}) && !b.matches(':disabled'))`);
    await evaluate(`(() => { const button = [...document.querySelectorAll('button')].find(b => b.textContent.trim().startsWith(${JSON.stringify(prefix)}) && !b.matches(':disabled')); if (!button) throw new Error('Missing/enabled button: ' + ${JSON.stringify(prefix)}); button.click(); })()`);
  }
  async function reload(params = {}) {
    const previousOrigin = await evaluate('performance.timeOrigin');
    await drainConsumptiveCommands(consumptive);
    trace.checkpoint('before-reload');
    await rawCommand('Page.getFrameTree');
    await rawCommand('Page.reload', params);
    trace.checkpoint('reload-acknowledged');
    await waitFor(`performance.timeOrigin !== ${previousOrigin} && document.readyState !== 'loading'`, 30000);
  }
  await command('Network.enable');
  await command('Page.enable');
  await command('Page.setLifecycleEventsEnabled', {enabled: true});
  await command('Page.getFrameTree');
  await waitFor(`location.origin === ${JSON.stringify(new URL(url).origin)} && document.readyState !== 'loading'`, 30000);
  return {command, evaluate, waitFor, click, reload, enableOwnedIframeInterception, assertInterceptionHealthy,
    waitForInterceptions, onIntercept: handler => { intercept = handler; }, async close() { if (trace.hasProtocolError()) { trace.checkpoint('protocol-error-drain-begin'); await new Promise(resolve => setTimeout(resolve, 750)); trace.checkpoint('protocol-error-drain-end'); } trace.closed(); socket.close(); await fetch(`${origin}/json/close/${page.id}`, { signal: AbortSignal.timeout(15000) }); }};
}

export async function drainConsumptiveCommands(consumptive, timeoutMs = 5000) {
  const deadline = Date.now() + timeoutMs;
  while (consumptive.size) {
    const remaining = deadline - Date.now();
    if (remaining <= 0) throw new Error('Consumptive CDP commands did not acknowledge before navigation');
    let timer;
    try {
      await Promise.race([
        Promise.all([...consumptive]),
        new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('Consumptive CDP commands did not acknowledge before navigation')), remaining); }),
      ]);
    } finally { clearTimeout(timer); }
  }
}

export function assertCDPTraceInterface(trace) {
  for (const method of ['sent', 'received', 'timeout', 'checkpoint', 'hasProtocolError', 'closed']) {
    if (typeof trace[method] !== 'function') throw new TypeError(`CDP trace interface missing ${method}`);
  }
}

export async function closeBrowsersPreservingError(primaryError, ...browsers) {
  const cleanupErrors = [];
  for (const browser of browsers.filter(Boolean)) {
    try { await browser.close(); } catch (error) { cleanupErrors.push(error); }
  }
  if (!cleanupErrors.length) return;
  if (primaryError) throw new AggregateError([primaryError, ...cleanupErrors],
    `Browser body failed: ${primaryError.stack ?? primaryError}; cleanup also failed`, {cause: primaryError});
  if (cleanupErrors.length === 1) throw cleanupErrors[0];
  throw new AggregateError(cleanupErrors, 'Multiple browser cleanup failures');
}
