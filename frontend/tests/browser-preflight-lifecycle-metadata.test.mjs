import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import {traceStartRecoveryResponses, createRequestSignalObserver} from './browser-start-recovery-diagnostics.mjs';

// Supplied CDP events only: neither browser execution nor an abort-cause verdict.
const front = 'http://127.0.0.1:15173', back = 'http://127.0.0.1:10199';
const secret = 'PRIVATE_HEADER_ORIGIN_URL_ID_REASON';
const ownedTarget = 'owned-' + secret;
const source = {protocol: 'cdp', targetId: ownedTarget};
function fixture() {
  let report;
  const calls = [];
  const trace = traceStartRecoveryResponses(async (...args) => { calls.push(args); }, async () => {},
    front, value => { report = value; }, {backend: back});
  return {trace, calls, send(method, params = {}, binding) { trace.observeBrowserEvent({method, params}, binding); },
    result() { trace.reportFailure(); return report.browserMetadata; }};
}
function request(h, method = 'OPTIONS', id = secret, path = '/matches/private/legal-moves') {
  h.send('Network.requestWillBeSent', {requestId: id, frameId: secret, loaderId: secret,
    request: {method, url: back + path, headers: {Authorization: secret}}, type: 'Preflight'});
}
function response(h, headers, id = secret) {
  h.send('Network.responseReceived', {requestId: id, timestamp: 2,
    response: {status: 200, headers, url: back + '/' + secret, headersText: secret}});
}
function cors(h) {
  const row = h.result().events.find(row => row.event === 'response');
  assert.ok(row?.cors, 'Actual selected response headers must have a categorical projection');
  return row.cors;
}
function privateFree(value) {
  const text = JSON.stringify(value);
  for (const value of [secret, front, back, 'Authorization', 'headersText', 'rawMessage']) assert.ok(!text.includes(value));
}
const allowed = {'Access-Control-Allow-Origin': front, 'ACCESS-CONTROL-ALLOW-METHODS': 'GET, POST',
  'Access-Control-Allow-Headers': 'Content-Type, Idempotency-Key', 'Access-Control-Allow-Private-Network': 'true'};

test('actual OPTIONS response exposes explicit GET/POST/header/PNA facts without raw headers', () => {
  const h = fixture(); request(h); response(h, {...allowed, Authorization: secret});
  assert.deepEqual(cors(h), {allowOrigin: 'expected', contentTypeAllowed: true, idempotencyKeyAllowed: true,
    getAllowed: true, postAllowed: true, methodsWildcard: false, headersWildcard: false, privateNetwork: 'true'});
  privateFree(h.result()); assert.deepEqual(h.calls, []);
});

for (const method of ['GET', 'OPTIONS']) test(`legal-moves ${method} response is scoped without inventing a preflight`, () => {
  const h = fixture(); request(h, method); response(h, allowed);
  assert.equal(cors(h).getAllowed, true);
  assert.equal(h.result().events.find(row => row.event === 'response').method, method);
  assert.deepEqual(h.result().events.map(row => row.event), ['request', 'response']);
});

test('start OPTIONS is observed, while an ordinary start POST retains the old response shape', () => {
  const h = fixture(); request(h, 'OPTIONS', 'one', '/matches/start'); response(h, allowed, 'one');
  request(h, 'POST', 'two', '/matches/start'); response(h, allowed, 'two');
  const rows = h.result().events.filter(row => row.event === 'response');
  assert.equal(rows[0].cors.postAllowed, true); assert.equal(Object.hasOwn(rows[1], 'cors'), false);
});

for (const [headers, origin, pna] of [[{}, 'absent', 'absent'],
  [{'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Private-Network': 'false'}, 'wildcard', 'false'],
  [{'Access-Control-Allow-Origin': secret, 'Access-Control-Allow-Private-Network': secret}, 'other', 'other'],
  [{'Access-Control-Allow-Origin': front + '\n' + front, 'Access-Control-Allow-Private-Network': 'true\ntrue'}, 'multiple', 'multiple'],
  [{'Access-Control-Allow-Origin': front, 'access-control-allow-origin': front}, 'multiple', 'absent']]) {
  test(`CORS categories preserve absence/ambiguity without a permission verdict ${origin}/${pna}`, () => {
    const h = fixture(); request(h); response(h, headers); const facts = cors(h);
    assert.equal(facts.allowOrigin, origin); assert.equal(facts.privateNetwork, pna); privateFree(h.result());
  });
}

