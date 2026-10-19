import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import vm from 'node:vm';
import * as diagnostics from './browser-start-recovery-diagnostics.mjs';

const source = readFileSync(new URL('./browser-start-recovery.mjs', import.meta.url), 'utf8');
const start = source.indexOf('async function startWithDroppedResponses(');
const end = source.indexOf('\ntry {', start);
assert.ok(start >= 0 && end > start, 'Exercise actual start, retry-intent and resume functions without app startup');
const backend = 'http://fixture.invalid', key = '0123456789abcdef0123456789abcdef';
const payload = {deck_a: 1, deck_b: 2, mode: 'human_vs_human'};
const body = JSON.stringify(payload);

async function fixture(dropCount = 1, {base64Encoded = false, inlineBody = true, rejectCommand} = {}) {
  const calls = [], logs = [], reports = [];
  let callback;
  const command = async (method, params) => {
    calls.push([method, params]);
    if (method === rejectCommand?.method) throw rejectCommand.error;
    if (method === 'Network.getRequestPostData') return {postData: base64Encoded ? Buffer.from(body).toString('base64') : body, base64Encoded};
    return {};
  };
  const context = {assert, Buffer, URL, backend, command, ...diagnostics,
    traceStartRecoveryResponses: (send, handler, frontend) => diagnostics.traceStartRecoveryResponses(send, handler, frontend,
      value => reports.push(['START_RECOVERY_RESPONSE_TRACE', JSON.stringify(value)])),
    process: {env: {}}, browser: {}, reviewStart: async () => {},
    click: async label => assert.equal(label, 'Start Best-of-3 Match'),
    onIntercept: fn => { callback = fn; },
    console: {log: (...args) => logs.push(args), error: (...args) => reports.push(args)}};
  vm.runInNewContext(`${source.slice(start, end)}\nglobalThis.start = startWithDroppedResponses; globalThis.resume = resumeRequestCapture; globalThis.same = sameIntent;`, context);
  const dropped = await context.start(dropCount);
  function pause(method, response = false, changes = {}) {
    return {requestId: 'PRIVATE_FETCH', networkId: 'PRIVATE_NETWORK', resourceType: 'XHR',
      request: {method, url: `${backend}/matches/start`, headers: {'Idempotency-Key': key}, ...(inlineBody ? {postData: body} : {})},
      ...(response ? {responseStatusCode: 200} : {}), ...changes};
  }
  return {calls, logs, reports, dropped, pause, invoke: input => callback(input), resume: () => context.resume(),
    same: pending => context.same(dropped.attempts, pending)};
}

const plain = value => JSON.parse(JSON.stringify(value));

test('actual start OPTIONS XHR request continues unmodified with no POST body read, attempt or drop', async () => {
  const f = await fixture();
  await f.invoke(f.pause('OPTIONS'));
  assert.deepEqual(plain(f.calls), [
    ['Fetch.enable', {patterns: [{urlPattern: '*/matches/start', requestStage: 'Request'}]}],
    ['Fetch.continueRequest', {requestId: 'PRIVATE_FETCH', interceptResponse: false}],
  ]);
  assert.equal(f.dropped(), 0);
  assert.equal(f.dropped.attempts.length, 0);
  assert.deepEqual(f.logs, []);
});

test('actual start POST request only opts into interception and cannot count as an accepted response', async () => {
  const f = await fixture();
  await f.invoke(f.pause('POST'));
  assert.deepEqual(plain(f.calls.slice(1)), [['Fetch.continueRequest', {requestId: 'PRIVATE_FETCH', interceptResponse: true}]]);
  assert.equal(f.dropped(), 0);
  assert.equal(f.dropped.attempts.length, 0);
  assert.deepEqual(f.logs, []);
});

for (const base64Encoded of [false, true]) {
  test(`actual accepted POST response uses Network body and original key/payload through drop, retry and resume (base64=${base64Encoded})`, async () => {
    const f = await fixture(2, {base64Encoded, inlineBody: !base64Encoded});
    for (let n = 0; n < 3; n++) {
      await f.invoke(f.pause('OPTIONS'));
      await f.invoke(f.pause('POST'));
      assert.equal(f.dropped.attempts.length, n);
      await f.invoke(f.pause('POST', true));
      if (n === 1) await f.resume();
    }
    assert.equal(f.dropped(), 2);
    assert.deepEqual(plain(f.dropped.attempts), Array.from({length:3}, () => ({key, payload})));
    f.same({key, payload: f.dropped.attempts[0].payload});
    assert.deepEqual(plain(f.calls.filter(([name]) => name === 'Network.getRequestPostData')),
      Array.from({length:3}, () => ['Network.getRequestPostData', {requestId: 'PRIVATE_NETWORK'}]));
    assert.equal(f.calls.filter(([name]) => name === 'Fetch.failRequest').length, 2);
    assert.deepEqual(plain(f.calls.filter(([name]) => name === 'Fetch.continueResponse')),
      [['Fetch.continueResponse', {requestId: 'PRIVATE_FETCH'}]]);
    assert.deepEqual(f.reports, []);
  });
}

test('actual positive CORS response branch remains distinct from request-stage bypass', async () => {
  const f = await fixture();
  await f.invoke(f.pause('OPTIONS', true));
  assert.deepEqual(plain(f.calls.slice(1)), [['Fetch.continueResponse', {requestId: 'PRIVATE_FETCH'}]]);
  assert.equal(f.dropped.attempts.length, 0);
  assert.equal(f.dropped(), 0);
});

test('actual nonaccepted POST response is captured but not dropped', async () => {
  const f = await fixture();
  await f.invoke(f.pause('POST', true, {responseStatusCode: 503}));
  assert.equal(f.dropped(), 0);
  assert.equal(f.dropped.attempts.length, 1);
  assert.deepEqual(plain(f.calls.slice(1)), [
    ['Network.getRequestPostData', {requestId: 'PRIVATE_NETWORK'}],
    ['Fetch.continueResponse', {requestId: 'PRIVATE_FETCH'}],
  ]);
});

test('actual resumeRequestCapture enables Request stage for POST response opt-in at the unchanged start endpoint', async () => {
  const f = await fixture();
  await f.resume();
  assert.deepEqual(plain(f.calls), Array.from({length:2}, () =>
    ['Fetch.enable', {patterns: [{urlPattern: '*/matches/start', requestStage: 'Request'}]}]));
});

test('actual start request continuation error is observed and is not an accepted POST attempt', async () => {
  const error = new Error('{"code":-32602,"message":"PRIVATE_FAILURE"}');
  const f = await fixture(1, {rejectCommand: {method: 'Fetch.continueRequest', error}});
  await assert.rejects(f.invoke(f.pause('POST')), actual => actual === error);
  assert.equal(f.dropped.attempts.length, 0);
  assert.equal(f.dropped(), 0);
  assert.equal(f.reports.length, 1);
  const report = JSON.parse(f.reports[0][1]);
  assert.deepEqual(report.responses[0].commands, [{method: 'Fetch.continueRequest', acknowledgment: 'error', errorCode: -32602}]);
  assert.equal(JSON.stringify(report).includes('PRIVATE_'), false);
});

test('actual start rejects unexpected request method without reading body or continuing', async () => {
  const f = await fixture();
  await assert.rejects(f.invoke(f.pause('GET')));
  assert.equal(f.calls.length, 1);
  assert.equal(f.dropped.attempts.length, 0);
  assert.equal(f.dropped(), 0);
  assert.equal(f.reports.length, 1);
});
