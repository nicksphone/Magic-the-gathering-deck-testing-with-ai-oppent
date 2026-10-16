import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import {traceStartRecoveryResponses, continueRequestForPostResponse} from './browser-start-recovery-diagnostics.mjs';

// Synthetic protocol controls, not browser/guest/application qualification.
const front = 'http://127.0.0.1:15173', back = 'http://127.0.0.1:10199';
const privateValue = 'PRIVATE_TOKEN_BODY_URL_STACK';
function observer() {
  let value;
  const commands = [];
  const trace = traceStartRecoveryResponses(async (...args) => commands.push(args), async () => {},
    front, report => { value = report; }, {backend: back});
  return {trace, commands, send(method, params = {}) { trace.observeBrowserEvent({method, params}); },
    result() { trace.reportFailure(); return value.browserMetadata; }};
}
function created(h, id = 'socket', url = `ws://127.0.0.1:15173/?token=${privateValue}`) {
  h.send('Network.webSocketCreated', {requestId: id, url, timestamp: 1, initiator: {stack: privateValue}});
}
function handshake(h, id = 'socket', response = {status: 101, headers: {'sEc-WeBsOcKeT-pRoToCoL': 'vite-hmr'}}) {
  h.send('Network.webSocketHandshakeResponseReceived', {requestId: id, timestamp: 2, response});
}
function frame(h, type = 'full-reload', id = 'socket', changes = {}) {
  h.send('Network.webSocketFrameReceived', {requestId: id, timestamp: 3,
    response: {opcode: 1, payloadData: JSON.stringify({type, path: privateValue, err: privateValue}), ...changes}});
}
const messages = result => result.events.filter(row => row.event === 'vite-message');
function privateFree(value) {
  const text = JSON.stringify(value);
  for (const secret of [privateValue, front, back, '"socket"', 'Authorization', 'callFrames']) {
    assert.ok(!text.includes(secret), `Diagnostic leaked ${secret}`);
  }
}

for (const reason of ['formSubmissionGet', 'formSubmissionPost', 'httpHeaderRefresh', 'scriptInitiated',
  'metaTagRefresh', 'pageBlockInterstitial', 'reload', 'anchorClick']) {
  test(`native requested navigation retains only finite reason ${reason}`, () => {
    const h = observer();
    h.send('Page.frameRequestedNavigation', {frameId: privateValue, reason, url: front + '/' + privateValue});
    const result = h.result();
    assert.deepEqual(result.events, [{event: 'navigation-requested', frameOrdinal: 1, reason}]);
    privateFree(result); assert.deepEqual(h.commands, []);
  });
}
for (const navigationType of ['reload', 'reloadBypassingCache', 'restore', 'restoreWithPost',
  'sameDocument', 'differentDocument', 'historySameDocument', 'historyDifferentDocument']) {
  test(`native started navigation retains finite type ${navigationType}`, () => {
    const h = observer();
    h.send('Page.frameStartedNavigating', {frameId: privateValue, loaderId: privateValue,
      navigationType, url: front + '/' + privateValue});
    const result = h.result();
    assert.deepEqual(result.events, [{event: 'navigation-started', frameOrdinal: 1, loaderOrdinal: 1, navigationType}]);
    privateFree(result);
  });
}
test('unknown navigation categories are other and malformed frame IDs do not become identities', () => {
  const h = observer();
  h.send('Page.frameRequestedNavigation', {frameId: 'one', reason: privateValue});
  h.send('Page.frameStartedNavigating', {frameId: 'one', loaderId: 'two', navigationType: privateValue});
  for (const frameId of [undefined, null, '', 'x'.repeat(257), {}, 1]) {
    h.send('Page.frameRequestedNavigation', {frameId, reason: 'reload'});
  }
  const result = h.result();
  assert.equal(result.events.length, 2);
  assert.equal(result.events[0].reason, 'other'); assert.equal(result.events[1].navigationType, 'other');
  assert.equal(result.unknownCategories, 2); assert.ok(result.invalidEvents >= 6); privateFree(result);
});

