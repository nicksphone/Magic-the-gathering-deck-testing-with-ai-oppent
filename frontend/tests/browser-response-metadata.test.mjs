import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import { traceStartRecoveryResponses } from './browser-start-recovery-diagnostics.mjs';

const frontend = 'http://127.0.0.1:15173';
const backend = 'http://127.0.0.1:10199';
const secret = 'PRIVATE_URL_HEADER_BODY_FRAME_AND_ERROR';

function observer() {
  let report;
  const commands = [];
  const trace = traceStartRecoveryResponses(async (...args) => { commands.push(args); },
    async () => {}, frontend, value => { report = value; }, { backend });
  assert.equal(typeof trace.observeBrowserEvent, 'function', 'Opt-in metadata observer is absent');
  return { trace, commands, emit(method, params = {}) { trace.observeBrowserEvent({ method, params }); },
    report() { trace.reportFailure(); return report; } };
}

function request(h, id, method, route = '/matches/private-match/action', extra = {}) {
  h.emit('Network.requestWillBeSent', { requestId: id, frameId: secret, loaderId: secret,
    timestamp: 1, request: { method, url: backend + route, headers: { Authorization: secret },
      postData: secret }, ...extra });
}

test('native OPTIONS and POST lifecycles are distinct from Fetch interception', () => {
  const h = observer();
  request(h, 'post-id', 'POST');
  request(h, 'options-id', 'OPTIONS', undefined, { initiator: { type: 'preflight', requestId: 'post-id' } });
  h.emit('Network.responseReceived', { requestId: 'options-id', timestamp: 2, response: { status: 204 } });
  h.emit('Network.loadingFinished', { requestId: 'options-id', timestamp: 3 });
  h.emit('Network.responseReceived', { requestId: 'post-id', timestamp: 4, response: { status: 200 } });
  h.emit('Network.loadingFinished', { requestId: 'post-id', timestamp: 5 });
  const report = h.report(), rows = report.browserMetadata.events;
  assert.equal(report.responses.length, 0, 'Network observations must not fabricate Fetch pauses');
  assert.deepEqual(rows.filter(row => row.event === 'request').map(row => row.method), ['POST', 'OPTIONS']);
  assert.deepEqual(rows.filter(row => row.event === 'response').map(row => row.status), [204, 200]);
  assert.equal(rows.find(row => row.method === 'OPTIONS').initiatorNetworkOrdinal,
    rows.find(row => row.method === 'POST').networkOrdinal);
  assert.equal(report.browserMetadata.outstandingRequests, 0);
  assert.deepEqual(h.commands, [], 'Metadata must never fetch a response body or issue protocol commands');
});

test('OPTIONS-only history never implies a missing POST outside Fetch', () => {
  const h = observer(); request(h, 'options', 'OPTIONS');
  const report = h.report();
  assert.equal(report.browserMetadata.events.length, 1);
  assert.equal(report.browserMetadata.events[0].method, 'OPTIONS');
  assert.equal(report.browserMetadata.outstandingRequests, 1);
  assert.equal(report.responses.length, 0);
});

test('failure categories retain CORS, blocking and cancellation but no arbitrary text', () => {
  const h = observer(); request(h, secret, 'POST', '/matches/start?private=' + secret);
  h.emit('Network.loadingFailed', { requestId: secret, timestamp: 9, canceled: true,
    errorText: 'net::ERR_FAILED', blockedReason: 'origin',
    corsErrorStatus: { corsError: 'PreflightAllowOriginMismatch', failedParameter: secret } });
  const report = h.report(), failed = report.browserMetadata.events.find(row => row.event === 'failed');
  assert.equal(failed.canceled, true);
  assert.equal(failed.errorClass, 'net::ERR_FAILED');
  assert.equal(failed.blockedReason, 'origin');
  assert.equal(failed.corsError, 'PreflightAllowOriginMismatch');
  assert.equal(failed.route, 'start');
  assert.equal(report.browserMetadata.outstandingRequests, 0);
  assert.ok(!JSON.stringify(report).includes(secret));
  assert.ok(!JSON.stringify(report).includes(backend));
});

test('unknown failure fields are explicit other values, never raw strings or hashes', () => {
  const h = observer(); request(h, 'post', 'POST');
  h.emit('Network.loadingFailed', { requestId: 'post', errorText: secret, blockedReason: secret,
    corsErrorStatus: { corsError: secret, failedParameter: secret } });
  const report = h.report(), failed = report.browserMetadata.events.at(-1);
  assert.equal(failed.errorClass, 'other'); assert.equal(failed.blockedReason, 'other');
  assert.equal(failed.corsError, 'other'); assert.equal(failed.canceled, null);
  assert.ok(!JSON.stringify(report).includes(secret));
});

