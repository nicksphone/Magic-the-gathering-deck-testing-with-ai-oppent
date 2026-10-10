import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { openBrowser } from './browser-driver.mjs';

const intended = 'http://127.0.0.1:15173/?fixture=original';
const api = 'http://127.0.0.1:10199';
const secret = 'PRIVATE_CARD_HEADER_BODY_SENTINEL';
const metadata = { origin: 'http://127.0.0.1:15173', activeMatch: 'own-match', alert: null };

function harness(t, options = {}) {
  const owner = fs.mkdtempSync(path.join(os.tmpdir(), 'passive-cdp-pure-'));
  fs.chmodSync(owner, 0o700);
  const directory = path.join(owner, 'private');
  const keys = ['MTG_PASSIVE_CDP_EVIDENCE', 'MTG_BROWSER_SQL_OWNER', 'MTG_FRONTEND_ORIGIN', 'MTG_BACKEND_ORIGIN'];
  const before = Object.fromEntries(keys.map(key => [key, process.env[key]]));
  const oldFetch = globalThis.fetch, oldSocket = globalThis.WebSocket;
  const state = { commands: [], fetches: [], snapshot: { ...metadata }, bodies: {}, errors: {}, socket: null,
    hold: new Set(), heldReplies: [] };
  process.env.MTG_BROWSER_SQL_OWNER = owner;
  process.env.MTG_BACKEND_ORIGIN = api;
  delete process.env.MTG_FRONTEND_ORIGIN;
  if (options.enabled === false) delete process.env.MTG_PASSIVE_CDP_EVIDENCE;
  else process.env.MTG_PASSIVE_CDP_EVIDENCE = directory;
  globalThis.fetch = async (url, params) => {
    state.fetches.push({ url, method: params.method });
    if (state.fetchFailure) throw state.fetchFailure;
    assert.match(url, /^http:\/\/127\.0\.0\.1:19222\/json\/(new\?|close\/)/, 'No extra HTTP API reads');
    return { json: async () => ({ id: 'owned-page', webSocketDebuggerUrl: 'ws://owned-page' }) };
  };
  globalThis.WebSocket = class {
    constructor() { this.listeners = {}; state.socket = this; queueMicrotask(() => this.onopen()); }
    addEventListener(type, listener) { (this.listeners[type] ??= []).push(listener); }
    emitTransport(type) {
      const event = { type, reason: secret, message: secret };
      for (const listener of this.listeners[type] ?? []) listener(event);
      this['on' + type]?.(event);
    }
    emit(method, params) { this.onmessage({ data: JSON.stringify({ method, params }) }); }
    send(raw) {
      const { id, method, params } = JSON.parse(raw);
      state.commands.push({ method, params });
      let result = {};
      if (method === 'Runtime.evaluate') {
        result = { result: { value: params.expression.includes('mtg.activeMatch') ? state.snapshot
          : params.expression === 'performance.timeOrigin' ? 1 : true } };
      } else if (method === 'Network.getResponseBody') result = state.bodies[params.requestId];
      if (method === 'Page.navigate') options.onNavigate?.(this);
      const reply = state.errors[method] ? { id, error: state.errors[method] } : { id, result };
      if (state.hold.has(method)) state.heldReplies.push(reply);
      else queueMicrotask(() => this.onmessage({ data: JSON.stringify(reply) }));
    }
    close() { state.socketClosed = true; this.emitTransport('close'); }
  };
  t.after(() => {
    globalThis.fetch = oldFetch; globalThis.WebSocket = oldSocket;
    for (const key of keys) before[key] === undefined ? delete process.env[key] : process.env[key] = before[key];
    fs.rmSync(owner, { recursive: true });
  });
  function events() {
    assert.ok(fs.existsSync(directory), 'Opt-in creates private evidence');
    const files = fs.readdirSync(directory);
    assert.equal(files.length, 1);
    const file = path.join(directory, files[0]);
    assert.equal(fs.statSync(directory).mode & 0o777, 0o700);
    assert.equal(fs.statSync(file).mode & 0o777, 0o600);
    return fs.readFileSync(file, 'utf8').trim().split('\n').map(line => JSON.parse(line));
  }
  function request(id, route = '/matches/own-match/legal-moves', extra = {}) {
    state.socket.emit('Network.requestWillBeSent', { requestId: id, frameId: 'frame-1', loaderId: 'loader-1',
      timestamp: 10, request: { url: api + route, method: 'GET', headers: { Authorization: secret }, postData: secret }, ...extra });
  }
  function response(id, status = 200) {
    state.socket.emit('Network.responseReceived', { requestId: id, timestamp: 11,
      response: { status, headers: { 'Set-Cookie': secret } } });
  }
  function finish(id, body) {
    state.bodies[id] = { body: typeof body === 'string' ? body : JSON.stringify(body), base64Encoded: false };
    state.socket.emit('Network.loadingFinished', { requestId: id, timestamp: 12 });
  }
  return { owner, directory, state, events, request, response, finish };
}

