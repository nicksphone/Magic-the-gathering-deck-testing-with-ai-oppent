import assert from 'node:assert/strict';
import {test} from 'node:test';

const feature = await import('./browser-start-recovery-diagnostics.mjs').catch(error => {
  if (error.code === 'ERR_MODULE_NOT_FOUND' && error.message.includes('/browser-start-recovery-diagnostics.mjs')) return {};
  throw error;
});
const frontend = 'http://127.0.0.1:15173';
const event = (changes = {}) => ({requestId: 'private-fetch-id', networkId: 'private-network-id',
  resourceType: 'Preflight', responseStatusCode: 200,
  request: {method: 'OPTIONS', url: 'http://127.0.0.1:10199/matches/start',
    headers: {'Idempotency-Key': 'PRIVATE_KEY'}, postData: 'PRIVATE_BODY'},
  responseHeaders: [{name: 'Access-Control-Allow-Origin', value: frontend},
    {name: 'Access-Control-Allow-Headers', value: 'Content-Type, Idempotency-Key'}], ...changes});

function wrap(command, handler, report) {
  assert.equal(typeof feature.traceStartRecoveryResponses, 'function', 'Start-recovery diagnostics are absent');
  return feature.traceStartRecoveryResponses(command, handler, frontend, report);
}

test('successful interception preserves event, command arguments and result without failure output', async () => {
  const calls = [], reports = [], input = event();
  const original = {postData: 'PRIVATE_BODY'};
  const wrapped = wrap(async (...args) => { calls.push(args); return original; }, async (received, command) => {
    assert.equal(received, input);
    assert.equal(await command('Network.getRequestPostData', {requestId: input.networkId}, 'private-session'), original);
    return 42;
  }, report => reports.push(report));
  assert.equal(await wrapped(input), 42);
  assert.deepEqual(calls, [['Network.getRequestPostData', {requestId: input.networkId}, 'private-session']]);
  assert.deepEqual(reports, []);
});

test('failed continuation retains native error and records the actual command and code', async () => {
  const reports = [], error = new Error(JSON.stringify({code: -32602, message: 'PRIVATE_MESSAGE', data: 'PRIVATE_DATA'}));
  const wrapped = wrap(async () => { throw error; }, async (received, command) => {
    await command('Fetch.continueResponse', {requestId: received.requestId});
  }, report => reports.push(report));
  await assert.rejects(wrapped(event()), actual => actual === error);
  assert.equal(reports.length, 1);
  assert.deepEqual(reports[0].responses[0].commands, [{method: 'Fetch.continueResponse', acknowledgment: 'error', errorCode: -32602}]);
  assert.equal(JSON.stringify(reports).includes('PRIVATE_'), false);
  assert.equal(JSON.stringify(reports).includes('private-'), false);
});

test('same native IDs correlate repeated response and error pauses without exposing identifiers', async () => {
  const reports = [], error = new Error('failure');
  const wrapped = wrap(async () => {}, async (received, command) => {
    if (received.responseErrorReason) throw error;
    await command('Fetch.continueResponse', {requestId: received.requestId});
  }, report => reports.push(report));
  await wrapped(event());
  await assert.rejects(wrapped(event({responseStatusCode: undefined, responseErrorReason: 'Failed'})), actual => actual === error);
  const [first, second] = reports[0].responses;
  assert.equal(first.requestOrdinal, second.requestOrdinal);
  assert.equal(first.networkOrdinal, second.networkOrdinal);
  assert.deepEqual(first.commands, [{method: 'Fetch.continueResponse', acknowledgment: 'accepted', errorCode: null}]);
  assert.equal(second.responseError, 'Failed');
  assert.equal(second.status, null);
});

test('different native IDs remain distinguishable', async () => {
  const reports = [];
  const wrapped = wrap(async () => {}, async received => { if (received.responseErrorReason) throw Error('failure'); }, r => reports.push(r));
  await wrapped(event());
  await assert.rejects(wrapped(event({requestId: 'another-private-id', networkId: 'another-private-network', responseErrorReason: 'Failed'})));
  const [first, second] = reports[0].responses;
  assert.notEqual(first.requestOrdinal, second.requestOrdinal);
  assert.notEqual(first.networkOrdinal, second.networkOrdinal);
});

test('CORS projection records only categories and required-header booleans', async () => {
  const reports = [];
  const wrapped = wrap(async () => {}, async () => { throw Error('failure'); }, r => reports.push(r));
  await assert.rejects(wrapped(event()));
  assert.deepEqual(reports[0].responses[0].cors, {allowOrigin: 'expected', contentTypeAllowed: true, idempotencyKeyAllowed: true});
  const text = JSON.stringify(reports);
  assert.equal(text.includes(frontend), false);
  assert.equal(text.includes('/matches/start'), false);
});

test('unknown metadata and sensitive errors are reduced to fixed categories', async () => {
  const reports = [];
  const wrapped = wrap(async () => {}, async () => { throw Error('PRIVATE_EXCEPTION'); }, r => reports.push(r));
  await assert.rejects(wrapped(event({resourceType: 'PRIVATE_RESOURCE', responseErrorReason: 'PRIVATE_ERROR',
    responseHeaders: [{name: 'Access-Control-Allow-Origin', value: 'https://private.example'}, {name: 'Authorization', value: 'PRIVATE_TOKEN'}],
    request: {method: 'PRIVATE_METHOD'}})));
  const row = reports[0].responses[0];
  assert.equal(row.method, 'other');
  assert.equal(row.resourceType, 'other');
  assert.equal(row.responseError, 'other');
  assert.equal(row.cors.allowOrigin, 'other');
  assert.equal(JSON.stringify(reports).includes('PRIVATE'), false);
  assert.equal(JSON.stringify(reports).includes('private.example'), false);
});

