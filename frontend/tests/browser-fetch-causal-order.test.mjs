// Protocol mocks only. These observations are not native/browser evidence.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import {traceStartRecoveryResponses, continueRequestForPostResponse} from './browser-start-recovery-diagnostics.mjs';

const front = 'http://127.0.0.1:15173', back = 'http://127.0.0.1:10199';
const secret = 'PRIVATE_PAYLOAD_URL_TOKEN';
const owner = {protocol: 'cdp', targetId: 'target-' + secret};
const pause = changes => ({requestId: 'fetch-' + secret, networkId: 'network-' + secret,
  resourceType: 'XHR', responseStatusCode: 200,
  request: {method: 'OPTIONS', url: back + '/matches/fixture/action', postData: secret}, ...changes});
const deferred = () => {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return {promise, resolve, reject};
};
function fixture(command = async () => 'native-result', handler = (event, observed) =>
  observed('Fetch.continueResponse', {requestId: event.requestId})) {
  const reports = [], calls = [];
  const trace = traceStartRecoveryResponses((...args) => { calls.push(args); return command(...args); },
    handler, front, value => reports.push(value), {backend: back, causal: true});
  return {trace, reports, calls,
    control(method, acknowledgment) { trace.observeControl?.(method, acknowledgment); },
    async send(event, source = owner, sessionId) {
      trace.observeBrowserEvent({method: 'Fetch.requestPaused', params: event,
        ...(sessionId === undefined ? {} : {sessionId})}, source);
      return trace(event);
    },
    snapshot() { trace.reportFailure(); return reports[0]; }};
}
const causalEvents = report => report.browserMetadata.events.filter(row => row.event.startsWith('fetch-'));

test('same Fetch ID response then error preserves both original commands and the native error', async () => {
  const primary = new Error('{"code":-32602,"message":"PRIVATE_PAYLOAD_URL_TOKEN"}');
  let calls = 0;
  const h = fixture(async () => { if (++calls === 2) throw primary; return 17; });
  h.control('Fetch.enable', 'sent'); h.control('Fetch.enable', 'accepted');
  assert.equal(await h.send(pause()), 17);
  await assert.rejects(h.send(pause({responseStatusCode: undefined, responseErrorReason: 'Failed'})), e => e === primary);
  assert.equal(h.calls.length, 2);
  const report = h.reports[0];
  assert.ok(report.causal, 'Missing passive causal diagnostics');
  const rows = causalEvents(report).filter(row => row.event === 'fetch-pause');
  assert.deepEqual(rows.map(row => row.stage), ['response', 'response-error']);
  assert.equal(rows[0].scopedRequestOrdinal, rows[1].scopedRequestOrdinal);
  assert.deepEqual(rows.map(row => row.resourceType), ['XHR', 'XHR']);
  const commands = causalEvents(report).filter(row => row.event === 'fetch-command');
  assert.deepEqual(commands.map(row => row.acknowledgment), ['sent', 'accepted', 'sent', 'error']);
  assert.ok(commands.every(row => row.requestIdBinding === 'fetch'));
  assert.ok(!JSON.stringify(report).includes(secret));
});

test('different Fetch IDs sharing a Network ID retain separate scoped identities', async () => {
  const h = fixture(); h.control('Fetch.enable', 'sent'); h.control('Fetch.enable', 'accepted');
  await h.send(pause()); await h.send(pause({requestId: 'second-' + secret}));
  const report = h.snapshot(); assert.ok(report.causal, 'Missing scoped identity namespace');
  const rows = causalEvents(report).filter(row => row.event === 'fetch-pause');
  assert.notEqual(rows[0].scopedRequestOrdinal, rows[1].scopedRequestOrdinal);
  assert.equal(report.responses[0].networkOrdinal, report.responses[1].networkOrdinal);
  assert.equal(h.calls.length, 2);
});