test('navigation and context events retain only local frame and loader ordinals', () => {
  const h = observer();
  h.emit('Page.frameNavigated', { frame: { id: secret, loaderId: 'first-' + secret,
    url: frontend + '/private/' + secret, securityOrigin: secret } });
  h.emit('Runtime.executionContextsCleared');
  h.emit('Page.frameNavigated', { frame: { id: secret, loaderId: 'second-' + secret,
    url: frontend + '/different/' + secret } });
  h.emit('Page.navigatedWithinDocument', { frameId: secret, url: frontend + '/#' + secret });
  const rows = h.report().browserMetadata.events;
  assert.deepEqual(rows.map(row => row.event), ['frame-navigated', 'contexts-cleared', 'frame-navigated', 'same-document-navigation']);
  assert.equal(rows[0].frameOrdinal, rows[2].frameOrdinal);
  assert.notEqual(rows[0].loaderOrdinal, rows[2].loaderOrdinal);
  assert.equal(rows[0].mainFrame, true);
  assert.ok(!JSON.stringify(rows).includes(secret));
  assert.ok(!JSON.stringify(rows).includes(frontend));
});

test('unmatched failure is labeled unknown rather than bound to the last request', () => {
  const h = observer(); request(h, 'known', 'OPTIONS');
  h.emit('Network.loadingFailed', { requestId: 'different', errorText: 'net::ERR_ABORTED' });
  const metadata = h.report().browserMetadata, failed = metadata.events.at(-1);
  assert.equal(failed.route, 'unmatched'); assert.equal(failed.method, null);
  assert.equal(failed.networkOrdinal, null);
  assert.equal(metadata.unmatchedEvents, 1);
  assert.equal(metadata.outstandingRequests, 1);
});

test('a redirect leaving the scoped route retains its original local correlation', () => {
  const h = observer(); request(h, 'redirected', 'POST');
  request(h, 'redirected', 'GET', undefined, { request: { method: 'GET', url: frontend + '/unrelated' } });
  const metadata = h.report().browserMetadata;
  assert.equal(metadata.events.at(-1).event, 'scope-exit');
  assert.equal(metadata.events.at(-1).networkOrdinal, metadata.events[0].networkOrdinal);
  assert.equal(metadata.outstandingRequests, 0);
  assert.ok(!JSON.stringify(metadata).includes('redirected'));
});

test('native preflight initiator reference survives without inventing a parent request event', () => {
  const h = observer();
  request(h, 'preflight', 'OPTIONS', '/matches/start', { initiator: { type: 'preflight', requestId: 'parent' } });
  h.emit('Network.responseReceived', { requestId: 'preflight', response: { status: 204 } });
  h.emit('Network.loadingFinished', { requestId: 'preflight' });
  h.emit('Network.loadingFailed', { requestId: 'parent', errorText: 'net::ERR_FAILED',
    corsErrorStatus: { corsError: 'PreflightAllowOriginMismatch' } });
  const metadata = h.report().browserMetadata;
  assert.equal(typeof metadata.events[0].initiatorNetworkOrdinal, 'number');
  assert.equal(metadata.events.at(-1).networkOrdinal, metadata.events[0].initiatorNetworkOrdinal);
  assert.equal(metadata.events.at(-1).route, 'unmatched');
  assert.deepEqual(metadata.events.filter(row => row.event === 'request').map(row => row.method), ['OPTIONS']);
  assert.equal(metadata.unmatchedInitiators, 1);
  assert.equal(metadata.outstandingRequests, 0);
});

test('unrelated unmatched failures do not consume scoped-request correlation identities', () => {
  const h = observer();
  for (let n = 0; n < 100; n++) h.emit('Network.loadingFailed', { requestId: 'unrelated-' + n, errorText: secret });
  request(h, 'scoped', 'POST');
  const metadata = h.report().browserMetadata;
  assert.equal(metadata.requestOverflow, 0);
  assert.equal(metadata.outstandingRequests, 1);
  assert.equal(metadata.unmatchedEvents, 100);
});

test('same-document navigation with no frame history reports unknown main-frame identity', () => {
  const h = observer();
  h.emit('Page.navigatedWithinDocument', { frameId: secret, url: frontend + '/' + secret });
  const row = h.report().browserMetadata.events[0];
  assert.equal(row.mainFrame, null);
  assert.ok(!JSON.stringify(row).includes(secret));
});