for (const initiator of ['parser', 'script', 'preload', 'SignedExchange', 'preflight', 'other']) {
  test(`frontend root Document records only ${initiator} initiator category`, () => {
    const h = observer();
    h.send('Network.requestWillBeSent', {type: 'Document', requestId: privateValue, frameId: privateValue,
      loaderId: privateValue, timestamp: 9, request: {method: 'GET', url: front + '/?private=' + privateValue,
        headers: {Authorization: privateValue}, postData: privateValue},
      initiator: {type: initiator, stack: {callFrames: [{url: privateValue}]}}});
    const result = h.result();
    assert.deepEqual(result.events, [{event: 'document-request', networkOrdinal: 1,
      frameOrdinal: 1, loaderOrdinal: 1, timestamp: 9, initiator}]);
    assert.equal(result.outstandingRequests, 0); privateFree(result);
  });
}
for (const [type, url] of [['Document', back + '/'], ['Document', 'https://foreign.invalid/'],
  ['Document', front + '/private'], ['Document', 'http://user:password@127.0.0.1:15173/'], ['Fetch', front + '/']]) {
  test(`foreign or non-root document is not admitted ${type} ${url}`, () => {
    const h = observer();
    h.send('Network.requestWillBeSent', {type, requestId: privateValue, request: {method: 'GET', url}});
    assert.deepEqual(h.result().events, []);
  });
}
test('a frontend Document redirect preserves existing action scope-exit accounting', () => {
  const h = observer();
  h.send('Network.requestWillBeSent', {requestId: 'redirect', request: {method: 'POST', url: back + '/matches/private/action'}});
  h.send('Network.requestWillBeSent', {requestId: 'redirect', type: 'Document', request: {method: 'GET', url: front + '/'}});
  const result = h.result();
  assert.equal(result.outstandingRequests, 0);
  assert.equal(result.events.at(-1).event, 'scope-exit');
  assert.equal(result.events.at(-1).networkOrdinal, result.events[0].networkOrdinal);
});