test('default keeps original intended navigation and exact command/error/intercept flow', async t => {
  const h = harness(t, { enabled: false });
  const browser = await openBrowser(intended);
  assert.equal(h.state.fetches[0].url, 'http://127.0.0.1:19222/json/new?' + intended);
  assert.deepEqual(h.state.commands.map(row => row.method), ['Runtime.evaluate']);
  assert.deepEqual(Object.keys(browser), ['command', 'evaluate', 'waitFor', 'click', 'reload', 'onIntercept', 'close']);
  let paused;
  browser.onIntercept(value => { paused = value; });
  h.state.socket.emit('Fetch.requestPaused', { requestId: 'original-intercept' });
  assert.deepEqual(paused, { requestId: 'original-intercept' });
  h.state.errors['Page.testError'] = { code: -32000, message: 'original-protocol-error' };
  await assert.rejects(browser.command('Page.testError'), { message: JSON.stringify(h.state.errors['Page.testError']) });
  await browser.close();
  assert.equal(fs.existsSync(h.directory), false);
  assert.equal(h.state.fetches.length, 2);
});

test('opt-in observes first navigation after listeners and awaited domains, with private output', async t => {
  const h = harness(t, { onNavigate(socket) {
    socket.emit('Network.requestWillBeSent', { requestId: 'first', frameId: 'frame-1', loaderId: 'loader-1',
      timestamp: 1, request: { url: api + '/matches', method: 'GET' } });
    socket.emit('Network.responseReceived', { requestId: 'first', timestamp: 2, response: { status: 200 } });
    socket.emit('Network.loadingFinished', { requestId: 'first', timestamp: 3 });
  } });
  h.state.bodies.first = { body: '[{"id":"own-match","revision":3}]', base64Encoded: false };
  const browser = await openBrowser(intended);
  await browser.close();
  assert.equal(h.state.fetches[0].url, 'http://127.0.0.1:19222/json/new?about:blank');
  assert.deepEqual(h.state.commands.slice(0, 3).map(row => row.method), ['Network.enable', 'Runtime.enable', 'Page.navigate']);
  assert.deepEqual(h.state.commands[2].params, { url: intended });
  const rows = h.events();
  assert.equal(rows.find(row => row.event === 'request').request_id, 'first');
  assert.equal(rows.find(row => row.event === 'response').status, 200);
  assert.equal(rows.find(row => row.event === 'finished').timestamp, 3);
  assert.equal(rows.at(-1).event, 'closed');
  assert.equal(rows.at(-1).complete, true);
  assert.equal(h.state.fetches.length, 2);
});

test('opt-in navigates the exact configured original URL, not a rewritten fixture or recipient', async t => {
  const h = harness(t);
  process.env.MTG_FRONTEND_ORIGIN = 'http://127.0.0.1:5193';
  h.state.snapshot.origin = process.env.MTG_FRONTEND_ORIGIN;
  const browser = await openBrowser(intended);
  await browser.close();
  assert.deepEqual(h.state.commands.find(row => row.method === 'Page.navigate').params,
    { url: 'http://127.0.0.1:5193/?fixture=original' });
  assert.ok(h.events().length > 0);
});