test('metadata output and correlation storage are finitely bounded under excess input', () => {
  const h = observer();
  for (let n = 0; n < 1000; n++) request(h, 'request-' + n, 'POST');
  for (let n = 0; n < 1000; n++) h.emit('Page.frameNavigated', {
    frame: { id: 'frame-' + n, loaderId: 'loader-' + n, url: frontend + '/' + secret } });
  const report = h.report(), metadata = report.browserMetadata;
  assert.ok(metadata.events.length <= 64);
  assert.ok(metadata.omittedEvents > 0 && metadata.requestOverflow > 0 && metadata.correlationOverflow > 0);
  assert.ok(metadata.outstandingRequests <= 16);
  assert.ok(JSON.stringify(report).length < 24000);
  assert.ok(!JSON.stringify(report).includes(secret));
});

test('malformed diagnostics cannot throw into the command/interception path', () => {
  const h = observer();
  assert.doesNotThrow(() => h.trace.observeBrowserEvent(null));
  assert.doesNotThrow(() => h.emit('Network.requestWillBeSent', { request: null }));
  assert.doesNotThrow(() => h.emit('Page.frameNavigated', {}));
  assert.ok(h.report().browserMetadata.invalidEvents > 0);
});

test('foreign URLs, credentials, unrelated bodies and headers are not observed', () => {
  const h = observer();
  request(h, 'foreign', 'POST', undefined, { request: { method: 'POST',
    url: 'https://foreign.example/' + secret, headers: { Cookie: secret }, postData: secret } });
  request(h, 'credential', 'POST', undefined, { request: { method: 'POST',
    url: 'http://user:password@127.0.0.1:10199/matches/start', postData: secret } });
  h.emit('Runtime.consoleAPICalled', { args: [{ value: secret }] });
  assert.deepEqual(h.report().browserMetadata.events, []);
  assert.deepEqual(h.commands, []);
});

test('default wrapper retains its original report schema and command behavior', () => {
  let report;
  const trace = traceStartRecoveryResponses(async () => {}, async () => {}, frontend, value => { report = value; });
  assert.equal(trace.observeBrowserEvent, undefined);
  trace.reportFailure();
  assert.deepEqual(Object.keys(report).sort(), ['omittedResponses', 'pendingCommands', 'responses']);
});

function driverReceiver(intercept, pending = new Map()) {
  const source = readFileSync(new URL('./browser-driver.mjs', import.meta.url), 'utf8');
  const begin = source.indexOf('  socket.onmessage =');
  const end = source.indexOf('\n  function rawCommand', begin);
  assert.ok(begin >= 0 && end > begin);
  const context = { socket: {}, passive: null, intercept, pending, JSON, Error };
  vm.runInNewContext(source.slice(begin, end), context);
  return value => context.socket.onmessage({ data: JSON.stringify(value) });
}

test('actual driver forwards native metadata without consuming original command replies', () => {
  const h = observer(); let result;
  const receive = driverReceiver(h.trace, new Map([[9, { resolve(value) { result = value; } }]]));
  receive({ method: 'Network.requestWillBeSent', params: { requestId: 'native',
    request: { url: backend + '/matches/start', method: 'POST' } } });
  receive({ id: 9, result: { original: true } });
  assert.deepEqual(result, { original: true });
  assert.equal(h.report().browserMetadata.events[0].method, 'POST');
});

test('a throwing diagnostic property cannot replace command rejection or real Fetch handler failure', () => {
  const diagnostic = new Error(secret), primary = new Error('original Fetch error');
  const intercept = () => { throw primary; }; let rejected;
  Object.defineProperty(intercept, 'observeBrowserEvent', { get() { throw diagnostic; } });
  const receive = driverReceiver(intercept, new Map([[5, { reject(value) { rejected = value; } }]]));
  receive({ id: 5, error: { code: -32602, message: 'original protocol error' } });
  assert.equal(rejected.message, '{"code":-32602,"message":"original protocol error"}');
  assert.throws(() => receive({ method: 'Fetch.requestPaused', params: { requestId: 'original' } }),
    error => error === primary);
});

