import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';
import {stripTypeScriptTypes} from 'node:module';
import {HttpResponseError, httpErrorMessage} from '../src/api/errors.ts';
import {traceStartRecoveryResponses} from './browser-start-recovery-diagnostics.mjs';

const clientSource = fs.readFileSync(new URL('../src/api/client.ts', import.meta.url), 'utf8');
const reqSource = clientSource.slice(clientSource.indexOf('async function req<T>'), clientSource.indexOf('async function matchReq('));
const recorderURL = new URL('../src/api/request-signal-diagnostics.ts', import.meta.url);
const recorderSource = fs.existsSync(recorderURL) ? fs.readFileSync(recorderURL, 'utf8') : '';
const tag = 'MTG_REQUEST_SIGNAL_DIAGNOSTIC';
const privateValue = 'PRIVATE_TOKEN_URL_KEY_BODY_STACK';

// On the unmodified baseline req has no recorder reference: RED exercises the
// actual old request body, not an absent-module import failure.
function client(options = {}) {
  const {fetch = async () => { throw new TypeError(privateValue); }, debug, now = () => 12} = options;
  const flag = Object.hasOwn(options, 'flag') ? options.flag : '1';
  const logs = [], clocks = [];
  const env = {AbortSignal, HttpResponseError, httpErrorMessage, Error, TypeError, JSON, TextEncoder,
    API: 'unit-only-not-a-transport', requestDiagnosticFlag: flag,
    performance: {now() { clocks.push(true); return now(); }}, fetch,
    console: {debug(...args) { logs.push(args); if (debug) debug(...args); }}};
  const code = stripTypeScriptTypes(recorderSource.replace(/^export /gm, '') + '\n'
    + reqSource.replaceAll('import.meta.env.VITE_REQUEST_SIGNAL_DIAGNOSTICS', 'requestDiagnosticFlag'));
  vm.runInNewContext(code + '\nglobalThis.actualRequest = req;', env);
  return {request: env.actualRequest, logs, clocks, records: () => logs.map(([label, value]) => {
    assert.equal(label, tag); return JSON.parse(value);
  })};
}
const row = changes => ({phase: 'fetch-rejected', ordinal: 1, route: 'action', method: 'POST',
  elapsedMs: 12, signalAvailable: true, initialAborted: false, signalAborted: false, signalReasonClass: null,
  errorClass: 'TypeError', atRecordCap: false, ...changes});
function privateFree(value) { assert.doesNotMatch(JSON.stringify(value), /PRIVATE_|https?:|Authorization|Idempotency|callFrames/); }