test('wildcards and case-sensitive HTTP methods are not silently promoted to explicit GET/POST allowance', () => {
  const h = fixture(); request(h); response(h, {'Access-Control-Allow-Methods': 'get, *', 'Access-Control-Allow-Headers': '*'});
  const facts = cors(h);
  assert.equal(facts.getAllowed, false); assert.equal(facts.postAllowed, false);
  assert.equal(facts.methodsWildcard, true); assert.equal(facts.headersWildcard, true);
  assert.equal(facts.contentTypeAllowed, false); assert.equal(facts.idempotencyKeyAllowed, false);
});

test('CDP newline-combined header lists retain only categorical membership', () => {
  const h = fixture(); request(h); response(h, {'Access-Control-Allow-Methods': 'GET\nPOST',
    'Access-Control-Allow-Headers': 'content-type\nidempotency-key'});
  assert.equal(cors(h).getAllowed, true); assert.equal(cors(h).postAllowed, true);
  assert.equal(cors(h).contentTypeAllowed, true); assert.equal(cors(h).idempotencyKeyAllowed, true);
});

for (const [label, headers] of [['missing', undefined], ['null', null], ['array', []], ['scalar', secret],
  ['oversize-value', {'Access-Control-Allow-Origin': 'x'.repeat(4097)}],
  ['non-string', {'Access-Control-Allow-Origin': 1}],
  ['too-many', Object.fromEntries(Array.from({length: 129}, (_, i) => ['header-' + i, 'value']))]]) {
  test(`unsupported bounded header shape stays unavailable ${label}`, () => {
    const h = fixture(); request(h); response(h, headers); const facts = cors(h);
    assert.equal(facts.allowOrigin, 'unavailable'); assert.equal(facts.getAllowed, null);
    assert.equal(facts.contentTypeAllowed, null); assert.equal(facts.privateNetwork, 'unavailable'); privateFree(h.result());
  });
}

test('malformed token lists are unknown, not a clean negative or a raw value', () => {
  const h = fixture(); request(h); response(h, {'Access-Control-Allow-Methods': 'GET, invalid space',
    'Access-Control-Allow-Headers': 'content-type,'});
  assert.equal(cors(h).getAllowed, null); assert.equal(cors(h).contentTypeAllowed, null);
});

test('unjoined/foreign/scope-exited responses cannot borrow the last request CORS facts', () => {
  const h = fixture(); request(h); response(h, allowed, 'unjoined');
  h.send('Network.requestWillBeSent', {requestId: secret, request: {method: 'GET', url: 'https://foreign.invalid/'}});
  response(h, allowed); assert.equal(h.result().events.some(row => row.cors), false);
});

test('ExtraInfo is not assumed available and cannot replace a responseReceived observation', () => {
  const h = fixture(); request(h);
  h.send('Network.responseReceivedExtraInfo', {requestId: secret, statusCode: 200, headers: allowed});
  assert.deepEqual(h.result().events.map(row => row.event), ['request']);
});

for (const reason of ['remove', 'swap', secret, undefined]) test(`native frame detach reason is finite ${reason === secret ? 'other' : reason}`, () => {
  const h = fixture(); request(h);
  h.send('Page.frameDetached', {frameId: secret, reason, url: secret});
  const row = h.result().events.at(-1);
  assert.deepEqual(row, {event: 'frame-detached', frameOrdinal: 1, correlation: 'joined',
    reason: reason === undefined ? null : reason === secret ? 'other' : reason});
  privateFree(h.result()); assert.deepEqual(h.calls, []);
});

test('unknown frame loss stays unjoined and cannot allocate a frame identity', () => {
  const h = fixture();
  h.send('Page.frameDetached', {frameId: secret, reason: 'remove'});
  h.send('Page.frameSubtreeWillBeDetached', {frameId: secret});
  request(h);
  const rows = h.result().events;
  assert.equal(rows[0].frameOrdinal, null); assert.equal(rows[0].correlation, 'unjoined');
  assert.equal(rows[1].event, 'frame-subtree-will-detach'); assert.equal(rows[1].frameOrdinal, null);
  assert.equal(rows[2].frameOrdinal, 1);
});

