import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import * as diagnostics from './browser-start-recovery-diagnostics.mjs';

const source = readFileSync(new URL('./browser-start-recovery.mjs', import.meta.url), 'utf8');
const selectStart = source.indexOf('async function selectDecks()');
const selectEnd = source.indexOf('\nasync function matchIds()', selectStart);
const functionsStart = source.indexOf('async function startWithDroppedResponses(');
const startupStart = source.indexOf('\ntry {', functionsStart) + '\ntry {'.length;
const startupEnd = source.indexOf('  const before = await matchIds();', startupStart);
assert.ok(selectStart >= 0 && selectEnd > selectStart && functionsStart > selectEnd
  && startupStart > functionsStart && startupEnd > startupStart);
const front = 'http://fixture.invalid', back = 'http://api.invalid';
const secret = 'PRIVATE_CONTEXT_FRAME_LOADER';
const row = (ordinal = 1) => ({phase: 'fetch-rejected', ordinal, route: 'start', method: 'POST',
  elapsedMs: 12, signalAvailable: true, initialAborted: false, signalAborted: false,
  signalReasonClass: null, errorClass: 'TypeError', atRecordCap: ordinal === 16});

async function fixture({commandError} = {}) {
  const calls = [], reports = [], handlers = [];
  let handler;
  const send = (method, params) => handler?.observeBrowserEvent?.({method, params});
  function context(id = 7, changes = {}) {
    send('Runtime.executionContextCreated', {context: {id, origin: front,
      auxData: {isDefault: true, frameId: secret}, ...changes}});
  }
  const frame = () => send('Page.frameNavigated', {frame: {id: secret, loaderId: secret}});
  const signal = (ordinal = 1, id = 7) => send('Runtime.consoleAPICalled', {type: 'debug', executionContextId: id,
    args: [{type: 'string', value: 'MTG_REQUEST_SIGNAL_DIAGNOSTIC'}, {type: 'string', value: JSON.stringify(row(ordinal))}]});
  const command = async (method, params) => {
    calls.push([method, params]);
    if (method === commandError?.method) throw commandError.error;
    if (method === 'Runtime.enable') context(1);
    if (method === 'Page.reload') {
      send('Runtime.executionContextsCleared', {});
      frame();
      context();
    }
    return {};
  };
  const env = {assert, Buffer, URL, browser: {}, backend: back, decks: {a: 1, b: 2}, command,
    process: {env: {MTG_FRONTEND_ORIGIN: front}},
    evaluate: async () => {}, waitFor: async () => {}, reviewStart: async () => {},
    click: async label => calls.push(['click', label]),
    onIntercept: next => {calls.push(['attach']); handlers.push(next); handler = next;},
    console: {log() {}}, ...diagnostics,
    traceStartRecoveryResponses: (sendCommand, callback, origin, report, options) =>
      diagnostics.traceStartRecoveryResponses(sendCommand, callback, origin, value => reports.push(value), options)};
  vm.runInNewContext(source.slice(selectStart, selectEnd) + '\n' + source.slice(functionsStart, startupStart - '\ntry {'.length)
    + '\nglobalThis.start = startWithDroppedResponses; globalThis.control = typeof observeFetchControl === "function" ? observeFetchControl : undefined;', env);
  await vm.runInNewContext('(async () => {' + source.slice(startupStart, startupEnd) + '})()', env);
  const late = async () => {await env.start(1); return handler;};
  const snapshot = () => {handler.reportFailure(); return reports.at(-1).browserMetadata.requestSignalAttribution;};
  return {calls, reports, handlers, send, context, frame, signal, late, snapshot, control: env.control};
}

test('actual recovery observes OPTIONS continuation and unjoined POST failures without inventing POST pauses', async () => {
  const f = await fixture();
  const trace = await f.late();
  const event = {requestId: secret, networkId: secret, resourceType: 'XHR',
    request: {method: 'OPTIONS', url: back + '/matches/start'}};
  trace.observeBrowserEvent({method: 'Fetch.requestPaused', params: event}, {protocol: 'cdp', targetId: secret});
  await trace(event);
  for (let i = 1; i <= 2; i++) {
    f.send('Network.requestWillBeSent', {requestId: secret + i,
      request: {method: 'POST', url: back + '/matches/start'}, type: 'Fetch',
      frameId: secret, loaderId: secret, initiator: {type: 'script'}});
    f.send('Network.loadingFailed', {requestId: secret + i, type: 'Fetch',
      errorText: 'net::ERR_ABORTED', canceled: true});
    f.signal(i);
  }
  trace.reportFailure();
  const report = f.reports.at(-1);
  assert.ok(report.causal, 'The actual recovery caller must enable the existing causal collector');
  assert.deepEqual(report.responses.map(row => row.method), ['OPTIONS']);
  const events = report.browserMetadata.events;
  assert.equal(events.filter(row => row.event === 'fetch-pause').length, 1);
  assert.equal(events.filter(row => row.event === 'failed').length, 2);
  assert.equal(events.filter(row => row.event === 'fetch-callback-end').length, 1);
  assert.equal(report.pendingCommands, 0);
  assert.equal(report.activeCallbacks, 0);
  assert.equal(report.browserMetadata.requestSignalAttribution.correlation, 'not-joined-to-native-network-id');
  assert.equal(JSON.stringify(report).includes(secret), false);
});

