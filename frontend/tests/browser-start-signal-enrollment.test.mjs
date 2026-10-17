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
    + '\nglobalThis.start = startWithDroppedResponses;', env);
  await vm.runInNewContext('(async () => {' + source.slice(startupStart, startupEnd) + '})()', env);
  const late = async () => {await env.start(1); return handler;};
  const snapshot = () => {handler.reportFailure(); return reports.at(-1).browserMetadata.requestSignalAttribution;};
  return {calls, reports, handlers, send, context, frame, signal, late, snapshot};
}

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