for (const method of ['Inspector.detached', 'Inspector.targetCrashed']) test(`owned page-session lifecycle ${method} is not a fabricated request failure`, () => {
  const h = fixture(); h.send(method, {reason: secret, rawMessage: secret});
  const row = h.result().events[0];
  assert.equal(row.event, method === 'Inspector.detached' ? 'inspector-detached' : 'inspector-target-crashed');
  assert.equal(row.ownership, 'owned-page-session');
  assert.equal(h.result().outstandingRequests, 0); privateFree(h.result());
});

for (const method of ['Target.targetDestroyed', 'Target.targetCrashed', 'Target.detachedFromTarget']) {
  test(`target lifecycle ${method} requires the actual owned target binding`, () => {
    const h = fixture();
    for (const binding of [undefined, {protocol: 'webdriver-bidi', targetId: ownedTarget}, source]) {
      h.send(method, {targetId: ownedTarget, sessionId: secret, status: secret, errorCode: 9}, binding);
    }
    h.send(method, {targetId: 'foreign-' + secret, errorCode: 9}, source);
    const rows = h.result().events;
    assert.equal(rows.length, 4);
    assert.deepEqual(rows.map(row => row.ownership), ['unjoined', 'unjoined', 'owned', 'unjoined']);
    if (method === 'Target.targetCrashed') assert.equal(rows[2].errorCode, 9);
    privateFree(h.result());
  });
}

test('deprecated absent target ID never borrows session ID or last target identity', () => {
  const h = fixture(); h.send('Target.detachedFromTarget', {sessionId: ownedTarget}, source);
  assert.equal(h.result().events[0].ownership, 'unjoined');
});

test('new observations share the existing64 event and16 correlation limits', () => {
  const h = fixture(); request(h);
  for (let n = 0; n < 1000; n++) h.send('Page.frameDetached', {frameId: secret, reason: 'remove'});
  const value = h.result(); assert.equal(value.events.length, 64); assert.equal(value.omittedEvents, 937);
  assert.equal(value.correlationOverflow, 0); assert.deepEqual(h.calls, []);
});

test('late lifecycle and CORS events do not mutate the once-published failure snapshot', () => {
  const h = fixture(); request(h); response(h, allowed); const value = h.result(), before = JSON.stringify(value);
  h.send('Inspector.targetCrashed'); response(h, {}); assert.equal(JSON.stringify(h.result()), before);
});

function receiver(intercept, pending = new Map(), firefox = false) {
  const text = readFileSync(new URL('./browser-driver.mjs', import.meta.url), 'utf8');
  const begin = text.indexOf('  socket.onmessage ='), end = text.indexOf('\n  function rawCommand', begin);
  assert.ok(begin >= 0 && end > begin);
  const context = {socket: {}, passive: null, intercept, pending, JSON, Error,
    firefoxTransport: firefox, page: {id: ownedTarget}};
  vm.runInNewContext(text.slice(begin, end), context);
  return value => context.socket.onmessage({data: JSON.stringify(value)});
}

test('actual driver supplies only its owned CDP target for real target notifications', () => {
  const h = fixture(), receive = receiver(h.trace);
  receive({method: 'Target.targetDestroyed', params: {targetId: ownedTarget}});
  assert.equal(h.result().events[0].ownership, 'owned');
  const bidi = fixture(); receiver(bidi.trace, new Map(), true)({method: 'Target.targetDestroyed', params: {targetId: ownedTarget}});
  assert.equal(bidi.result().events[0].ownership, 'unjoined');
});