test('actual req records its selected un-aborted signal on rejection and rethrows the same object', async () => {
  const error = new TypeError(privateValue); let options;
  const f = client({fetch: async (_url, init) => { options = init; throw error; }});
  await assert.rejects(f.request('/matches/private/action', {method: 'POST'}), e => e === error);
  assert.equal(f.records().length, 1);
  assert.equal(f.records()[0].signalAborted, options.signal.aborted);
  assert.equal(f.records()[0].initialAborted, false);
  assert.equal(f.records()[0].signalAvailable, true);
  assert.equal(f.records()[0].route, 'action'); assert.equal(f.records()[0].method, 'POST'); privateFree(f.records());
});
for (const flag of [undefined, null, false, true, 0, 1, '0', 'true']) {
  test(`strict opt-in rejects ${String(flag)} without clocks or records`, async () => {
    const f = client({flag}); await assert.rejects(f.request('/matches/start'));
    assert.deepEqual(f.logs, []); assert.deepEqual(f.clocks, []);
  });
}
test('actual req creates exactly its original 30000ms signal once', async () => {
  const timeout = AbortSignal.timeout, values = [];
  AbortSignal.timeout = ms => { values.push(ms); return timeout(ms); };
  try {
    const f = client(); await assert.rejects(f.request('/matches/private/legal-moves'));
    assert.deepEqual(values, [30000]); assert.equal(f.records()[0].route, 'legal-moves');
  } finally { AbortSignal.timeout = timeout; }
});
test('a supplied signal is the exact fetch signal and its actual abort reason is typed only', async () => {
  const signal = AbortSignal.abort(new DOMException(privateValue, 'TimeoutError'));
  const timeout = AbortSignal.timeout; let passed;
  AbortSignal.timeout = () => { throw new Error('No new default timer'); };
  try {
    const f = client({fetch: async (_url, init) => { passed = init.signal; throw new TypeError(privateValue); }});
    await assert.rejects(f.request('/matches/start', {method: 'POST', signal}));
    assert.equal(passed, signal); assert.equal(f.records()[0].signalAborted, true);
    assert.equal(f.records()[0].initialAborted, true);
    assert.equal(f.records()[0].signalReasonClass, 'TimeoutError'); privateFree(f.records());
  } finally { AbortSignal.timeout = timeout; }
});
test('a unit-supplied signal that aborts during fetch is distinguished from an already-aborted signal', async () => {
  const controller = new AbortController();
  const error = new DOMException(privateValue, 'AbortError');
  const f = client({fetch: async () => { controller.abort(error); throw error; }});
  await assert.rejects(f.request('/matches/start', {signal: controller.signal}), e => e === error);
  assert.equal(f.records()[0].initialAborted, false); assert.equal(f.records()[0].signalAborted, true);
  assert.equal(f.records()[0].signalReasonClass, 'AbortError');
});
test('successful and HTTP-error requests gain no diagnostic records or response-body reads', async () => {
  let reads = 0;
  const success = client({fetch: async () => ({ok: true, json() { reads++; return Promise.resolve({unit: true}); }})});
  assert.deepEqual(await success.request('/matches/start'), {unit: true}); assert.equal(reads, 1);
  assert.deepEqual(success.logs, []);
  const http = client({fetch: async () => ({ok: false, status: 409, text: async () => 'unit conflict'})});
  await assert.rejects(http.request('/matches/start'), e => e instanceof HttpResponseError && e.status === 409);
  assert.deepEqual(http.logs, []);
});
test('the original JSON-promise rejection remains outside fetch attribution', async () => {
  const error = new SyntaxError(privateValue); let reads = 0;
  const f = client({fetch: async () => ({ok: true, json() { reads++; return Promise.reject(error); }})});
  await assert.rejects(f.request('/matches/start'), e => e === error);
  assert.equal(reads, 1); assert.deepEqual(f.logs, []);
  assert.equal((stripTypeScriptTypes(reqSource).match(/\bawait\b/g) ?? []).length, 2);
  assert.match(reqSource, /return res\.json\(\) as Promise<T>;/);
});
test('original URL/options getter evaluation order and object identities are retained', async () => {
  const order = [], signal = AbortSignal.timeout(30000), headers = {unit: 'value'};
  const address = {toString() { order.push('path'); return '/matches/private/action'; }};
  const init = {get headers() { order.push('headers'); return headers; },
    get method() { order.push('method'); return 'POST'; }, get signal() { order.push('signal'); return signal; }};
  const f = client({fetch: async (_url, options) => {
    order.push('fetch'); assert.equal(options.headers, headers); assert.equal(options.signal, signal);
    throw new TypeError(privateValue);
  }});
  await assert.rejects(f.request(address, init));
  assert.deepEqual(order, ['path', 'headers', 'method', 'signal', 'signal', 'fetch']);
  assert.equal(f.records()[0].route, 'other');
});
test('all route and method information is finite and never includes request data', async () => {
  for (const [route, expected] of [['/matches/start', 'start'], ['/matches/unit/legal-moves', 'legal-moves'],
    ['/matches/unit/action', 'action'], ['/private?token=' + privateValue, 'other']]) {
    const f = client(); await assert.rejects(f.request(route, {method: 'PRIVATE_METHOD', body: privateValue}));
    assert.equal(f.records()[0].route, expected); assert.equal(f.records()[0].method, 'other'); privateFree(f.records());
  }
});
test('records stop at16 and the final record explicitly marks possible truncation', async () => {
  const f = client(); for (let i = 0; i < 20; i++) await assert.rejects(f.request('/matches/start'));
  assert.equal(f.records().length, 16); assert.deepEqual(f.records().map(r => r.ordinal), Array.from({length: 16}, (_, i) => i + 1));
  assert.equal(f.records()[15].atRecordCap, true); privateFree(f.records());
});
test('sink, clock, error-name, and non-native signal failures never replace the request error', async () => {
  for (const options of [{debug() { throw new Error(privateValue); }}, {now() { throw new Error(privateValue); }}]) {
    const error = new TypeError(privateValue), f = client({...options, fetch: async () => { throw error; }});
    await assert.rejects(f.request('/matches/start'), e => e === error);
  }
  const error = {get name() { throw new Error(privateValue); }}, f = client({fetch: async () => { throw error; }});
  await assert.rejects(f.request('/matches/start', {signal: {aborted: false}}), e => e === error);
  assert.equal(f.records()[0].signalAvailable, false); assert.equal(f.records()[0].signalAborted, null);
  assert.equal(f.records()[0].errorClass, 'other'); privateFree(f.records());
});