for (const outcome of ['accepted', 'rejected']) {
  test('metadata snapshot is immutable across later native events and ' + outcome + ' ACK', async () => {
    let release, reject, report;
    const error = new Error('original native rejection');
    const ack = new Promise((yes, no) => { release = yes; reject = no; });
    const trace = traceStartRecoveryResponses(() => ack, async (event, command) => {
      await command('Fetch.continueRequest', { requestId: event.requestId });
    }, frontend, value => { report = value; }, { backend });
    trace.observeBrowserEvent({ method: 'Network.requestWillBeSent', params: { requestId: 'native',
      request: { url: backend + '/matches/start', method: 'POST' } } });
    const paused = trace({ requestId: 'fetch', networkId: 'native', request: { method: 'POST' } });
    paused.catch(() => {});
    trace.reportFailure(); const before = JSON.stringify(report);
    assert.equal(report.pendingCommands, 1);
    assert.equal(report.responses[0].networkOrdinal, report.browserMetadata.events[0].networkOrdinal);
    trace.observeBrowserEvent({ method: 'Network.loadingFailed', params: { requestId: 'native', errorText: secret } });
    if (outcome === 'accepted') { release(); await paused; }
    else { reject(error); await assert.rejects(paused, actual => actual === error); }
    trace.reportFailure(); assert.equal(JSON.stringify(report), before);
  });
}

const recoverySource = readFileSync(new URL('./browser-start-recovery.mjs', import.meta.url), 'utf8');
for (const outcome of ['success', 'failure', 'reporter-failure']) {
  test('actual outer recovery finalization publishes only failures on ' + outcome + ' without replacing its result', async () => {
    const failure = recoverySource.lastIndexOf('\n} catch (error) {');
    const begin = failure >= 0 ? failure : recoverySource.lastIndexOf('\n} finally {');
    assert.ok(begin >= 0);
    const finalization = recoverySource.slice(begin + 3);
    assert.ok(finalization.startsWith('catch (error) {') || finalization.startsWith('finally {'));
    const primary = new Error('original waitFor failure'); let published = 0, closed = 0;
    const fn = Object.assign(() => {}, { trace: { reportFailure() {
      published++; if (outcome === 'reporter-failure') throw new Error(secret);
    } } });
    const context = { startWithDroppedResponses: fn, primary, close: async () => { closed++; } };
    const body = outcome === 'success' ? 'return 42;' : 'throw primary;';
    const result = vm.runInNewContext(`(async () => { try { ${body} } ${finalization} })()`, context);
    if (outcome === 'success') assert.equal(await result, 42);
    else await assert.rejects(result, error => error === primary);
    assert.equal(published, outcome === 'success' ? 0 : 1); assert.equal(closed, 1);
  });
}

function scenarioInitialization(name, rejectAt) {
  const recovery = name === 'recovery';
  const source = recovery ? recoverySource
    : readFileSync(new URL('./browser-ui-v2-costs.mjs', import.meta.url), 'utf8');
  const begin = source.indexOf(recovery ? 'const { evaluate,' : 'const b=await openBrowser(ui);');
  const scenario = source.indexOf(recovery ? '  await selectDecks();' : ' for(const seat of [1,2])');
  const finalization = source.lastIndexOf(recovery ? '\n} catch (error) {' : '\n} finally {');
  assert.ok(begin >= 0 && scenario > begin && finalization > scenario);
  const calls = [], primary = new Error('domain subscription rejected');
  let closed = 0, enteredScenario = false;
  const browser = { command: async method => {
    calls.push(method); if (method === rejectAt) throw primary;
  }, close: async () => { closed++; } };
  const result = vm.runInNewContext(`(async () => { ${source.slice(begin, scenario)}
    enterScenario(); ${source.slice(finalization)} })()`,
  { browser, ui: frontend, openBrowser: async () => browser,
    enterScenario: () => { enteredScenario = true; } });
  return { result, calls, primary, closed: () => closed, enteredScenario: () => enteredScenario };
}

for (const name of ['recovery', 'held-response']) {
  test(`actual ${name} program subscribes to Network, Page and Runtime before its scenarios`, async () => {
    const h = scenarioInitialization(name);
    await h.result;
    assert.deepEqual(h.calls, ['Network.enable', 'Page.enable', 'Runtime.enable']);
    assert.equal(h.enteredScenario(), true);
    assert.equal(h.closed(), 1);
  });
  for (const domain of ['Network.enable', 'Page.enable', 'Runtime.enable']) {
    test(`actual ${name} program closes its page and preserves a rejected ${domain}`, async () => {
      const h = scenarioInitialization(name, domain);
      await assert.rejects(h.result, error => error === h.primary);
      assert.equal(h.enteredScenario(), false);
      assert.equal(h.closed(), 1);
      assert.equal(h.calls.at(-1), domain);
    });
  }
}
