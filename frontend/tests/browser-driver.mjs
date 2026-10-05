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
  let intercept;
  socket.onmessage = ({ data }) => {
    const message = JSON.parse(data);
    if (message.method === 'Fetch.requestPaused') { void intercept?.(message.params); return; }
    const waiter = pending.get(message.id);
    if (!waiter) return;
    pending.delete(message.id);
    message.error ? waiter.reject(new Error(JSON.stringify(message.error))) : waiter.resolve(message.result);
  };
  function rawCommand(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = ++sequence;
      const timer = setTimeout(() => { pending.delete(id); reject(new Error(`Chromium command timed out: ${method}`)); }, 15000);
      pending.set(id, { resolve: result => { clearTimeout(timer); resolve(result); }, reject: error => { clearTimeout(timer); reject(error); } });
      socket.send(JSON.stringify({ id, method, params }));
    });
  }
  function command(method, params = {}) {
    return method === 'Page.reload' ? reload(params) : rawCommand(method, params);
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
    await rawCommand('Page.reload', params);
    await waitFor(`performance.timeOrigin !== ${previousOrigin} && document.readyState !== 'loading'`, 30000);
  }
  await waitFor(`location.origin === ${JSON.stringify(new URL(url).origin)} && document.readyState !== 'loading'`, 30000);
  return {command, evaluate, waitFor, click, reload, onIntercept: handler => { intercept = handler; }, async close() { socket.close(); await fetch(`${origin}/json/close/${page.id}`, { signal: AbortSignal.timeout(15000) }); }};
}