test('actual recovery Fetch controls record sends and ACKs without changing native commands or errors', async () => {
  const f = await fixture();
  const trace = await f.late();
  assert.equal(typeof f.control, 'function', 'The actual caller must observe its Fetch control boundaries');
  await f.control('Fetch.disable');
  trace.reportFailure();
  const controls = f.reports.at(-1).browserMetadata.events.filter(row => row.event === 'fetch-control');
  assert.deepEqual(controls.map(row => [row.method, row.acknowledgment]), [
    ['Fetch.enable', 'sent'], ['Fetch.enable', 'accepted'],
    ['Fetch.disable', 'sent'], ['Fetch.disable', 'accepted'],
  ]);
  assert.deepEqual(structuredClone(f.calls.filter(([method]) => method.startsWith('Fetch.'))), [
    ['Fetch.enable', {patterns: [{urlPattern: '*/matches/start', requestStage: 'Request'}]}],
    ['Fetch.disable', undefined],
  ]);
  const primary = new Error('PRIVATE_NATIVE_ERROR');
  const rejected = await fixture({commandError: {method: 'Fetch.enable', error: primary}});
  await assert.rejects(rejected.late(), error => error === primary);
  rejected.handlers.at(-1).reportFailure();
  assert.deepEqual(rejected.reports.at(-1).browserMetadata.events
    .filter(row => row.event === 'fetch-control').map(row => row.acknowledgment), ['sent']);
});

test('all nine actual recovery Fetch control sites use the passive boundary observer', () => {
  const sites = [...source.matchAll(/await (command|observeFetchControl)\('Fetch\.(enable|disable)'/g)];
  assert.equal(sites.length, 9, 'Retain the complete original control-site inventory');
  assert.ok(sites.every(site => site[1] === 'observeFetchControl'), 'Legacy recovery controls must not bypass observation');
});

test('actual startup attaches the passive observer before original domains and deck reload', async () => {
  const f = await fixture();
  assert.deepEqual(f.calls.map(([method]) => method), ['attach', 'Network.enable', 'Page.enable', 'Runtime.enable', 'Page.reload']);
  assert.equal(typeof f.handlers[0].observeBrowserEvent, 'function');
  assert.equal(f.calls.some(([method]) => method.startsWith('Fetch.')), false);
});

test('context created before Fetch interception remains attributable after actual registration', async () => {
  const f = await fixture();
  await f.late();
  f.signal();
  const value = f.snapshot();
  assert.equal(value?.records.length, 1);
  assert.equal(value.unknownContext, 0);
  assert.equal(value.records[0].signalAborted, false);
  assert.equal(value.correlation, 'not-joined-to-native-network-id');
  assert.equal(JSON.stringify(value).includes(secret), false);
});

test('replacing the trace across starts preserves the same real context without duplicate intake', async () => {
  const f = await fixture();
  for (let ordinal = 1; ordinal <= 3; ordinal++) {
    await f.late();
    f.signal(ordinal);
    const value = f.snapshot();
    assert.equal(value?.records.length, ordinal);
    assert.deepEqual(value.records.map(record => record.diagnosticOrdinal), Array.from({length: ordinal}, (_, i) => i + 1));
    assert.equal(value.unknownContext, 0);
  }
});

test('real context clearing retires old ownership and admits only a newly observed context', async () => {
  const f = await fixture();
  await f.late();
  f.send('Runtime.executionContextsCleared', {});
  f.signal();
  f.context(8);
  f.signal(1, 8);
  const value = f.snapshot();
  assert.equal(value?.records.length, 1);
  assert.equal(value.unknownContext, 1);
});

test('early enrollment still refuses foreign, nondefault and unobserved-frame contexts', async () => {
  for (const change of [{origin: 'https://foreign.invalid'}, {auxData: {isDefault: false, frameId: secret}},
    {auxData: {isDefault: true, frameId: 'PRIVATE_UNOBSERVED'}}]) {
    const f = await fixture();
    f.context(8, change);
    await f.late();
    f.signal(1, 8);
    assert.equal(f.snapshot()?.records.length ?? 0, 0);
  }
});

test('destroying or detaching the early owned context does not admit its later signal', async () => {
  for (const [method, params] of [['Runtime.executionContextDestroyed', {executionContextId: 7}],
    ['Page.frameDetached', {frameId: secret, reason: 'remove'}]]) {
    const f = await fixture();
    f.send(method, params);
    await f.late();
    f.signal();
    assert.equal(f.snapshot()?.records.length ?? 0, 0);
  }
});

test('late real handler preserves continuation arguments and the original command error identity', async () => {
  const error = new Error('{"code":-32602,"message":"PRIVATE_NATIVE_ERROR"}');
  const f = await fixture({commandError: {method: 'Fetch.continueResponse', error}});
  const handler = await f.late();
  await assert.rejects(handler({requestId: secret, request: {method: 'OPTIONS'}, responseStatusCode: 200}), actual => actual === error);
  const last = f.calls.at(-1);
  assert.equal(last[0], 'Fetch.continueResponse');
  assert.equal(last[1].requestId, secret);
  assert.equal(f.reports.length, 1);
  assert.equal(JSON.stringify(f.reports).includes('PRIVATE_'), false);
});