const front = 'http://127.0.0.1:15173', back = 'http://127.0.0.1:10199';
function observer() {
  let result; const commands = [];
  const trace = traceStartRecoveryResponses(async (...args) => commands.push(args), async () => {}, front, value => { result = value; }, {backend: back});
  const send = (method, params) => trace.observeBrowserEvent({method, params});
  const context = (id = 3, changes = {}) => send('Runtime.executionContextCreated', {context: {
    id, origin: front, auxData: {isDefault: true, frameId: 'PRIVATE_FRAME'}, ...changes}});
  const message = (value = row(), id = 3) => send('Runtime.consoleAPICalled', {type: 'debug', executionContextId: id,
    args: [{type: 'string', value: tag}, {type: 'string', value: JSON.stringify(value)}], stackTrace: privateValue});
  send('Page.frameNavigated', {frame: {id: 'PRIVATE_FRAME', loaderId: 'PRIVATE_LOADER'}});
  return {send, context, message, commands, result() { trace.reportFailure(); return result.browserMetadata; }};
}
test('existing native stream admits typed records only from an actual owned default context', () => {
  const f = observer(); f.context(); f.message(); const d = f.result();
  assert.equal(d.requestSignalAttribution.records.length, 1);
  assert.equal(d.requestSignalAttribution.records[0].frameOrdinal, 1);
  assert.equal(d.requestSignalAttribution.status, 'observed-partial');
  assert.deepEqual(f.commands, []); privateFree(d);
});
test('unknown, foreign and nondefault console contexts cannot attribute an App signal', () => {
  for (const changes of [{origin: 'https://foreign.invalid'}, {auxData: {isDefault: false, frameId: 'PRIVATE_FRAME'}}, {id: '3'}]) {
    const f = observer(); f.context(3, changes); f.message();
    assert.equal(f.result().requestSignalAttribution?.records.length ?? 0, 0); privateFree(f.result());
  }
});
test('context destruction, clearing, and duplicate identity cannot retain stale attribution', () => {
  for (const event of ['Runtime.executionContextDestroyed', 'Runtime.executionContextsCleared', 'duplicate']) {
    const f = observer(); f.context();
    if (event === 'duplicate') f.context(); else f.send(event, {executionContextId: 3});
    f.message(); assert.equal(f.result().requestSignalAttribution?.records.length ?? 0, 0);
  }
});
test('malformed or private console fields are rejected rather than sanitized into a false record', () => {
  for (const changes of [{ordinal: 1.5}, {route: privateValue}, {method: privateValue}, {signalAborted: 'false'},
    {signalAvailable: false}, {signalReasonClass: 'TimeoutError'}, {elapsedMs: 30001}, {errorClass: privateValue},
    {raw: privateValue}, {atRecordCap: true}]) {
    const f = observer(); f.context(); f.message(row(changes)); const d = f.result();
    assert.equal(d.requestSignalAttribution?.records.length ?? 0, 0); privateFree(d);
  }
});
test('signal diagnostics never consume or reorder the original failure-time native buffer', () => {
  const f = observer(); f.context(); f.message();
  f.send('Network.requestWillBeSent', {requestId: 'PRIVATE_NET', frameId: 'PRIVATE_FRAME', loaderId: 'PRIVATE_LOADER',
    request: {method: 'POST', url: back + '/matches/private/action'}});
  f.send('Network.loadingFailed', {requestId: 'PRIVATE_NET', canceled: true, errorText: 'net::ERR_ABORTED'});
  const d = f.result();
  assert.deepEqual(d.events.map(r => r.event), ['frame-navigated', 'request', 'failed']);
  assert.equal(d.omittedEvents, 0); assert.equal(d.events.at(-1).errorClass, 'net::ERR_ABORTED');
  assert.deepEqual(f.commands, []); assert.equal(d.requestSignalAttribution.records.length, 1);
});
test('signal record and context identity collections have independent finite16 caps', () => {
  const f = observer(); for (let i = 1; i <= 17; i++) f.context(i);
  for (let i = 1; i <= 17; i++) f.message(row({ordinal: Math.min(i, 16), atRecordCap: i >= 16}), 1);
  f.message(row(), 17); const d = f.result();
  assert.equal(d.requestSignalAttribution.records.length, 16);
  assert.equal(d.requestSignalAttribution.atRecordCap, true);
  assert.ok(d.requestSignalAttribution.contextOverflow >= 1); privateFree(d);
});
test('CI development builder opts in with the original pages plus the UI clarity fixture', async () => {
  const source = fs.readFileSync(new URL('./prepare-development-frontend.mjs', import.meta.url), 'utf8');
  const begin = source.indexOf('export function buildDevelopmentFrontend'), end = source.indexOf('\nif (process.argv[1]', begin);
  let config;
  const fn = vm.runInNewContext(source.slice(begin, end).replace('export ', '') + '\nbuildDevelopmentFrontend;', {
    process: {env: {NODE_ENV: 'development'}}, path, build: value => { config = value; return Promise.resolve(); }});
  await fn({root: '/unit-owned', configFile: '/unit-config', outDir: '/unit-out'});
  assert.equal(config.define?.['import.meta.env.VITE_REQUEST_SIGNAL_DIAGNOSTICS'], '"1"');
  assert.equal(config.mode, 'development'); assert.equal(config.build.target, 'es2022');
  assert.deepEqual({...config.build.rollupOptions.input}, {
    application: '/unit-owned/index.html', attackAll: '/unit-owned/tests/attack-all.html',
    humanActions: '/unit-owned/tests/human-actions.html',
    interactivePreflight: '/unit-owned/tests/interactive-preflight.html',
    simulationPreflight: '/unit-owned/tests/simulation-preflight.html',
    uiClarity: '/unit-owned/tests/ui-clarity.html',
    developmentProof: '/unit-owned/tests/fixtures/ci-development-runtime/probe.html',
  });
});
test('a context ID reused for a foreign origin invalidates its former signal ownership', () => {
  const f = observer(); f.context(); f.context(3, {origin: 'https://foreign.invalid'}); f.message();
  assert.equal(f.result().requestSignalAttribution?.records.length ?? 0, 0);
});
test('initially-aborted then finally-unaborted cannot be accepted as native signal evidence', () => {
  const f = observer(); f.context(); f.message(row({initialAborted: true}));
  assert.equal(f.result().requestSignalAttribution?.records.length ?? 0, 0);
});
test('new context-loss counters saturate and do not grow the retained native history', () => {
  const f = observer(); f.context(3);
  for (let i = 100; i < 70100; i++) f.context(i);
  f.message(); const d = f.result();
  assert.equal(d.requestSignalAttribution.contextOverflow, 65535);
  assert.equal(d.events.length, 1);
});
test('a throwing URL conversion is not attributed to fetch when fetch was never invoked', async () => {
  const error = new TypeError(privateValue); let fetchCalls = 0;
  const f = client({fetch: async () => { fetchCalls++; throw new Error('Unexpected fetch'); }});
  await assert.rejects(f.request({toString() { throw error; }}), e => e === error);
  assert.equal(fetchCalls, 0); assert.deepEqual(f.logs, []);
});
test('throwing init.signal getters are not attributed to fetch before argument construction finishes', async () => {
  for (const throwOnRead of [1, 2]) {
    const error = new TypeError(privateValue); let fetchCalls = 0, signalReads = 0;
    const signal = AbortSignal.timeout(30000);
    const f = client({fetch: async () => { fetchCalls++; throw new Error('Unexpected fetch'); }});
    await assert.rejects(f.request('/matches/start', {get signal() {
      if (++signalReads === throwOnRead) throw error;
      return signal;
    }}), e => e === error);
    assert.equal(fetchCalls, 0); assert.equal(signalReads, throwOnRead); assert.deepEqual(f.logs, []);
  }
});

