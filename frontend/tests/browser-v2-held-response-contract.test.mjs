import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import vm from 'node:vm';
import {traceStartRecoveryResponses} from './browser-start-recovery-diagnostics.mjs';
import * as diagnostics from './browser-start-recovery-diagnostics.mjs';

const source = readFileSync(new URL('./browser-ui-v2-costs.mjs', import.meta.url), 'utf8');
const begin = source.indexOf(' b.onIntercept(');
const end = source.indexOf("\n await b.command('Fetch.enable'", begin);
assert.ok(begin >= 0 && end > begin, 'Actual held-response callback must be present');
const frontend = 'http://127.0.0.1:15173';
const event = changes => ({requestId: 'PRIVATE_FETCH', networkId: 'PRIVATE_NETWORK', resourceType: 'Preflight',
  responseStatusCode: 200, request: {method: 'OPTIONS', postData: 'PRIVATE_BODY', headers: {Authorization: 'PRIVATE_KEY'}},
  responseHeaders: [{name: 'Access-Control-Allow-Origin', value: frontend}], ...changes});

function fixture(command = async () => ({})) {
  const reports = [], calls = [];
  let callback;
  const context = {ui: frontend, traceStartRecoveryResponses, continueRequestForPostResponse: diagnostics.continueRequestForPostResponse,
    b: {async command(...args) { calls.push(args); return command(...args); }, onIntercept(fn) { callback = fn; }},
    console: {error(label, value) { reports.push({label, value: JSON.parse(value)}); }}};
  vm.runInNewContext(`let held, continueHeld;\n${source.slice(begin, end)}\nglobalThis.heldResponse = () => held; globalThis.resumeHeld = () => continueHeld();`, context);
  return {calls, reports, invoke: value => callback(value), held: () => context.heldResponse(), resume: () => context.resumeHeld()};
}

test('actual cost callback still holds the real POST response without auto-continuing', async () => {
  const f = fixture(), post = event({request: {method: 'POST'}});
  await f.invoke(post);
  assert.equal(f.held(), post);
  assert.deepEqual(f.calls, []);
  assert.deepEqual(f.reports, []);
});

test('actual cost callback continues successful CORS preflight exactly once', async () => {
  const f = fixture(), options = event();
  await f.invoke(options);
  assert.equal(f.calls.length, 1);
  assert.equal(f.calls[0][0], 'Fetch.continueResponse');
  assert.deepEqual(Object.keys(f.calls[0][1]), ['requestId']);
  assert.equal(f.calls[0][1].requestId, options.requestId);
  assert.equal(f.held(), undefined);
  assert.deepEqual(f.reports, []);
});

test('actual cost callback reports failed continuation without changing its failure', async () => {
  const error = new Error('{"code":-32602,"message":"PRIVATE_REASON"}');
  const f = fixture(async () => { throw error; });
  await assert.rejects(f.invoke(event()), actual => actual === error);
  assert.equal(f.reports.length, 1);
  assert.equal(f.reports[0].label, 'V2_HELD_RESPONSE_TRACE');
  assert.equal(f.reports[0].value.responses[0].commands[0].errorCode, -32602);
  assert.equal(JSON.stringify(f.reports).includes('PRIVATE_'), false);
});

test('actual cost callback correlates response/error pauses and retains genuine ACK order', async () => {
  let call = 0;
  const f = fixture(async () => { if (++call === 2) throw Error('{"code":-32602}'); });
  await f.invoke(event());
  await assert.rejects(f.invoke(event({responseStatusCode: undefined, responseErrorReason: 'Failed'})));
  assert.equal(f.reports.length, 1);
  const [first, second] = f.reports[0].value.responses;
  assert.equal(first.requestOrdinal, second.requestOrdinal);
  assert.equal(first.networkOrdinal, second.networkOrdinal);
  assert.equal(first.commands[0].acknowledgment, 'accepted');
  assert.equal(second.commands[0].acknowledgment, 'error');
  assert.equal(second.responseError, 'Failed');
});