test('owner session and accepted enable generation are separate bounded namespaces', async () => {
  const h = fixture(); h.control('Fetch.enable', 'sent');
  await h.send(pause()); // A native pause may precede the enable ACK.
  h.control('Fetch.enable', 'accepted');
  await h.send(pause(), owner, 'child-' + secret);
  h.control('Fetch.disable', 'sent'); h.control('Fetch.disable', 'accepted');
  h.control('Fetch.enable', 'sent'); h.control('Fetch.enable', 'accepted');
  await h.send(pause(), {protocol: 'cdp', targetId: 'other-' + secret});
  await h.trace(pause()); // Missing wire provenance is never invented.
  const report = h.snapshot(); assert.ok(report.causal, 'Missing generation/ownership diagnostics');
  const rows = causalEvents(report).filter(row => row.event === 'fetch-pause');
  assert.equal(rows[0].generationState, 'enable-pending');
  assert.equal(rows[1].sessionScope, 'child');
  assert.notEqual(rows[0].scopedRequestOrdinal, rows[1].scopedRequestOrdinal);
  assert.notEqual(rows[0].ownerOrdinal, rows[2].ownerOrdinal);
  assert.equal(rows[2].enableGeneration, 2);
  assert.equal(rows[3].provenance, 'unjoined');
  assert.equal(rows[3].scopedRequestOrdinal, null);
  assert.equal(h.calls.length, 4);
});

test('response error with no status stays response-error without a continuation-method swap', async () => {
  const h = fixture(async () => 23, async (event, command) => {
    assert.equal(await continueRequestForPostResponse(command, event), false);
    return command('Fetch.continueResponse', {requestId: event.requestId});
  });
  const event = pause({responseErrorReason: 'Failed'}); delete event.responseStatusCode;
  assert.equal(await h.send(event), 23);
  const report = h.snapshot(); assert.ok(report.causal, 'Missing explicit native stage');
  const row = causalEvents(report).find(row => row.event === 'fetch-pause');
  assert.equal(row.stage, 'response-error');
  assert.equal(row.statusPresent, false); assert.equal(row.errorPresent, true);
  assert.deepEqual(h.calls, [['Fetch.continueResponse', {requestId: event.requestId}]]);
});

test('later event before prior ACK does not serialize injected promises or change primary rejection', async () => {
  const first = deferred(), second = deferred(), primary = new Error('original-native');
  let count = 0;
  const h = fixture(() => (++count === 1 ? first.promise : second.promise));
  const a = h.send(pause()); const b = h.send(pause({requestId: 'other-' + secret}));
  b.catch(() => {}); second.reject(primary); await assert.rejects(b, e => e === primary);
  assert.equal(h.calls.length, 2);
  const frozen = JSON.stringify(h.reports[0]);
  first.resolve(99); assert.equal(await a, 99);
  assert.equal(JSON.stringify(h.reports[0]), frozen);
  assert.equal(typeof h.trace.captureFinal, 'function', 'Missing bounded after-first capture');
  const final = h.trace.captureFinal();
  assert.equal(final.pendingCommands, 0); assert.equal(final.activeCallbacks, 0);
  assert.ok(final.events.some(row => row.event === 'fetch-command' && row.acknowledgment === 'accepted'));
  assert.ok(final.events.every(row => row.localOrdinal > final.firstFailureEventCount));
  assert.equal(final.nativeWireCommandIdentity, 'unknown');
});