test('own completed restore projection excludes private cards, headers, bodies and foreign matches', async t => {
  const h = harness(t), browser = await openBrowser(intended);
  h.request('detail', '/matches/own-match'); h.response('detail');
  h.finish('detail', { id: 'own-match', revision: 17, mode: 'human_vs_human', controllers: { 1: 'human', 2: 'human' },
    priority_player: 2, players: { 1: { hand: [{ name: secret }] } }, log: [secret],
    pending_mechanic_choice: { kind: 'copy_target', player_id: 2, label: 'Choose target 1 for Lightning Helix (copy)', options: [secret] } });
  h.request('legal'); h.response('legal');
  h.finish('legal', { revision: 17, player_id: 2, moves: [{ type: 'choose_mechanic', options: [secret], card_name: secret }], secret });
  h.request('foreign', '/matches/foreign-match'); h.response('foreign'); h.finish('foreign', { id: 'foreign-match', secret });
  h.request('summary', '/matches'); h.response('summary');
  h.finish('summary', [{ id: 'own-match', revision: 17, players: [secret] }, { id: 'foreign-match', players: [secret] }]);
  h.state.socket.emit('Runtime.consoleAPICalled', { args: [{ value: secret }] });
  await browser.close();
  const rows = h.events(), text = JSON.stringify(rows);
  assert.ok(!text.includes(secret)); assert.ok(!text.includes('foreign-match'));
  const detail = rows.find(row => row.event === 'projection' && row.route === 'match').metadata;
  assert.equal(detail.revision, 17); assert.deepEqual(detail.controllers, { 1: 'human', 2: 'human' });
  assert.deepEqual(detail.pending, { kind: 'copy_target', player_id: 2, option_count: 1,
    label_sha256: '9712f6a511a845d284914ced349535a7f902f3c34d129a645955ecc541bab7be' });
  const legal = rows.find(row => row.event === 'projection' && row.route === 'legal-moves').metadata;
  assert.deepEqual(legal, { revision: 17, player_id: 2, move_count: 1, move_types: { choose_mechanic: 1 } });
  assert.deepEqual(h.state.commands.filter(row => row.method === 'Network.getResponseBody').map(row => row.params.requestId),
    ['detail', 'legal', 'summary']);
  assert.equal(h.state.fetches.length, 2);
});

test('failed and unanswered requests retain real frontier, not fabricated HTTP errors', async t => {
  const h = harness(t), browser = await openBrowser(intended);
  h.request('failed');
  h.state.socket.emit('Network.loadingFailed', { requestId: 'failed', timestamp: 11, canceled: true, errorText: secret,
    corsErrorStatus: { corsError: 'DisallowedByMode', failedParameter: secret } });
  h.request('unanswered', '/matches/own-match');
  await browser.close();
  const rows = h.events();
  assert.equal(rows.find(row => row.event === 'failed').canceled, true);
  assert.equal(rows.find(row => row.event === 'failed').cors_error, 'DisallowedByMode');
  assert.equal(rows.filter(row => row.event === 'response').length, 0);
  assert.equal(rows.at(-1).outstanding, 1); assert.equal(rows.at(-1).complete, false);
  assert.ok(!JSON.stringify(rows).includes(secret));
});

test('Runtime errors preserve class and location without arbitrary text/stack/console dumps', async t => {
  const h = harness(t), browser = await openBrowser(intended);
  h.state.socket.emit('Runtime.exceptionThrown', { timestamp: 23, exceptionDetails: { exceptionId: 4, text: secret,
    lineNumber: 491, columnNumber: 7, exception: { className: 'TypeError', description: secret },
    stackTrace: { callFrames: [{ functionName: secret, url: 'https://foreign.test/' + secret }] } } });
  await browser.close();
  const rows = h.events(), error = rows.find(row => row.event === 'runtime-error');
  assert.equal(error.class_name, 'TypeError'); assert.equal(error.line, 491); assert.equal(error.column, 7);
  assert.ok(!JSON.stringify(rows).includes(secret));
});

