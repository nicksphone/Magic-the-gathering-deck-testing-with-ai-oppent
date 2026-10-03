export async function waitForApiState(url, predicate, timeoutMs = 15000) {
  const deadline = Date.now() + timeoutMs;
  let state;
  while (Date.now() < deadline) {
    const response = await fetch(url, { signal: AbortSignal.timeout(Math.min(5000, deadline - Date.now())) })
      .catch(error => { throw new Error(`State read failed; last state: ${JSON.stringify({ revision: state?.revision, priority: state?.priority_player, stack: state?.stack?.length })}`, { cause: error }); });
    if (!response.ok) throw new Error(`State request failed: ${response.status}`);
    state = await response.json();
    if (predicate(state)) return state;
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error(`API state condition timed out: ${JSON.stringify({ priority: state?.priority_player, stack: state?.stack, step: state?.step })}`);
}

export async function openBrowser(url) {
  const origin = 'http://127.0.0.1:19222';
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
  function command(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = ++sequence;
      const timer = setTimeout(() => { pending.delete(id); reject(new Error(`Chromium command timed out: ${method}`)); }, 15000);
      pending.set(id, { resolve: result => { clearTimeout(timer); resolve(result); }, reject: error => { clearTimeout(timer); reject(error); } });
      socket.send(JSON.stringify({ id, method, params }));
    });
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
      if (await evaluate(`document.body && (${expression})`)) return;
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    throw new Error(`Browser condition timed out: ${expression}\n${await evaluate('document.body?.innerText')}`);
  }
  async function click(prefix) {
    await waitFor(`[...document.querySelectorAll('button')].some(b => b.textContent.trim().startsWith(${JSON.stringify(prefix)}) && !b.matches(':disabled'))`);
    await evaluate(`(() => { const button = [...document.querySelectorAll('button')].find(b => b.textContent.trim().startsWith(${JSON.stringify(prefix)}) && !b.matches(':disabled')); if (!button) throw new Error('Missing/enabled button: ' + ${JSON.stringify(prefix)}); button.click(); })()`);
  }
  async function reload() {
    const previousOrigin = await evaluate('performance.timeOrigin');
    await command('Page.reload');
    await waitFor(`performance.timeOrigin !== ${previousOrigin} && document.readyState !== 'loading'`, 30000);
  }
  await waitFor(`location.origin === ${JSON.stringify(new URL(url).origin)} && document.readyState !== 'loading'`, 30000);
  return {command, evaluate, waitFor, click, reload, onIntercept: handler => { intercept = handler; }, async close() { socket.close(); await fetch(`${origin}/json/close/${page.id}`, { signal: AbortSignal.timeout(15000) }); }};
}