for (const type of ['connected', 'update', 'full-reload', 'custom', 'prune', 'error', 'ping']) {
  test(`owned native 101 plus vite-hmr admits only finite message type ${type}`, () => {
    const h = observer(); created(h); handshake(h); frame(h, type);
    const result = h.result();
    assert.deepEqual(result.events.map(row => row.event), ['frontend-websocket-created', 'vite-handshake', 'vite-message']);
    assert.deepEqual(messages(result), [{event: 'vite-message', socketOrdinal: 1, timestamp: 3, messageType: type}]);
    assert.deepEqual(result.events.map(row => row.socketOrdinal), [1, 1, 1]);
    privateFree(result); assert.deepEqual(h.commands, []);
  });
}
for (const url of ['ws://foreign.invalid/', 'wss://127.0.0.1:15173/', 'ws://127.0.0.1:15173/private',
  'ws://user:password@127.0.0.1:15173/', 'ws://127.0.0.1:15173/#private', 'not a URL']) {
  test(`foreign/noncanonical WebSocket cannot acquire Vite ownership ${url}`, () => {
    const h = observer(); created(h, 'socket', url); handshake(h); frame(h);
    assert.deepEqual(messages(h.result()), []);
  });
}
for (const response of [{status: 200, headers: {'Sec-WebSocket-Protocol': 'vite-hmr'}},
  {status: '101', headers: {'Sec-WebSocket-Protocol': 'vite-hmr'}},
  {status: 101, headers: {}}, {status: 101, headers: {'Sec-WebSocket-Protocol': 'VITE-HMR'}},
  {status: 101, headers: {'Sec-WebSocket-Protocol': 'vite-hmr,other'}},
  {status: 101, headers: {'Sec-WebSocket-Protocol': 'vite-hmr', 'sec-websocket-protocol': 'other'}}]) {
  test(`actual status/protocol handshake is mandatory ${JSON.stringify(response)}`, () => {
    const h = observer(); created(h); handshake(h, 'socket', response); frame(h);
    assert.deepEqual(messages(h.result()), []);
  });
}
test('missing creation or handshake and post-close frames never impersonate the owned socket', () => {
  const h = observer(); handshake(h); frame(h);
  created(h); frame(h); handshake(h); frame(h, 'connected');
  h.send('Network.webSocketClosed', {requestId: 'socket', timestamp: 4}); frame(h);
  const result = h.result();
  assert.deepEqual(messages(result).map(row => row.messageType), ['connected']);
  assert.equal(result.events.at(-1).event, 'vite-closed'); privateFree(result);
});
test('duplicate native creation or handshake invalidates ownership rather than inheriting it', () => {
  for (const duplicate of ['creation', 'handshake']) {
    const h = observer(); created(h); handshake(h);
    if (duplicate === 'creation') created(h, 'socket', 'ws://foreign.invalid/'); else handshake(h);
    frame(h); assert.deepEqual(messages(h.result()), []);
  }
});
for (const [index, changes] of [{opcode: 2}, {opcode: '1'}, {payloadData: '{'}, {payloadData: 'null'},
  {payloadData: '[]'}, {payloadData: JSON.stringify({type: privateValue})},
  {payloadData: ' '.repeat(4097)}, {payloadData: JSON.stringify({type: 'update', private: '\u6f22'.repeat(1500)})}].entries()) {
  test(`malformed/nontext/oversize message case ${index} never leaks or becomes a cause ${Object.keys(changes).join()}`, () => {
    const h = observer(); created(h); handshake(h); frame(h, 'full-reload', 'socket', changes);
    const result = h.result(); assert.deepEqual(messages(result), []); privateFree(result);
  });
}
test('WebSocket retention16 and event64 bounds do not grow or issue protocol commands', () => {
  const h = observer();
  for (let n = 0; n < 17; n++) { created(h, 'native-' + n); handshake(h, 'native-' + n); }
  for (let n = 0; n < 1000; n++) frame(h, 'ping', 'native-0');
  const result = h.result();
  assert.equal(result.webSocketOverflow, 1); assert.equal(result.events.length, 64);
  assert.ok(result.omittedEvents > 0); assert.ok(result.events.every(row => row.socketOrdinal <= 16));
  assert.deepEqual(h.commands, []); privateFree(result);
});
test('foreign socket flood cannot consume the owned16 socket slots', () => {
  const h = observer();
  for (let n = 0; n < 1000; n++) created(h, 'foreign-' + n, 'ws://foreign.invalid/');
  created(h); handshake(h); frame(h);
  const result = h.result(); assert.equal(messages(result).length, 1);
  assert.equal(messages(result)[0].socketOrdinal, 1); assert.equal(result.webSocketOverflow, 0);
});
test('late native frames cannot mutate the first failure snapshot', () => {
  const h = observer(); created(h); handshake(h); frame(h);
  const result = h.result(), before = JSON.stringify(result); frame(h, 'update');
  assert.equal(JSON.stringify(result), before); assert.equal(JSON.stringify(h.result()), before);
});