test('original reload rebinds read-only activeMatch before the same original reload command', async t => {
  const h = harness(t), browser = await openBrowser(intended);
  h.state.snapshot.activeMatch = 'new-own-match';
  await browser.reload({ ignoreCache: false });
  h.request('new', '/matches/new-own-match/legal-moves'); h.response('new');
  h.finish('new', { revision: 9, player_id: 1, moves: [] });
  await browser.close();
  const commands = h.state.commands, reload = commands.findIndex(row => row.method === 'Page.reload');
  assert.ok(commands.slice(0, reload).some(row => row.method === 'Runtime.evaluate' && row.params.expression.includes('mtg.activeMatch')));
  assert.deepEqual(commands[reload].params, { ignoreCache: false });
  assert.equal(h.events().find(row => row.event === 'request' && row.request_id === 'new').match_id, 'new-own-match');
  assert.ok(!commands.some(row => /setItem|removeItem|fetch\(/.test(row.params.expression ?? '')));
});

test('observer events do not consume original command replies, errors or explicit intercept events', async t => {
  const h = harness(t), browser = await openBrowser(intended);
  let paused;
  browser.onIntercept(value => { paused = value; });
  h.state.socket.emit('Fetch.requestPaused', { requestId: 'still-original-intercept' });
  h.request('during-command');
  h.state.errors['Page.testError'] = { code: -32602, message: 'original-error' };
  await assert.rejects(browser.command('Page.testError'), { message: '{"code":-32602,"message":"original-error"}' });
  assert.equal(await browser.evaluate('true'), true);
  assert.deepEqual(paused, { requestId: 'still-original-intercept' });
  await browser.close();
  assert.ok(!h.state.commands.some(row => /Fetch.enable|setExtraHTTPHeaders|setCacheDisabled|emulateNetwork/.test(row.method)));
  assert.ok(h.events().some(row => row.event === 'request'));
});

test('domain enable failure is explicitly incomplete without substituting a successful observation', async t => {
  const h = harness(t);
  h.state.errors['Network.enable'] = { code: -32000, message: secret };
  const browser = await openBrowser(intended); await browser.close();
  const rows = h.events();
  assert.ok(rows.some(row => row.event === 'incomplete' && row.reason === 'Network.enable'));
  assert.equal(rows.at(-1).complete, false);
  assert.ok(!JSON.stringify(rows).includes(secret));
  assert.equal(h.state.commands.filter(row => row.method === 'Page.navigate').length, 1);
});

for (const [name, body, error] of [['invalid-json', '{' + secret, null], ['body-command-error', '{}', { code: -32000, message: secret }]]) {
  test(name + ' remains incomplete and does not change the original protocol error', async t => {
    const h = harness(t), browser = await openBrowser(intended);
    if (error) h.state.errors['Network.getResponseBody'] = error;
    h.request('body'); h.response('body'); h.finish('body', body);
    await browser.close();
    const rows = h.events();
    assert.ok(rows.some(row => row.event === 'incomplete'));
    assert.equal(rows.at(-1).complete, false);
    assert.ok(!JSON.stringify(rows).includes(secret));
  });
}

test('unbound detail is visibly incomplete and unrelated route/body is never collected', async t => {
  const h = harness(t); h.state.snapshot.activeMatch = null;
  const browser = await openBrowser(intended);
  h.request('unbound', '/matches/unknown-match'); h.response('unbound'); h.finish('unbound', { secret });
  h.request('wrong-route', '/matches/own-match/action'); h.response('wrong-route'); h.finish('wrong-route', { secret });
  await browser.close();
  const rows = h.events();
  assert.equal(h.state.commands.filter(row => row.method === 'Network.getResponseBody').length, 0);
  assert.equal(rows.at(-1).complete, false);
  assert.ok(!JSON.stringify(rows).includes('unknown-match'));
});

test('redirect to a foreign origin removes body admission for the old request ID', async t => {
  const h = harness(t), browser = await openBrowser(intended);
  h.request('redirect');
  h.request('redirect', '/matches/own-match/legal-moves', { request: { url: 'https://foreign.test/matches/own-match/legal-moves', method: 'GET' } });
  h.response('redirect'); h.finish('redirect', { secret });
  await browser.close();
  assert.equal(h.state.commands.filter(row => row.method === 'Network.getResponseBody').length, 0);
  assert.ok(!JSON.stringify(h.events()).includes('foreign.test'));
});

test('writer failure is visible, private, and cannot replace the caller command error', async t => {
  const h = harness(t), browser = await openBrowser(intended);
  const write = fs.writeSync, stderr = process.stderr.write;
  const warnings = [];
  try {
    fs.writeSync = () => { throw new Error(secret); };
    process.stderr.write = chunk => { warnings.push(String(chunk)); return true; };
    h.state.socket.emit('Runtime.exceptionThrown', { exceptionDetails: { exception: { className: 'TypeError' } } });
    h.state.errors['Page.testError'] = { code: -32000, message: 'retained-primary-error' };
    await assert.rejects(browser.command('Page.testError'), { message: '{"code":-32000,"message":"retained-primary-error"}' });
    await browser.close();
    assert.equal(typeof browser.passiveCdp, 'function');
    assert.equal(browser.passiveCdp().complete, false);
    assert.ok(browser.passiveCdp().errors.includes('write'));
    assert.ok(warnings.some(row => row.includes('PASSIVE_CDP_INCOMPLETE')));
    assert.ok(!warnings.join('').includes(secret));
  } finally { fs.writeSync = write; process.stderr.write = stderr; }
});

for (const boundary of ['outside-owner', 'symlink', 'public-mode']) {
  test('private output rejects ' + boundary + ' before page creation', async t => {
    const h = harness(t);
    if (boundary === 'outside-owner') process.env.MTG_PASSIVE_CDP_EVIDENCE = path.join(path.dirname(h.owner), 'foreign-cdp-output');
    if (boundary === 'symlink') { fs.mkdirSync(path.join(h.owner, 'target')); fs.symlinkSync(path.join(h.owner, 'target'), h.directory); }
    if (boundary === 'public-mode') { fs.mkdirSync(h.directory); fs.chmodSync(h.directory, 0o755); }
    let browser;
    try { await assert.rejects(async () => { browser = await openBrowser(intended); }, /private.*owner|private.*directory/i); }
    finally { if (browser) await browser.close(); }
    assert.equal(h.state.fetches.length, 0);
  });
}

test('initial original fetch error closes the observer without masking that exact error', async t => {
  const h = harness(t); h.state.fetchFailure = new Error('original-create-error');
  await assert.rejects(openBrowser(intended), error => error === h.state.fetchFailure);
  assert.equal(h.events().at(-1).event, 'closed');
  assert.equal(h.state.fetches.length, 1);
  const handles = fs.readdirSync('/proc/self/fd').flatMap(fd => {
    try { return fs.readlinkSync('/proc/self/fd/' + fd).startsWith(h.directory + '/') ? [fd] : []; }
    catch (error) { if (error.code !== 'ENOENT') throw error; return []; }
  });
  assert.deepEqual(handles, []);
});

test('finished without an actual response event cannot certify response coverage', async t => {
  const h = harness(t), browser = await openBrowser(intended);
  h.request('no-response'); h.finish('no-response', { player_id: 1, moves: [] });
  await browser.close();
  const rows = h.events();
  assert.ok(rows.some(row => row.event === 'incomplete' && row.reason === 'response-missing'));
  assert.equal(rows.at(-1).complete, false);
  assert.equal(rows.filter(row => row.event === 'response').length, 0);
});

test('read-only route binding observes a changed activeMatch even without an original reload', async t => {
  const h = harness(t), browser = await openBrowser(intended);
  h.state.snapshot.activeMatch = 'new-active-match';
  h.request('new-active', '/matches/new-active-match/legal-moves'); h.response('new-active');
  h.finish('new-active', { player_id: 2, revision: 4, moves: [] });
  await browser.close();
  const rows = h.events();
  assert.equal(rows.find(row => row.event === 'projection')?.match_id, 'new-active-match');
  assert.equal(h.state.fetches.length, 2);
});

test('invalid observer backend origin fails before opening a writer or page', async t => {
  const h = harness(t); process.env.MTG_BACKEND_ORIGIN = 'not a URL';
  await assert.rejects(openBrowser(intended), /Invalid URL/);
  assert.equal(h.state.fetches.length, 0);
  assert.equal(fs.existsSync(h.directory) ? fs.readdirSync(h.directory).length : 0, 0);
});

test('private owner on NFS is rejected before opening writer or page', async t => {
  const h = harness(t), statfs = fs.statfsSync;
  fs.statfsSync = () => ({ type: 0x6969 });
  let browser;
  try { await assert.rejects(async () => { browser = await openBrowser(intended); }, /private.*local/i); }
  finally { fs.statfsSync = statfs; if (browser) await browser.close(); }
  assert.equal(h.state.fetches.length, 0);
});

test('non-schema CORS strings cannot introduce arbitrary text into private projections', async t => {
  const h = harness(t), browser = await openBrowser(intended);
  h.request('cors');
  h.state.socket.emit('Network.loadingFailed', { requestId: 'cors', corsErrorStatus: { corsError: 'HiddenPrivateLetters' } });
  await browser.close();
  assert.ok(!JSON.stringify(h.events()).includes('HiddenPrivateLetters'));
});

test('a pending body projection cannot block event metadata or report complete coverage', async t => {
  const h = harness(t), browser = await openBrowser(intended);
  h.state.hold.add('Network.getResponseBody');
  h.request('held-body'); h.response('held-body'); h.finish('held-body', { revision: 8, player_id: 1, moves: [] });
  try {
    await new Promise(resolve => setImmediate(resolve));
    h.state.socket.emit('Runtime.exceptionThrown', { exceptionDetails: { exception: { className: 'TypeError' } } });
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(await browser.evaluate('true'), true);
    assert.ok(h.events().some(row => row.event === 'runtime-error'));
    assert.equal(browser.passiveCdp().complete, false);
  } finally {
    for (const reply of h.state.heldReplies) h.state.socket.onmessage({ data: JSON.stringify(reply) });
    await browser.close();
  }
  assert.equal(h.events().at(-1).complete, true);
});

for (const boundary of ['foreign-match', 'missing-binding']) {
  test('same-ID same-origin ' + boundary + ' redirect invalidates previous own body admission', async t => {
    const h = harness(t), browser = await openBrowser(intended);
    h.request('same-id');
    await browser.evaluate('true');
    if (boundary === 'missing-binding') {
      h.state.snapshot.activeMatch = null;
      await browser.reload({ ignoreCache: false });
    }
    h.request('same-id', boundary === 'foreign-match' ? '/matches/foreign-match/legal-moves' : '/matches/own-match/legal-moves');
    h.response('same-id');
    h.finish('same-id', { revision: 99, player_id: 2, moves: Array.from({ length: 7 }, () => ({ type: 'choose_mechanic', options: [secret] })) });
    await browser.close();
    const rows = h.events();
    assert.equal(h.state.commands.filter(row => row.method === 'Network.getResponseBody').length, 0, 'Rejected redirected body must not be read');
    assert.equal(rows.filter(row => row.event === 'projection').length, 0, 'Foreign metrics must not be attributed to the earlier own request');
    assert.equal(rows.at(-1).complete, false);
    assert.ok(!JSON.stringify(rows).includes('foreign-match'));
    assert.ok(!JSON.stringify(rows).includes(secret));
  });
}

test('same-ID still-owned redirect keeps genuine response admission and complete observer coverage', async t => {
  const h = harness(t), browser = await openBrowser(intended);
  h.request('same-id');
  h.request('same-id', '/matches/own-match/legal-moves', { redirectResponse: { status: 302, headers: { private: secret }, url: secret } });
  h.response('same-id');
  h.finish('same-id', { revision: 19, player_id: 1, moves: [{ type: 'choose_mechanic' }] });
  await browser.close();
  const rows = h.events();
  assert.equal(h.state.commands.filter(row => row.method === 'Network.getResponseBody').length, 1);
  assert.deepEqual(rows.find(row => row.event === 'projection').metadata,
    { revision: 19, player_id: 1, move_count: 1, move_types: { choose_mechanic: 1 } });
  assert.equal(rows.find(row => row.event === 'redirect')?.status, 302);
  assert.ok(!JSON.stringify(rows).includes(secret));
  assert.equal(rows.at(-1).complete, true);
});

for (const loss of ['close', 'error']) {
  test('unexpected post-start transport ' + loss + ' cannot certify complete coverage with no outstanding request', async t => {
    const h = harness(t), browser = await openBrowser(intended);
    assert.equal(browser.passiveCdp().outstanding, 0);
    h.state.socket.emitTransport(loss);
    await browser.close();
    const rows = h.events();
    assert.equal(rows.at(-1).complete, false);
    assert.ok(rows.at(-1).errors.includes('transport-' + loss));
    assert.ok(!JSON.stringify(rows).includes(secret));
    assert.equal(h.state.fetches.length, 2);
  });
}

for (const hop of ['missing', 'invalid']) {
  test('same-ID owned redirect with ' + hop + ' prior-hop status cannot certify complete coverage', async t => {
    const h = harness(t), browser = await openBrowser(intended);
    h.request('same-id');
    h.request('same-id', '/matches/own-match/legal-moves', hop === 'invalid' ? { redirectResponse: { status: secret } } : {});
    h.response('same-id');
    h.finish('same-id', { revision: 20, player_id: 1, moves: [] });
    await browser.close();
    const rows = h.events();
    assert.equal(rows.at(-1).complete, false);
    assert.ok(rows.at(-1).errors.includes('redirect-response-missing'));
    assert.equal(rows.find(row => row.event === 'projection').metadata.revision, 20);
    assert.ok(!JSON.stringify(rows).includes(secret));
  });
}