test('actual held POST is continued exactly once by the later explicit release', async () => {
  const f = fixture(), post = event({resourceType: 'Fetch', request: {method: 'POST'}});
  await f.invoke(post);
  assert.deepEqual(f.calls, []);
  await f.resume();
  assert.equal(f.calls.length, 1);
  assert.equal(f.calls[0][0], 'Fetch.continueResponse');
  assert.equal(f.calls[0][1].requestId, post.requestId);
  assert.deepEqual(f.reports, []);
  assert.ok(source.includes("await continueHeld();await b.command('Fetch.disable');"), 'Actual program must use the observed explicit release');
});

test('actual deferred POST release failure is observed without changing its error', async () => {
  const error = new Error('{"code":-32602,"message":"PRIVATE_REASON"}');
  const f = fixture(async () => { throw error; });
  await f.invoke(event({resourceType: 'Fetch', request: {method: 'POST'}}));
  await assert.rejects(f.resume(), actual => actual === error);
  assert.equal(f.reports.length, 1);
  assert.equal(f.reports[0].label, 'V2_HELD_RESPONSE_TRACE');
  assert.equal(f.reports[0].value.responses[0].method, 'POST');
  assert.equal(f.reports[0].value.responses[0].commands[0].errorCode, -32602);
  assert.equal(JSON.stringify(f.reports).includes('PRIVATE_'), false);
});

function requestPause(method) {
  const input = event({resourceType: 'XHR', request: {method}});
  delete input.responseStatusCode;
  return input;
}

test('actual OPTIONS XHR request bypasses response interception and never becomes a held POST', async () => {
  const f = fixture();
  await f.invoke(requestPause('OPTIONS'));
  assert.deepEqual(JSON.parse(JSON.stringify(f.calls)), [['Fetch.continueRequest', {requestId: 'PRIVATE_FETCH', interceptResponse: false}]]);
  assert.equal(f.held(), undefined);
  assert.deepEqual(f.reports, []);
});

test('actual POST request only opts in, then its response waits for the same explicit release', async () => {
  const f = fixture(), post = event({resourceType: 'XHR', request: {method: 'POST'}});
  await f.invoke(requestPause('POST'));
  assert.deepEqual(JSON.parse(JSON.stringify(f.calls)), [['Fetch.continueRequest', {requestId: 'PRIVATE_FETCH', interceptResponse: true}]]);
  assert.equal(f.held(), undefined);
  await f.invoke(post);
  assert.equal(f.held(), post);
  assert.equal(f.calls.length, 1);
  await f.resume();
  assert.equal(f.calls.length, 2);
  assert.equal(f.calls[1][0], 'Fetch.continueResponse');
  assert.equal(f.calls[1][1].requestId, post.requestId);
});

test('held-response request continuation rejection is observed and never creates a held response', async () => {
  const error = new Error('{"code":-32602,"message":"PRIVATE_REASON"}');
  const f = fixture(async () => { throw error; });
  await assert.rejects(f.invoke(requestPause('POST')), actual => actual === error);
  assert.equal(f.held(), undefined);
  assert.equal(f.reports.length, 1);
  assert.equal(f.reports[0].value.responses[0].commands[0].method, 'Fetch.continueRequest');
  assert.equal(f.reports[0].value.responses[0].commands[0].errorCode, -32602);
});

test('held-response handler rejects unexpected request methods instead of treating them as preflight', async () => {
  const f = fixture();
  await assert.rejects(f.invoke(requestPause('GET')));
  assert.deepEqual(f.calls, []);
  assert.equal(f.held(), undefined);
  assert.equal(f.reports.length, 1);
});

test('actual held-response enable captures request stage at the unchanged endpoint', async () => {
  const calls = [];
  const start = source.indexOf(" await b.command('Fetch.enable'", begin);
  const stop = source.indexOf('\n', start + 1);
  await vm.runInNewContext(`(async()=>{${source.slice(start, stop)}})()`, {b: {command: async (...args) => calls.push(args)}});
  assert.deepEqual(JSON.parse(JSON.stringify(calls)), [['Fetch.enable', {patterns: [{urlPattern: '*/matches/*/action', requestStage: 'Request'}]}]]);
});