test('synchronous handler failure remains the original error', async () => {
  const error = new Error('PRIVATE_SYNC'), reports = [];
  const wrapped = wrap(async () => {}, () => { throw error; }, r => reports.push(r));
  await assert.rejects(wrapped(event()), actual => actual === error);
  assert.equal(reports.length, 1);
});

test('diagnostic output failure cannot replace the interception failure', async () => {
  const error = new Error('interception');
  const wrapped = wrap(async () => {}, () => { throw error; }, () => { throw Error('observer'); });
  await assert.rejects(wrapped(event()), actual => actual === error);
});

test('retained history and failure output are bounded without suppressing failures', async () => {
  const reports = [], error = new Error('failure');
  const wrapped = wrap(async () => {}, received => { if (received.responseErrorReason) throw error; }, r => reports.push(r));
  for (let i = 0; i < 20; i++) await wrapped(event({requestId: `private-${i}`, networkId: `network-${i}`}));
  await assert.rejects(wrapped(event({responseErrorReason: 'Failed'})), actual => actual === error);
  await assert.rejects(wrapped(event({responseErrorReason: 'Failed'})), actual => actual === error);
  assert.equal(reports.length, 1);
  assert.equal(reports[0].responses.length, 16);
  assert.equal(reports[0].omittedResponses, 5);
  assert.equal(JSON.stringify(reports).includes('private-'), false);
});

test('invalid protocol error payload never leaks arbitrary values', async () => {
  const reports = [];
  const wrapped = wrap(async () => { throw Error('{"code":"PRIVATE_CODE","data":"PRIVATE_DATA"}'); }, async (received, command) => {
    await command('Fetch.continueResponse', {requestId: received.requestId});
  }, r => reports.push(r));
  await assert.rejects(wrapped(event()));
  assert.equal(reports[0].responses[0].commands[0].errorCode, null);
  assert.equal(JSON.stringify(reports).includes('PRIVATE_'), false);
});

test('deferred continuation after callback return still reports its genuine native failure', async () => {
  const reports = [], error = new Error('{"code":-32602,"message":"PRIVATE_DEFERRED"}');
  let resume;
  const wrapped = wrap(async () => { throw error; }, (received, command) => {
    resume = () => command('Fetch.continueResponse', {requestId: received.requestId});
    return 'held';
  }, report => reports.push(report));
  assert.equal(await wrapped(event({resourceType: 'Fetch', request: {method: 'POST'}})), 'held');
  assert.deepEqual(reports, []);
  await assert.rejects(resume(), actual => actual === error);
  assert.equal(reports.length, 1);
  assert.equal(reports[0].responses[0].method, 'POST');
  assert.equal(reports[0].responses[0].commands[0].errorCode, -32602);
  assert.equal(JSON.stringify(reports).includes('PRIVATE_'), false);
});

for (const method of ['OPTIONS', 'POST']) {
  test(`${method} request opts into response interception only for POST without rewriting the request`, async () => {
    assert.equal(typeof feature.continueRequestForPostResponse, 'function');
    const calls = [], input = event({resourceType: 'XHR', request: {method}});
    delete input.responseStatusCode;
    assert.equal(await feature.continueRequestForPostResponse(async (...args) => calls.push(args), input), true);
    assert.deepEqual(calls, [['Fetch.continueRequest', {requestId: 'private-fetch-id', interceptResponse: method === 'POST'}]]);
  });
}

for (const changes of [{responseStatusCode: 200}, {responseStatusCode: 0},
  {responseErrorReason: 'Failed'}, {responseErrorReason: ''}]) {
  test(`response-stage ${JSON.stringify(changes)} remains owned by the original handler`, async () => {
    assert.equal(typeof feature.continueRequestForPostResponse, 'function');
    const calls = [], input = {requestId: 'id', request: {method: 'POST'}, ...changes};
    assert.equal(await feature.continueRequestForPostResponse(async (...args) => calls.push(args), input), false);
    assert.deepEqual(calls, []);
  });
}

test('unexpected request methods reject rather than silently bypassing POST-only capture', async () => {
  assert.equal(typeof feature.continueRequestForPostResponse, 'function');
  for (const method of ['GET', 'HEAD', 'PUT', 'PATCH', 'DELETE', '', undefined]) {
    const calls = [];
    await assert.rejects(feature.continueRequestForPostResponse(async (...args) => calls.push(args), {requestId: 'id', request: {method}}));
    assert.deepEqual(calls, []);
  }
});

test('request continuation failure retains its native error and fixed diagnostic command', async () => {
  assert.equal(typeof feature.continueRequestForPostResponse, 'function');
  const reports = [], error = new Error('{"code":-32602,"message":"PRIVATE_REQUEST"}');
  const wrapped = wrap(async () => { throw error; }, (received, command) =>
    feature.continueRequestForPostResponse(command, received), value => reports.push(value));
  await assert.rejects(wrapped({requestId: 'PRIVATE_ID', resourceType: 'XHR', request: {method: 'OPTIONS'}}), actual => actual === error);
  assert.deepEqual(reports[0].responses[0].commands, [{method: 'Fetch.continueRequest', acknowledgment: 'error', errorCode: -32602}]);
  assert.equal(JSON.stringify(reports).includes('PRIVATE_'), false);
});