// Protocol controls only: use the old real collector for RED, not a missing export.
import * as signalDiagnostics from './browser-start-recovery-diagnostics.mjs';
const v2Source = fs.readFileSync(new URL('./browser-ui-v2.mjs', import.meta.url), 'utf8');
function sharedSignals() {
  if (signalDiagnostics.createRequestSignalObserver) return signalDiagnostics.createRequestSignalObserver(front, back);
  let value;
  const old = traceStartRecoveryResponses(async () => {}, async () => {}, front, next => { value = next; }, {backend: back});
  return {observe: old.observeBrowserEvent, snapshot() { old.reportFailure(); return value.browserMetadata.requestSignalAttribution; }};
}
function sharedFixture() {
  const shared = sharedSignals();
  const send = (method, params) => shared.observe({method, params});
  const context = (id = 3, changes = {}) => send('Runtime.executionContextCreated', {context: {
    id, origin: front, auxData: {isDefault: true, frameId: 'PRIVATE_FRAME'}, ...changes}});
  const message = (value = row(), id = 3) => send('Runtime.consoleAPICalled', {type: 'debug', executionContextId: id,
    args: [{type: 'string', value: tag}, {type: 'string', value: JSON.stringify(value)}], stackTrace: privateValue});
  send('Page.frameNavigated', {frame: {id: 'PRIVATE_FRAME', loaderId: 'PRIVATE_LOADER'}});
  const late = () => { let report; const trace = traceStartRecoveryResponses(async () => {}, async () => {}, front,
    next => { report = next; }, {backend: back, requestSignals: shared}); return {trace, result() { trace.reportFailure(); return report.browserMetadata; }}; };
  return {shared, send, context, message, late};
}
function v2Startup() {
  const marker = '\ntry {\n', start = v2Source.indexOf(marker) + marker.length;
  const end = v2Source.indexOf('  await viewport();', start);
  assert.ok(start >= marker.length && end >= start);
  return v2Source.slice(start, end);
}
test('V2 installs passive signal ownership before original setup and enables only Page/Runtime observations', async () => {
  const calls = []; let handler;
  const env = {origin: front, api: back, recoverDroppedResponse() {},
    createRequestSignalObserver: sharedSignals,
    b: {onIntercept(value) { calls.push('attach'); handler = value; }},
    command: async name => { calls.push(name); assert.equal(typeof handler?.observeBrowserEvent, 'function'); }};
  await vm.runInNewContext('(async()=>{' + v2Startup() + '})()', env);
  assert.deepEqual(calls, ['attach', 'Page.enable', 'Runtime.enable']);
  assert.doesNotMatch(v2Startup(), /Fetch\.|reload|fetch\(|setTimeout/);
});
test('current context learned before interception remains attributable in the later failure trace', () => {
  const f = sharedFixture(); f.context(); const late = f.late(); f.message();
  const value = late.result().requestSignalAttribution;
  assert.equal(value?.records.length, 1); assert.equal(value.records[0].signalAborted, false); privateFree(value);
});
test('shared observation still rejects foreign and nondefault contexts', () => {
  for (const changes of [{origin: 'https://foreign.invalid'}, {auxData: {isDefault: false, frameId: 'PRIVATE_FRAME'}}]) {
    const f = sharedFixture(); f.context(3, changes); const late = f.late(); f.message();
    assert.equal(late.result().requestSignalAttribution?.records.length ?? 0, 0);
  }
});
test('a destroyed shared context cannot attribute a later console record', () => {
  const f = sharedFixture(); f.context(); f.send('Runtime.executionContextDestroyed', {executionContextId: 3});
  const late = f.late(); f.message(); assert.equal(late.result().requestSignalAttribution?.records.length ?? 0, 0);
});
test('duplicate shared context identity is invalidated rather than silently reused', () => {
  const f = sharedFixture(); f.context(); f.context(); const late = f.late(); f.message();
  assert.equal(late.result().requestSignalAttribution?.records.length ?? 0, 0);
});
test('clearing shared contexts refuses stale ownership and accepts a genuinely new context', () => {
  const f = sharedFixture(); f.context(); f.send('Runtime.executionContextsCleared', {});
  const late = f.late(); f.message(); f.context(4); f.message(row(), 4);
  const value = late.result().requestSignalAttribution; assert.equal(value?.records.length, 1); assert.equal(value.unknownContext, 1);
});
test('shared current context still needs a genuinely observed matching frame', () => {
  const f = sharedFixture(); f.context(3, {auxData: {isDefault: true, frameId: 'PRIVATE_UNOBSERVED_FRAME'}});
  const late = f.late(); f.message(); assert.equal(late.result().requestSignalAttribution?.records.length ?? 0, 0);
});
test('shared malformed and oversized records are rejected by the existing typed codec', () => {
  const f = sharedFixture(); f.context(); const late = f.late();
  f.message(row({raw: privateValue})); f.message(row({route: privateValue.repeat(100)}));
  const value = late.result().requestSignalAttribution; assert.equal(value?.records.length ?? 0, 0);
  privateFree(late.result());
});
test('shared observer retains the same finite16 record and context limits', () => {
  const f = sharedFixture(); for (let i = 1; i <= 17; i++) f.context(i);
  const late = f.late(); for (let i = 1; i <= 16; i++) f.message(row({ordinal: i, atRecordCap: i === 16}), 1);
  f.message(row(), 17); const value = late.result().requestSignalAttribution;
  assert.equal(value?.records.length, 16); assert.equal(value.atRecordCap, true); assert.equal(value.contextOverflow, 1);
});
test('a shared signal snapshot cannot leak a mutable record back into the private collector', () => {
  const f = sharedFixture(); f.context(); f.message(); const first = f.late().result().requestSignalAttribution;
  assert.equal(first?.records.length, 1); first.records[0].route = 'other';
  assert.equal(f.late().result().requestSignalAttribution.records[0].route, 'action');
});
test('shared context forwarding does not consume or reorder the original native failure history', () => {
  const f = sharedFixture(); f.context(); const late = f.late();
  const send = (method, params) => late.trace.observeBrowserEvent({method, params});
  send('Network.requestWillBeSent', {requestId: 'PRIVATE_NET', request: {method: 'POST', url: back + '/matches/private/action'}});
  send('Runtime.consoleAPICalled', {type: 'debug', executionContextId: 3,
    args: [{type: 'string', value: tag}, {type: 'string', value: JSON.stringify(row())}]});
  send('Network.loadingFailed', {requestId: 'PRIVATE_NET', canceled: true, errorText: 'net::ERR_ABORTED'});
  const value = late.result(); assert.deepEqual(value.events.map(x => x.event), ['request', 'failed']);
  assert.equal(value.requestSignalAttribution?.records.length, 1); assert.equal(value.omittedEvents, 0); privateFree(value);
});
test('observational startup rejection uses the original finally close and preserves the same error', async () => {
  const error = new Error(privateValue); let closed = 0, startedOriginal = 0;
  const env = {origin: front, api: back, recoverDroppedResponse() {}, createRequestSignalObserver: sharedSignals,
    b: {onIntercept() {}, async close() { closed++; }}, command: async name => { if (name === 'Runtime.enable') throw error; },
    viewport: async () => { startedOriginal++; }};
  const cleanup = v2Source.slice(v2Source.lastIndexOf('} finally { await b.close(); }'));
  await assert.rejects(vm.runInNewContext('(async()=>{try {' + v2Startup() + 'await viewport();' + cleanup + '})()', env), value => value === error);
  assert.equal(closed, 1); assert.equal(startedOriginal, 0);
});

test('OPTIONS and HTTP200 do not imply a native preflight classification', () => {
  const f = observer();
  f.send('Network.requestWillBeSent', {requestId: 'PRIVATE_OPTIONS', type: 'XHR', initiator: {type: 'other'},
    request: {method: 'OPTIONS', url: back + '/matches/private/action'}});
  f.send('Network.responseReceived', {requestId: 'PRIVATE_OPTIONS', response: {status: 200}});
  const rows = f.result().events.filter(value => value.networkOrdinal);
  assert.deepEqual(rows.map(value => [value.networkType, value.initiatorType]), [['XHR', 'other'], ['XHR', 'other']]);
  assert.equal(rows[1].status, 200); assert.equal(Object.hasOwn(rows[0], 'preflight'), false);
  privateFree(rows); assert.deepEqual(f.commands, []);
});

test('native Preflight and initiator metadata retain their actual triggering request-ID link', () => {
  const f = observer();
  f.send('Network.requestWillBeSent', {requestId: 'PRIVATE_PARENT', type: 'Fetch', initiator: {type: 'script'},
    request: {method: 'POST', url: back + '/matches/private/action'}});
  f.send('Network.requestWillBeSent', {requestId: 'PRIVATE_PREFLIGHT', type: 'Preflight',
    initiator: {type: 'preflight', requestId: 'PRIVATE_PARENT', stack: privateValue},
    request: {method: 'OPTIONS', url: back + '/matches/private/action'}});
  const rows = f.result().events.filter(value => value.event === 'request');
  assert.equal(rows[1].networkType, 'Preflight'); assert.equal(rows[1].initiatorType, 'preflight');
  assert.equal(rows[1].initiatorNetworkOrdinal, rows[0].networkOrdinal);
  assert.notEqual(rows[1].networkOrdinal, rows[0].networkOrdinal); privateFree(f.result());
});

test('missing and unknown Network categories stay null or finite other without leaking values', () => {
  const f = observer();
  for (const [requestId, fields] of [['PRIVATE_MISSING', {}], ['PRIVATE_UNKNOWN',
    {type: privateValue, initiator: {type: privateValue}}]]) {
    f.send('Network.requestWillBeSent', {requestId, ...fields,
      request: {method: 'POST', url: back + '/matches/private/action'}});
  }
  const d = f.result(), rows = d.events.filter(value => value.event === 'request');
  assert.deepEqual(rows.map(value => [value.networkType, value.initiatorType]), [[null, null], ['other', 'other']]);
  assert.equal(d.unknownCategories, 2); privateFree(d);
});

test('Network initiator correlation uses native request IDs, never coincident ordinals', () => {
  const f = observer();
  f.send('Network.requestWillBeSent', {requestId: 'PRIVATE_FIRST', type: 'Fetch', initiator: {type: 'script'},
    request: {method: 'POST', url: back + '/matches/private/action'}});
  f.send('Network.requestWillBeSent', {requestId: 'PRIVATE_SECOND', type: 'Preflight',
    initiator: {type: 'preflight', requestId: 'PRIVATE_UNOBSERVED'},
    request: {method: 'OPTIONS', url: back + '/matches/private/action'}});
  const d = f.result(), rows = d.events.filter(value => value.event === 'request');
  assert.equal(rows[1].initiatorType, 'preflight'); assert.equal(rows[1].initiatorNetworkOrdinal, 3);
  assert.notEqual(rows[1].initiatorNetworkOrdinal, rows[0].networkOrdinal);
  assert.equal(d.unmatchedInitiators, 1); privateFree(d);
});

test('an acknowledged error response pause is not an HTTP success or signal-abort certificate', async () => {
  let report; const commands = [];
  const trace = traceStartRecoveryResponses(async (...args) => { commands.push(args); },
    async (event, command) => command('Fetch.continueResponse', {requestId: event.requestId}), front,
    value => { report = value; }, {backend: back});
  trace.observeBrowserEvent({method: 'Network.requestWillBeSent', params: {requestId: 'PRIVATE_NET', type: 'Fetch',
    initiator: {type: 'script'}, request: {method: 'POST', url: back + '/matches/private/action'}}});
  await trace({requestId: 'PRIVATE_PAUSE', networkId: 'PRIVATE_NET', resourceType: 'Fetch',
    request: {method: 'POST'}, responseErrorReason: 'Aborted'});
  trace.observeBrowserEvent({method: 'Network.loadingFailed', params: {requestId: 'PRIVATE_NET',
    canceled: true, errorText: 'net::ERR_ABORTED'}});
  trace.reportFailure();
  assert.equal(report.responses[0].status, null); assert.equal(report.responses[0].responseError, 'Aborted');
  assert.equal(report.responses[0].commands[0].acknowledgment, 'accepted');
  assert.equal(report.browserMetadata.events.at(-1).canceled, true);
  assert.equal(Object.hasOwn(report.browserMetadata, 'requestSignalAttribution'), false);
  assert.equal(commands.length, 1); privateFree(report);
});