test('observer failure cannot consume command results/errors or the original Fetch exception', () => {
  const primary = new Error('original'), native = {code: -32602, message: 'original protocol failure'};
  const handler = () => { throw primary; }; handler.observeBrowserEvent = () => { throw new Error(secret); };
  let result, error;
  const receive = receiver(handler, new Map([[1, {resolve(value) {result = value;}}], [2, {reject(value) {error = value;}}]]));
  receive({id: 1, result: {original: true}}); receive({id: 2, error: native});
  assert.deepEqual(result, {original: true}); assert.equal(error.message, JSON.stringify(native));
  assert.throws(() => receive({method: 'Fetch.requestPaused', params: {requestId: secret}}), value => value === primary);
});

test('without metadata opt-in the original schema and absence of observer remain exact', () => {
  let report;
  const trace = traceStartRecoveryResponses(async () => {}, async () => {}, front, value => {report = value;});
  assert.equal(trace.observeBrowserEvent, undefined); trace.reportFailure();
  assert.deepEqual(Object.keys(report).sort(), ['omittedResponses', 'pendingCommands', 'responses']);
});

test('newline-expanded CORS headers remain within the old128 header-entry bound', () => {
  const h = fixture(); request(h);
  response(h, {'Access-Control-Allow-Methods': Array(129).fill('GET').join('\n')});
  assert.equal(cors(h).allowOrigin, 'unavailable'); assert.equal(cors(h).getAllowed, null);
});

test('an accessor header cannot execute diagnostic-time code or issue a command', () => {
  const h = fixture(); request(h); let reads = 0;
  response(h, {get 'Access-Control-Allow-Origin'() { reads++; throw new Error(secret); }});
  assert.equal(reads, 0); assert.equal(cors(h).allowOrigin, 'unavailable'); assert.deepEqual(h.calls, []);
});

for (const method of ['Page.frameDetached', 'Inspector.detached', 'Inspector.targetCrashed', 'Target.targetDestroyed']) {
  test(`lifecycle ${method} retires only the diagnostic owned context, including a shared early observer`, () => {
    for (const shared of [false, true]) {
      const early = shared ? createRequestSignalObserver(front, back) : null;
      let report;
      const trace = traceStartRecoveryResponses(async () => {}, async () => {}, front, value => {report = value;},
        {backend: back, ...(early ? {requestSignals: early} : {})});
      const send = (method, params = {}) => trace.observeBrowserEvent({method, params}, source);
      send('Page.frameNavigated', {frame: {id: secret, loaderId: secret}});
      send('Runtime.executionContextCreated', {context: {id: 3, origin: front, auxData: {isDefault: true, frameId: secret}}});
      send(method, {frameId: secret, targetId: ownedTarget, reason: 'remove'});
      const row = {phase: 'fetch-rejected', ordinal: 1, route: 'legal-moves', method: 'GET', elapsedMs: 15,
        signalAvailable: true, initialAborted: false, signalAborted: false, signalReasonClass: null,
        errorClass: 'TypeError', atRecordCap: false};
      send('Runtime.consoleAPICalled', {type: 'debug', executionContextId: 3,
        args: [{type: 'string', value: 'MTG_REQUEST_SIGNAL_DIAGNOSTIC'}, {type: 'string', value: JSON.stringify(row)}]});
      trace.reportFailure();
      assert.equal(report.browserMetadata.requestSignalAttribution.records.length, 0);
      assert.equal(report.browserMetadata.requestSignalAttribution.unknownContext, 1);
    }
  });
}

test('child-session and BiDi-shaped lifecycle events cannot impersonate the owned CDP page', () => {
  const h = fixture();
  for (const changes of [{sessionId: secret}, {protocol: 'webdriver-bidi'}]) {
    h.trace.observeBrowserEvent({method: 'Inspector.targetCrashed', params: {}, ...changes}, source);
    h.trace.observeBrowserEvent({method: 'Target.targetDestroyed', params: {targetId: ownedTarget}, ...changes}, source);
  }
  assert.deepEqual(h.result().events, []);
});

test('malformed frame IDs cannot create detach correlations or consume identities', () => {
  const h = fixture();
  for (const frameId of [undefined, null, '', 1, {}, 'x'.repeat(257)]) h.send('Page.frameDetached', {frameId, reason: 'remove'});
  request(h); const value = h.result();
  assert.equal(value.invalidEvents, 6); assert.equal(value.events.length, 1); assert.equal(value.events[0].frameOrdinal, 1);
});