const costsSource = readFileSync(new URL('./browser-ui-v2-costs.mjs', import.meta.url), 'utf8');
const setupCode = costsSource.slice(costsSource.indexOf('async function humanIdle()'), costsSource.indexOf('\ntry {'));
function sequence({setupError, earlyPause = false, pauseSetup = false} = {}) {
  const candidate = costsSource.indexOf(' let s,held,continueHeld;');
  const begin = candidate >= 0 ? candidate : costsSource.indexOf(" const s=await setup('/fixture');");
  const end = costsSource.lastIndexOf('\n} finally {await b.close();}');
  assert.ok(begin >= 0 && end > begin);
  let trace, resumeSetup;
  const setupPending = new Promise(resolve => { resumeSetup = resolve; });
  const calls = [], logs = [], state = {id: 'PRIVATE_MATCH', revision: 0};
  const browser = {
    onIntercept(fn) { calls.push('hook'); trace = fn; },
    async command(method) { calls.push(method); },
    async evaluate(expression) { return expression.includes('every(e=>e.disabled)') ? true : undefined; },
    async waitFor() {},
    async reload() {
      calls.push('reload');
      assert.equal(typeof trace?.observeBrowserEvent, 'function', 'Observer was not installed before actual setup reload');
      trace.observeBrowserEvent({method: 'Network.webSocketCreated', params: {requestId: 'socket', url: front.replace('http:', 'ws:') + '/?token=' + privateValue}});
      trace.observeBrowserEvent({method: 'Network.webSocketHandshakeResponseReceived', params: {requestId: 'socket', response: {status: 101, headers: {'Sec-WebSocket-Protocol': 'vite-hmr'}}}});
      trace.observeBrowserEvent({method: 'Network.webSocketFrameReceived', params: {requestId: 'socket', response: {opcode: 1, payloadData: '{"type":"connected"}'}}});
      if (earlyPause) await trace({requestId: 'early', request: {method: 'POST', url: back + '/matches/unknown/action'}, responseStatusCode: 200});
      if (pauseSetup) await setupPending;
    },
    async click() {
      calls.push('click');
      const event = {requestId: 'post', request: {method: 'POST', url: back + '/matches/' + state.id + '/action'}};
      await trace(event); await trace({...event, responseStatusCode: 200});
    },
  };
  const context = {b: browser, api: back, ui: front, assert, traceStartRecoveryResponses,
    continueRequestForPostResponse, JSON, AbortController,
    fetch: async (url, options) => {
      calls.push(options.method + ':' + url);
      assert.equal(options.method, 'POST', 'Setup failure must never fetch diagnostic /matches/undefined');
      if (setupError) throw setupError;
      return {status: 200, json: async () => state};
    },
    waitForApiState: async () => ({revision: 1, players: {'2': {battlefield: [{id: 'forest'}]}}}),
    setTimeout() { throw Error('Positive flow must not enter a polling/diagnostic timer'); }, clearTimeout() {},
    console: {log() {}, error(label, value) { logs.push({label, value: JSON.parse(value)}); }}};
  const promise = vm.runInNewContext(`(async()=>{${setupCode}\n${costsSource.slice(begin, end)}})()`, context);
  promise.catch(() => {});
  return {promise, calls, logs, release: resumeSetup, trace: () => trace};
}
test('actual setup/reload arms observer first and enables Fetch only after the known fixture returns', async () => {
  const p = sequence({pauseSetup: true});
  await new Promise(setImmediate);
  assert.equal(p.calls[0], 'hook'); assert.ok(p.calls.includes('reload'));
  assert.ok(!p.calls.includes('Fetch.enable')); assert.ok(!p.calls.includes('click'));
  p.release(); await p.promise;
  assert.ok(p.calls.indexOf('Fetch.enable') > p.calls.indexOf('reload'));
  assert.equal(p.calls.filter(call => call === 'reload').length, 1);
  assert.equal(p.calls.filter(call => call === 'click').length, 1);
  assert.deepEqual(p.logs, []);
  p.trace().reportFailure();
  assert.equal(p.logs[0].value.browserMetadata.events.find(row => row.event === 'vite-message').messageType, 'connected');
});
test('actual setup failure preserves its original error and never reads an undefined match', async () => {
  const primary = new Error('PRIVATE_SETUP_FAILURE'); const p = sequence({setupError: primary});
  await assert.rejects(p.promise, error => error === primary);
  assert.equal(p.calls[0], 'hook'); assert.equal(p.calls.filter(call => call.startsWith('POST:')).length, 1);
  assert.ok(!p.calls.includes('Fetch.enable')); assert.ok(!p.calls.includes('click'));
  assert.deepEqual(p.logs.map(row => row.label), ['V2_HELD_RESPONSE_TRACE']);
  privateFree(p.logs);
});
test('a Fetch pause before fixture identity is known cannot bind held state or continue it', async () => {
  const p = sequence({earlyPause: true});
  await assert.rejects(p.promise, /fixture is not ready/);
  assert.ok(!p.calls.some(call => call.startsWith('Fetch.'))); assert.ok(!p.calls.includes('click'));
  assert.deepEqual(p.logs.map(row => row.label), ['V2_HELD_RESPONSE_TRACE']);
});
