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

async function passiveCdp(url) {
  const directory = process.env.MTG_PASSIVE_CDP_EVIDENCE;
  if (!directory) return null;
  const frontend = new URL(url).origin;
  const backend = new URL(process.env.MTG_BACKEND_ORIGIN || 'http://127.0.0.1:10199').origin;
  const { default: fs } = await import('node:fs');
  const { default: path } = await import('node:path');
  const { createHash, randomUUID } = await import('node:crypto');
  const owner = process.env.MTG_BROWSER_SQL_OWNER;
  const privateDirectory = location => {
    const info = fs.lstatSync(location);
    if (!info.isDirectory() || info.isSymbolicLink() || info.uid !== process.getuid()
      || (info.mode & 0o777) !== 0o700) throw new Error('Passive CDP requires a private owner directory');
  };
  if (!owner || !owner.startsWith('/tmp/') || path.resolve(owner) !== owner
    || fs.realpathSync(owner) !== owner) throw new Error('Passive CDP requires a private local owner directory');
  privateDirectory(owner);
  if ([0x0187, 0x6969, 0xff534d42, 0xfe534d42].includes(fs.statfsSync(owner).type)) {
    throw new Error('Passive CDP requires a private local owner directory');
  }
  const relative = path.relative(owner, directory);
  if (!path.isAbsolute(directory) || path.resolve(directory) !== directory || !relative
    || relative.startsWith('..') || path.isAbsolute(relative)) throw new Error('Passive CDP requires a private directory inside its owner');
  let location = owner;
  for (const part of relative.split(path.sep)) {
    location = path.join(location, part);
    if (!fs.existsSync(location)) fs.mkdirSync(location, { mode: 0o700 });
    privateDirectory(location);
    if (fs.statSync(location).dev !== fs.statSync(owner).dev) throw new Error('Passive CDP requires a private local owner directory');
  }
  const fd = fs.openSync(path.join(directory, `cdp-${process.pid}-${randomUUID()}.jsonl`),
    fs.constants.O_WRONLY | fs.constants.O_CREAT | fs.constants.O_EXCL | fs.constants.O_NOFOLLOW, 0o600);
  const errors = new Set(), requests = new Map(), projections = new Set();
  let work = Promise.resolve(), raw, binding = null, generation = 0, pageId = null, ready = false, stopped = false;
  const token = value => typeof value === 'string' && /^[a-zA-Z0-9_.-]{1,128}$/.test(value) ? value : null;
  const number = value => typeof value === 'number' && Number.isFinite(value) ? value : null;
  const hash = value => typeof value === 'string' ? createHash('sha256').update(value).digest('hex') : null;
  function writeFailure(reason) {
    if (!errors.has(reason)) {
      errors.add(reason);
      try { process.stderr.write(`PASSIVE_CDP_INCOMPLETE ${reason}\n`); } catch { /* No diagnostic may replace the caller's error. */ }
    }
  }
  function record(event, fields = {}) {
    try {
      const bytes = Buffer.from(JSON.stringify({ event, page_id: pageId, ...fields }) + '\n');
      if (fs.writeSync(fd, bytes) !== bytes.length) writeFailure('write');
    } catch { writeFailure('write'); }
  }
  function incomplete(reason) { errors.add(reason); record('incomplete', { reason }); }
  const status = () => ({ complete: ready && !errors.size && !requests.size && !projections.size,
    errors: [...errors], outstanding: requests.size, pending_projections: projections.size });
  async function snapshot(reason) {
    if (reason === 'reload') { generation++; binding = null; }
    const epoch = generation;
    try {
      const result = await raw('Runtime.evaluate', { expression: `(() => ({origin: location.origin, activeMatch: localStorage.getItem('mtg.activeMatch'), alert: document.querySelector('[role="alert"]')?.textContent ?? null}))()`, returnByValue: true });
      const value = result.result?.value;
      if (result.exceptionDetails || value?.origin !== frontend || epoch !== generation) throw new Error('Unbound snapshot');
      binding = token(value.activeMatch);
      record('snapshot', { reason, origin: frontend, match_id: binding, alert_sha256: hash(value.alert) });
    } catch { incomplete('snapshot'); }
  }
  function route(value) {
    try {
      const parsed = new URL(value);
      if (parsed.username || parsed.password) return null;
      const prefix = parsed.origin === backend ? '' : parsed.origin === frontend ? '/api' : null;
      if (prefix === null) return null;
      const match = parsed.pathname.match(new RegExp(`^${prefix}/matches(?:/([a-zA-Z0-9_-]{1,128})(/legal-moves)?)?$`));
      return match ? { kind: match[2] ? 'legal-moves' : match[1] ? 'match' : 'summary', id: match[1] ?? null } : null;
    } catch { return null; }
  }
  const pendingKinds = new Set('effect_cast suspend_cast scry scry_top_order surveil surveil_top_order hand_top_order proliferate ward_payment ward_cost_cards counter_payment optional_search optional_reveal graveyard_return discard each_player_discard cleanup_discard mulligan_bottom opening_hand opening_hand_exile sacrifice draw land_entry land_from_hand saga_entry entry_mode note_creature_type attacking_token_target topdeck_reveal_creature topdeck_put topdeck_bottom_order look_top_choose look_top_select_hand search_library combat_damage copy_target spree_target_change legend_keeper exchange_energy_payment loyalty_cards loyalty_attachment'.split(' '));
  const moveTypes = new Set('pass_priority play_land cast_spell activate_ability choose_mechanic choose_legend choose_trigger_order choose_replacement declare_attackers declare_blockers assign_combat_damage mulligan keep_hand bottom_mulligan sideboard concede'.split(' '));
  function project(value, request) {
    if (request.info.route === 'summary') {
      if (!Array.isArray(value)) throw new Error('Summary shape');
      return { own_records: value.filter(row => row?.id === request.binding).map(row => ({ id: request.binding, revision: number(row.revision) })) };
    }
    if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Response shape');
    if (request.info.route === 'legal-moves') {
      if (!Array.isArray(value.moves)) throw new Error('Moves shape');
      const kinds = {};
      for (const move of value.moves) {
        const kind = moveTypes.has(move?.type) ? move.type : 'other';
        kinds[kind] = (kinds[kind] ?? 0) + 1;
      }
      return { revision: number(value.revision), player_id: [1, 2].includes(value.player_id) ? value.player_id : null, move_count: value.moves.length, move_types: kinds };
    }
    if (value.id !== request.binding) throw new Error('Body binding');
    const pending = value.pending_mechanic_choice;
    return { id: request.binding, revision: number(value.revision),
      mode: ['human_vs_human', 'player_vs_ai', 'ai_vs_ai'].includes(value.mode) ? value.mode : null,
      controllers: Object.fromEntries(['1', '2'].map(seat => [seat, ['human', 'ai'].includes(value.controllers?.[seat]) ? value.controllers[seat] : null])),
      priority_player: [1, 2].includes(value.priority_player) ? value.priority_player : null,
      pending: pending ? { kind: pendingKinds.has(pending.kind) ? pending.kind : 'other',
        player_id: [1, 2].includes(pending.player_id) ? pending.player_id : null,
        option_count: Array.isArray(pending.options) ? pending.options.length : null, label_sha256: hash(pending.label) } : null };
  }
  async function handle(method, params, bound, epoch) {
    if (method === 'Runtime.exceptionThrown') {
      const details = params.exceptionDetails ?? {};
      record('runtime-error', { timestamp: number(params.timestamp), exception_id: number(details.exceptionId),
        class_name: ['Error', 'TypeError', 'ReferenceError', 'RangeError', 'SyntaxError'].includes(details.exception?.className) ? details.exception.className : 'other',
        line: number(details.lineNumber), column: number(details.columnNumber), text_sha256: hash(details.text), description_sha256: hash(details.exception?.description) });
      return;
    }
    const id = token(params.requestId);
    if (!id) { incomplete('request-id'); return; }
    if (method === 'Network.requestWillBeSent') {
      const previous = requests.get(id);
      requests.delete(id);
      if (previous) {
        const status = number(params.redirectResponse?.status);
        if (!Number.isInteger(status) || status < 100 || status > 599) incomplete('redirect-response-missing');
        else record('redirect', { ...previous.info, timestamp: number(params.timestamp), status });
      }
      const selected = params.request?.method === 'GET' ? route(params.request.url) : null;
      if (!selected) {
        if (previous) incomplete('redirect-scope');
        return;
      }
      if (!bound && epoch === generation) { await snapshot('request'); bound = binding; }
      if (selected.id && !bound) { incomplete('binding-missing'); return; }
      if (selected.id && selected.id !== bound && epoch === generation) { await snapshot('route'); bound = binding; }
      if (selected.id && selected.id !== bound) {
        if (previous) incomplete('redirect-scope');
        return;
      }
      const info = { request_id: id, route: selected.kind, match_id: bound,
        frame_id: token(params.frameId), loader_id: token(params.loaderId), method: 'GET' };
      requests.set(id, { info, binding: bound, status: null });
      record('request', { ...info, timestamp: number(params.timestamp) });
      return;
    }
    const request = requests.get(id);
    if (!request) return;
    if (method === 'Network.responseReceived') {
      request.status = number(params.response?.status);
      record('response', { ...request.info, timestamp: number(params.timestamp), status: request.status });
    } else if (method === 'Network.loadingFailed') {
      requests.delete(id);
      const cors = params.corsErrorStatus?.corsError;
      const knownCors = ['DisallowedByMode', 'InvalidResponse', 'MissingAllowOriginHeader', 'MultipleAllowOriginValues', 'InvalidAllowOriginValue', 'AllowOriginMismatch', 'InvalidAllowCredentials', 'CorsDisabledScheme', 'PreflightInvalidStatus', 'PreflightDisallowedRedirect', 'PreflightMissingAllowOriginHeader', 'PreflightMultipleAllowOriginValues', 'PreflightInvalidAllowOriginValue', 'PreflightAllowOriginMismatch', 'PreflightInvalidAllowCredentials', 'PreflightMissingAllowExternal', 'PreflightInvalidAllowExternal', 'InvalidAllowMethodsPreflightResponse', 'InvalidAllowHeadersPreflightResponse', 'MethodDisallowedByPreflightResponse', 'HeaderDisallowedByPreflightResponse', 'RedirectContainsCredentials', 'InsecurePrivateNetwork', 'InvalidPrivateNetworkAccess', 'UnexpectedPrivateNetworkAccess', 'NoCorsRedirectModeNotFollow'];
      record('failed', { ...request.info, timestamp: number(params.timestamp), canceled: params.canceled === true,
        cors_error: knownCors.includes(cors) ? cors : cors ? 'other' : null, cors_sha256: hash(cors), error_sha256: hash(params.errorText) });
    } else if (method === 'Network.loadingFinished') {
      requests.delete(id);
      record('finished', { ...request.info, timestamp: number(params.timestamp) });
      if (request.status === null) incomplete('response-missing');
      if (request.status >= 200 && request.status < 300) {
        const task = (async () => {
          try {
            const result = await raw('Network.getResponseBody', { requestId: id });
            if (typeof result?.body !== 'string' || result.body.length > 2 * 1024 * 1024) throw new Error('Body bound');
            const text = result.base64Encoded ? Buffer.from(result.body, 'base64').toString('utf8') : result.body;
            record('projection', { ...request.info, metadata: project(JSON.parse(text), request) });
          } catch { incomplete('body-projection'); }
        })();
        projections.add(task);
        void task.finally(() => projections.delete(task));
      }
    }
  }
  record('session', { blank_bootstrap: true, intended_origin: frontend });
  return {
    async start(command, id) {
      raw = command; pageId = token(id);
      for (const method of ['Network.enable', 'Runtime.enable']) {
        try { await raw(method); } catch { incomplete(method); }
      }
      ready = true;
    },
    event(message) {
      if (stopped || !['Network.requestWillBeSent', 'Network.responseReceived', 'Network.loadingFinished', 'Network.loadingFailed', 'Runtime.exceptionThrown'].includes(message.method)) return;
      const bound = binding, epoch = generation;
      work = work.then(() => handle(message.method, message.params ?? {}, bound, epoch)).catch(() => incomplete('observer'));
    },
    snapshot, status,
    transportLost(reason) { if (!stopped) incomplete(reason); },
    async close() {
      if (stopped) return;
      stopped = true;
      await work;
      await Promise.allSettled([...projections]);
      record('closed', status());
      try { fs.closeSync(fd); } catch { writeFailure('close'); }
    },
  };
}

