// Pure CDP scheduling model plus actual caller slices/helper, not browser evidence.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import vm from 'node:vm';
import * as diagnostics from './browser-start-recovery-diagnostics.mjs';

const startSource = readFileSync(new URL('./browser-start-recovery.mjs', import.meta.url), 'utf8');
const costSource = readFileSync(new URL('./browser-ui-v2-costs.mjs', import.meta.url), 'utf8');
const backend = 'http://api.invalid', frontend = 'http://frontend.invalid';
const key = '0123456789abcdef0123456789abcdef';
const payload = {deck_a: 1, deck_b: 2, mode: 'human_vs_human'};
const body = JSON.stringify(payload);
const plain = value => JSON.parse(JSON.stringify(value));

function lifecycle(url) {
  let patterns = [], callback, serial = 0;
  const calls = [], pauses = [], responseOverrides = new Map();
  const selected = stage => patterns.some(pattern => pattern.requestStage === stage &&
    new RegExp('^' + pattern.urlPattern.split('*').map(value => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('.*') + '$').test(url));
  const command = async (method, params = {}) => {
    calls.push([method, plain(params)]);
    if (method === 'Fetch.enable') patterns = plain(params.patterns);
    if (method === 'Fetch.disable') patterns = [];
    if (method === 'Fetch.continueRequest') responseOverrides.set(params.requestId, params.interceptResponse);
    if (method === 'Network.getRequestPostData') return {postData: body, base64Encoded: false};
    return {};
  };
  return {calls, pauses, command, onIntercept(fn) { callback = fn; },
    async exchange(method) {
      const event = {requestId: 'fetch-' + (++serial), networkId: 'network-' + serial,
        request: {url, method, headers: {'Idempotency-Key': key}, ...(method === 'POST' ? {postData: body} : {})},
        resourceType: 'XHR'};
      if (selected('Request')) {
        pauses.push({method, stage: 'Request'});
        await callback(event);
        assert.ok(responseOverrides.has(event.requestId), 'Request continuation must actually ACK before the response phase');
      }
      if (responseOverrides.has(event.requestId) ? responseOverrides.get(event.requestId) : selected('Response')) {
        pauses.push({method, stage: 'Response'});
        await callback({...event, responseStatusCode: 200, responseHeaders: []});
      }
      return event;
    },
  };
}

function startFixture() {
  const life = lifecycle(backend + '/matches/start');
  const begin = startSource.indexOf('async function startWithDroppedResponses(');
  const end = startSource.indexOf('\ntry {', begin);
  assert.ok(begin >= 0 && end > begin);
  const context = {assert, Buffer, URL, backend, ...diagnostics, command: life.command,
    onIntercept: life.onIntercept, browser: {}, process: {env: {}}, reviewStart: async () => {},
    click: async label => assert.equal(label, 'Start Best-of-3 Match'), console: {log() {}, error() {}}};
  vm.runInNewContext(`${startSource.slice(begin, end)}\nglobalThis.start = startWithDroppedResponses; globalThis.resume = resumeRequestCapture;`, context);
  return {life, start: count => context.start(count), resume: () => context.resume()};
}

async function costFixture() {
  const life = lifecycle(backend + '/matches/owned/action');
  const begin = costSource.indexOf(' b.onIntercept(');
  const end = costSource.indexOf("\n s=await setup('/fixture');", begin);
  const enableBegin = costSource.indexOf(" await b.command('Fetch.enable'", end);
  const enableEnd = costSource.indexOf('\n', enableBegin + 1);
  const release = "await continueHeld();await b.command('Fetch.disable');";
  assert.ok(begin >= 0 && end > begin && enableBegin > end && enableEnd > enableBegin);
  assert.ok(costSource.includes(release));
  const context = {...diagnostics, ui: frontend, api: backend, s: {id: 'owned'},
    b: {onIntercept: life.onIntercept, command: life.command}, console: {error() {}}};
  await vm.runInNewContext(`(async()=>{let held,continueHeld,heldTrace,currentUrlSeen=false,otherUrlSeen=false;\n${costSource.slice(begin, end)}\n${costSource.slice(enableBegin, enableEnd)}\nglobalThis.held = () => held; globalThis.release = async()=>{${release}};})()`, context);
  return {life, held: () => context.held(), release: () => context.release()};
}

const responseMethods = life => life.pauses.filter(row => row.stage === 'Response').map(row => row.method);
const continuations = life => life.calls.filter(([method]) => method === 'Fetch.continueRequest');

test('actual initial start selects only the POST response after request-stage opt-in', async () => {
  const f = startFixture(), dropped = await f.start(1);
  await f.life.exchange('OPTIONS');
  await f.life.exchange('POST');
  assert.deepEqual(responseMethods(f.life), ['POST']);
  assert.deepEqual(continuations(f.life).map(([, params]) => params.interceptResponse), [false, true]);
  assert.equal(dropped(), 1);
  assert.deepEqual(plain(dropped.attempts), [{key, payload}]);
  assert.equal(f.life.calls.filter(([method]) => method === 'Fetch.failRequest').length, 1);
});

test('actual start rearm restores POST-only response selection at the same endpoint', async () => {
  const f = startFixture(), dropped = await f.start(0);
  await f.life.command('Fetch.disable');
  await f.resume();
  await f.life.exchange('OPTIONS');
  await f.life.exchange('POST');
  assert.deepEqual(responseMethods(f.life), ['POST']);
  assert.deepEqual(continuations(f.life).map(([, params]) => params.interceptResponse), [false, true]);
  assert.equal(f.life.calls.filter(([method]) => method === 'Fetch.enable').length, 2);
  assert.deepEqual(plain(dropped.attempts), [{key, payload}]);
  assert.equal(dropped(), 0);
  assert.equal(f.life.calls.filter(([method]) => method === 'Fetch.continueResponse').length, 1);
});

test('actual cost capture never pauses an OPTIONS response and holds POST until the original explicit release', async () => {
  const f = await costFixture();
  await f.life.exchange('OPTIONS');
  const post = await f.life.exchange('POST');
  assert.deepEqual(responseMethods(f.life), ['POST']);
  assert.deepEqual(continuations(f.life).map(([, params]) => params.interceptResponse), [false, true]);
  assert.equal(f.held().requestId, post.requestId);
  assert.equal(f.held().responseStatusCode, 200);
  assert.equal(f.life.calls.filter(([method]) => method === 'Fetch.continueResponse').length, 0);
  await f.release();
  assert.deepEqual(f.life.calls.slice(-2), [
    ['Fetch.continueResponse', {requestId: post.requestId}], ['Fetch.disable', {}],
  ]);
});

for (const stage of ['Response', 'Request']) {
  test(`CDP scheduling control: ${stage} patterns ${stage === 'Response' ? 'also select OPTIONS responses' : 'honor each request opt-in'}`, async () => {
    const life = lifecycle(backend + '/matches/start');
    life.onIntercept(async event => {
      if (await diagnostics.continueRequestForPostResponse(life.command, event)) return;
      await life.command('Fetch.continueResponse', {requestId: event.requestId});
    });
    await life.command('Fetch.enable', {patterns: [{urlPattern: '*/matches/start', requestStage: stage}]});
    await life.exchange('OPTIONS');
    await life.exchange('POST');
    assert.deepEqual(responseMethods(life), stage === 'Response' ? ['OPTIONS', 'POST'] : ['POST']);
    assert.deepEqual(continuations(life).map(([, params]) => params.interceptResponse), stage === 'Response' ? [] : [false, true]);
  });
}