test('actual UI caller captures after-first metadata only after its existing failure-only reads', async () => {
  const source = readFileSync(new URL('./browser-ui-v2.mjs', import.meta.url), 'utf8');
  const start = source.indexOf('async function recoverDroppedResponse(s) {');
  const end = source.indexOf('\ntry {', start);
  assert.ok(start >= 0 && end > start);
  const primary = new Error('{"code":-32602,"message":"original-native"}');
  const calls = [], logs = [], reads = []; let trace, serial = 0;
  const event = pause({responseStatusCode: undefined, responseErrorReason: 'Failed'});
  const command = async method => { calls.push(method); if (method === 'Fetch.continueResponse') throw primary; };
  const context = {api: back, origin: front, traceStartRecoveryResponses, continueRequestForPostResponse, command,
    b: {supportsFetchResourceTypeFilter: true,
      onIntercept(value) { trace = value; }, async browserIdentity() { reads.push('runtime'); return {product: 'Chrome/155.0.8059.85', protocolVersion: '1.3'}; }},
    click: async () => { trace.observeBrowserEvent({method: 'Fetch.requestPaused', params: event}, owner); await trace(event); },
    evaluate: async () => ({activeMatch: true, renderedMatch: true, renderedRevision: '0', enabledPrefixCount: 0}),
    waitFor: async () => assert.fail('No recovery predicate after native rejection'),
    fetch: async () => { reads.push('canonical'); trace.observeBrowserEvent({method: 'Network.requestWillBeSent', params: {
      requestId: 'late-' + secret, type: 'Fetch', request: {method: 'POST', url: back + '/matches/fixture/action'}}});
      return {ok: true, json: async () => ({revision: 1})}; },
    Date, Promise, AbortController, setTimeout: () => ++serial, clearTimeout() {},
    console: {error(...args) { logs.push(args); }} };
  const fn = vm.runInNewContext('(' + source.slice(start, end) + ')', context);
  await assert.rejects(fn({id: 'fixture'}), e => e === primary);
  assert.equal(logs.length, 1); assert.equal(logs[0][0], 'DROP_RESPONSE_TRACE');
  const diagnostic = JSON.parse(logs[0][1]);
  assert.ok(diagnostic.requestLifecycleFinal, 'Actual caller lacks final capture after failure-only reads');
  assert.ok(diagnostic.requestLifecycleFinal.events.some(row => row.event === 'request' && row.method === 'POST'));
  assert.ok(!diagnostic.requestLifecycle.browserMetadata.events.some(row => row.event === 'request' && row.method === 'POST'));
  assert.deepEqual(reads.sort(), ['canonical', 'runtime']);
  assert.deepEqual(calls, ['Network.enable', 'Fetch.enable', 'Fetch.continueResponse', 'Fetch.disable']);
  assert.equal(diagnostic.canonical.revision, 1);
});

test('shared event64 identity16 pause16 command8 limits and privacy survive overflow', async () => {
  const h = fixture();
  for (let index = 0; index < 100; index++) {
    h.control('Fetch.enable', 'sent'); h.control('Fetch.enable', 'accepted');
    await h.send(pause({requestId: secret + index}), {protocol: 'cdp', targetId: secret + index}, secret + index);
  }
  const report = h.snapshot(); assert.ok(report.causal, 'Missing bounded identity counters');
  assert.ok(report.browserMetadata.events.length <= 64);
  assert.ok(report.responses.length <= 16 && report.responses.every(row => row.commands.length <= 8));
  assert.ok(report.causal.owners <= 16 && report.causal.sessions <= 16 && report.causal.requests <= 16);
  assert.ok(report.browserMetadata.omittedEvents > 0 && report.causal.unknownBindings > 0);
  assert.ok(!JSON.stringify(report).includes(secret));
  assert.equal(h.calls.length, 100, 'No dedup/ignore at observer capacity');
  assert.equal(typeof h.trace.captureFinal, 'function');
  assert.ok(JSON.stringify(h.trace.captureFinal()).length < 32000);
});

test('Network Fetch never fabricates a POST pause type and Firefox resourceType rejection is unchanged', () => {
  const source = readFileSync(new URL('./firefox-transport.mjs', import.meta.url), 'utf8');
  const start = source.indexOf(' function options(params,keys)');
  const end = source.indexOf('\n // A request has one', start);
  assert.ok(start >= 0 && end > start);
  const parse = vm.runInNewContext('(() => {' + source.slice(start, end) + '; return fetchPatterns; })()',
    {unavailable() { throw Error('original-unavailable'); }});
  assert.throws(() => parse({patterns: [{urlPattern: '*', requestStage: 'Response', resourceType: 'Fetch'}]}),
    /Unsupported Firefox command options/);
  const h = fixture();
  h.trace.observeBrowserEvent({method: 'Network.requestWillBeSent', params: {requestId: 'native-' + secret,
    type: 'Fetch', request: {method: 'POST', url: back + '/matches/fixture/action'}}});
  const report = h.snapshot(); assert.ok(report.causal, 'Missing explicit observation namespace');
  assert.equal(causalEvents(report).filter(row => row.event === 'fetch-pause').length, 0);
  assert.equal(report.browserMetadata.events[0].networkType, 'Fetch');
  assert.equal(report.causal.nativeWireCommandIdentity, 'unknown');
});