export async function openBrowser(url) {
  const origin = process.env.MTG_BROWSER_ORIGIN || 'http://127.0.0.1:19222';
  if (process.env.MTG_FRONTEND_ORIGIN) url = url.replace('http://127.0.0.1:15173', process.env.MTG_FRONTEND_ORIGIN);
  const passive = process.env.MTG_PASSIVE_CDP_EVIDENCE ? await passiveCdp(url) : null;
  try {
  const page = await (await fetch(`${origin}/json/new?${passive ? 'about:blank' : url}`, { method: 'PUT', signal: AbortSignal.timeout(15000) })).json();
  const socket = new WebSocket(page.webSocketDebuggerUrl);
  if (passive) {
    socket.addEventListener('close', () => passive.transportLost('transport-close'));
    socket.addEventListener('error', () => passive.transportLost('transport-error'));
  }
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
    passive?.event(message);
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
    if (passive) await passive.snapshot('reload');
    const previousOrigin = await evaluate('performance.timeOrigin');
    await rawCommand('Page.reload', params);
    await waitFor(`performance.timeOrigin !== ${previousOrigin} && document.readyState !== 'loading'`, 30000);
  }
  if (passive) {
    await passive.start(rawCommand, page.id);
    await rawCommand('Page.navigate', { url });
    await passive.snapshot('navigation');
  }
  await waitFor(`location.origin === ${JSON.stringify(new URL(url).origin)} && document.readyState !== 'loading'`, 30000);
  return {command, evaluate, waitFor, click, reload, onIntercept: handler => { intercept = handler; }, ...(passive ? { passiveCdp: passive.status } : {}), async close() { if (passive) await passive.close(); socket.close(); await fetch(`${origin}/json/close/${page.id}`, { signal: AbortSignal.timeout(15000) }); }};
  } catch (error) { if (passive) await passive.close(); throw error; }
}
