import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import * as diagnostics from './browser-source-diagnostic.mjs';

// Synthetic protocol controls, not browser/native execution or causal proof.
const helperUrl = new URL('./browser-source-diagnostic.mjs', import.meta.url);
const uiUrl = new URL('./browser-ui-v2.mjs', import.meta.url);
const prefix = '::error title=Browser response drop failure::';
const oldUiSha = '96ba5fe35b9a020daff4aaebd10e2787e287be9619d8d161460b9a4ab6a68558';
const oldImport = "import { observeUiV2Failures } from './browser-source-diagnostic.mjs';";
const newImport = "import { observeUiV2Failures, reportUiV2DropFailure } from './browser-source-diagnostic.mjs';";
const reportCall = '      reportUiV2DropFailure(diagnostic);\n';

function project(input) {
  assert.equal(typeof diagnostics.uiV2DropFailureMetadata, 'function', 'Missing pure response-drop projector');
  return diagnostics.uiV2DropFailureMetadata(input);
}

function response(overrides = {}) {
  return {method: 'OPTIONS', status: 200, current: true, command: 'continue',
    continuation: 'ack', errorCode: null, ...overrides};
}

function snapshot(overrides = {}) {
  return {dropped: false, postResponseObserved: false, responses: [response()],
    omittedResponses: 0, canonical: {status: 'available', revision: 0}, ...overrides};
}

function expected(overrides = {}) {
  return {schema: 1, program: 'browser-ui-v2.mjs', stage: 'response-drop',
    dropped: false, post_response_observed: false,
    responses: {retained: 1, omitted: 0, options_200: 1, current_post_200: 0,
      continue_ack: 1, drop_ack: 0, error: 0, pending: 0},
    canonical: {status: 'available', revision: 0}, ...overrides};
}

function frameRecord(text) {
  assert.ok(text.startsWith(`\n${prefix}`) && text.endsWith('\n'));
  const body = text.slice(`\n${prefix}`.length, -1);
  assert.doesNotMatch(body, /[\r\n]/);
  assert.ok(Buffer.byteLength(body) <= 512);
  return JSON.parse(body);
}

// Execute the actual helper source; replace only module syntax and the native
// write boundary, not the projector or reporter implementations.
function reporting(writeSync) {
  assert.equal(typeof diagnostics.reportUiV2DropFailure, 'function', 'Missing finite annotation reporter');
  const source = readFileSync(helperUrl, 'utf8');
  const nativeImport = "import {writeSync} from 'node:fs';";
  assert.equal(source.split(nativeImport).length - 1, 1);
  const body = source.replace(nativeImport, '')
    .replaceAll('import.meta.url', JSON.stringify(helperUrl.href)).replace(/^export /gm, '');
  assert.doesNotMatch(body, /^\s*import\s/m);
  return vm.runInNewContext(`${body}\n({reportUiV2DropFailure});`, {URL, writeSync}, {timeout: 1000});
}

test('an OPTIONS continuation does not claim an observed or dropped POST', () => {
  assert.deepEqual(project(snapshot()), expected());
});

test('an acknowledged current POST drop retains observed flags and canonical revision', () => {
  const input = snapshot({dropped: true, postResponseObserved: true,
    responses: [response(), response({method: 'POST', command: 'drop'})],
    canonical: {status: 'available', revision: 1}});
  assert.deepEqual(project(input), expected({dropped: true, post_response_observed: true,
    responses: {retained: 2, omitted: 0, options_200: 1, current_post_200: 1,
      continue_ack: 1, drop_ack: 1, error: 0, pending: 0},
    canonical: {status: 'available', revision: 1}}));
});

test('retained response statuses and continuation outcomes have distinct counters', () => {
  const input = snapshot({dropped: true, postResponseObserved: true, responses: [
    response({continuation: 'error'}),
    response({method: 'POST', status: null, continuation: 'pending'}),
    response({method: 'GET', status: 204, current: false}),
    response({method: 'POST', command: 'drop'}),
  ], omittedResponses: 3});
  assert.deepEqual(project(input).responses, {retained: 4, omitted: 3,
    options_200: 1, current_post_200: 1, continue_ack: 1, drop_ack: 1, error: 1, pending: 1});
});

test('canonical availability states remain explicit and never invent revision zero', () => {
  for (const status of ['pending', 'unavailable', 'timed-out']) {
    assert.deepEqual(project(snapshot({canonical: {status, revision: null}})).canonical,
      {status, revision: null});
  }
  for (const revision of [0, Number.MAX_SAFE_INTEGER]) {
    assert.deepEqual(project(snapshot({canonical: {status: 'available', revision}})).canonical,
      {status: 'available', revision});
  }
});

test('missing, coerced, out-of-range and unknown projected operands suppress the record', () => {
  for (const input of [null, undefined, [], 'PRIVATE_SYNTHETIC_BODY']) assert.equal(project(input), null);
  const changes = [
    d => { delete d.dropped; }, d => { d.dropped = 'false'; },
    d => { d.postResponseObserved = 0; }, d => { delete d.responses; },
    d => { d.responses = {}; }, d => { d.responses = Array.from({length: 17}, () => response()); },
    d => { d.omittedResponses = -1; }, d => { d.omittedResponses = 0.5; },
    d => { d.omittedResponses = '0'; }, d => { d.omittedResponses = Number.MAX_SAFE_INTEGER + 1; },
    d => { delete d.canonical; }, d => { d.canonical.status = 'PRIVATE_STATUS'; },
    d => { d.canonical.revision = null; }, d => { d.canonical.revision = -1; },
    d => { d.canonical.revision = Number.MAX_SAFE_INTEGER + 1; },
    d => { d.canonical = {status: 'unavailable', revision: 0}; },
    d => { d.responses[0].method = 'PRIVATE_METHOD'; },
    d => { d.responses[0].current = 'true'; }, d => { d.responses[0].status = '200'; },
    d => { d.responses[0].status = 99; }, d => { d.responses[0].status = 600; },
    d => { d.responses[0].status = NaN; }, d => { d.responses[0].command = 'PRIVATE_COMMAND'; },
    d => { d.responses[0].continuation = 'PRIVATE_CONTINUATION'; },
    d => { Object.defineProperty(d, 'canonical', {get() { throw new Error('SYNTHETIC_GETTER'); }}); },
  ];
  for (const change of changes) {
    const input = snapshot(); change(input);
    assert.equal(project(input), null);
  }
});

test('unprojected names URLs IDs messages stacks and bodies are neither read nor exported', () => {
  const input = snapshot();
  let reads = 0;
  for (const record of [input, input.responses[0], input.canonical]) {
    for (const key of ['url', 'id', 'name', 'message', 'stack', 'body', 'state', 'request', 'headers']) {
      Object.defineProperty(record, key, {enumerable: true, get() {
        reads++; throw new Error('PRIVATE_SYNTHETIC_UNPROJECTED');
      }});
    }
  }
  input.requestLifecycle = {message: 'PRIVATE_SYNTHETIC_LIFECYCLE'};
  input.requestLifecycleFinal = {url: 'https://private.invalid/synthetic'};
  input.program = 'PRIVATE_SYNTHETIC_PROGRAM';
  const output = project(input);
  assert.deepEqual(output, expected());
  assert.equal(reads, 0);
  assert.doesNotMatch(JSON.stringify(output), /PRIVATE_|https:|private\.invalid/);
});

test('projection preserves its frozen input and returns independent nested records', () => {
  const input = snapshot();
  const before = JSON.stringify(input);
  Object.freeze(input.responses[0]); Object.freeze(input.responses);
  Object.freeze(input.canonical); Object.freeze(input);
  const output = project(input);
  assert.deepEqual(output, expected());
  assert.equal(JSON.stringify(input), before);
  assert.notEqual(output.canonical, input.canonical);
  assert.notEqual(output.responses, input.responses);
});

test('the maximum retained slice and safe scalar counters remain below 512 annotation bytes', () => {
  const output = project(snapshot({responses: Array.from({length: 16}, () => response()),
    omittedResponses: Number.MAX_SAFE_INTEGER,
    canonical: {status: 'available', revision: Number.MAX_SAFE_INTEGER}}));
  assert.deepEqual(output, expected({responses: {retained: 16, omitted: Number.MAX_SAFE_INTEGER,
    options_200: 16, current_post_200: 0, continue_ack: 16, drop_ack: 0, error: 0, pending: 0},
    canonical: {status: 'available', revision: Number.MAX_SAFE_INTEGER}}));
  assert.ok(Buffer.byteLength(JSON.stringify(output)) <= 512);
});

test('the actual reporter frames one finite record suppresses invalid input and tolerates sink failure', () => {
  const writes = [];
  const {reportUiV2DropFailure} = reporting((fd, text) => { writes.push([fd, text]); });
  reportUiV2DropFailure(snapshot());
  assert.deepEqual(writes.map(([fd]) => fd), [2]);
  assert.deepEqual(frameRecord(writes[0][1]), expected());
  reportUiV2DropFailure(null);
  assert.equal(writes.length, 1);
  const broken = reporting(() => { throw new Error('PRIVATE_SYNTHETIC_SINK'); });
  assert.doesNotThrow(() => broken.reportUiV2DropFailure(snapshot()));
});

test('caller wiring changes only its existing diagnostic import and one failure-only report call', () => {
  const source = readFileSync(uiUrl, 'utf8');
  assert.equal(source.split(newImport).length - 1, 1);
  assert.equal(source.split(reportCall).length - 1, 1);
  assert.ok(source.indexOf(reportCall) > source.indexOf('diagnostic.requestLifecycleFinal='));
  assert.ok(source.indexOf(reportCall) < source.indexOf("console.error('DROP_RESPONSE_TRACE'"));
  const restored = source.replace(newImport, oldImport).replace(reportCall, '');
  assert.equal(createHash('sha256').update(restored).digest('hex'), oldUiSha);
});

async function actualFailurePath(withPost, sinkThrows) {
  const writes = [], commands = [], reads = [], timerBudgets = [], legacy = [];
  const originalError = new Error('PRIVATE_SYNTHETIC_CLICK_FAILURE');
  const {reportUiV2DropFailure} = reporting((fd, text) => {
    assert.equal(fd, 2); writes.push(text);
    if (sinkThrows) throw new Error('PRIVATE_SYNTHETIC_SINK');
  });
  const source = readFileSync(uiUrl, 'utf8');
  const start = source.indexOf('async function recoverDroppedResponse(s) {');
  const end = source.indexOf('\ntry {\n  recoverDroppedResponse.requestSignals=', start);
  assert.ok(start >= 0 && end > start);
  let onIntercept;
  const api = 'http://127.0.0.1:10199', origin = 'http://127.0.0.1:15173';
  const fixture = {id: 'synthetic-owned-match'};
  const actionUrl = `${api}/matches/${fixture.id}/action`;
  const command = async (method, params) => { commands.push([method, params]); return {}; };
  const b = {supportsFetchResourceTypeFilter: true, onIntercept(fn) { onIntercept = fn; },
    async browserIdentity() { reads.push('runtime'); return {product: 'SyntheticBrowser/1', protocolVersion: '1'}; }};
  const context = {api, origin, b, command, reportUiV2DropFailure, AbortController,
    continueRequestForPostResponse: async () => false,
    traceStartRecoveryResponses(_command, handler, _origin, collect) {
      const trace = async event => handler(event, command);
      trace.observeControl = () => {};
      trace.reportFailure = () => { reads.push('observer'); collect({}); };
      trace.captureFinal = () => { reads.push('final'); return {private: 'PRIVATE_SYNTHETIC_FINAL'}; };
      return trace;
    },
    async click(label) {
      assert.equal(label, 'Play Land Forest');
      await onIntercept({requestId: 'synthetic-options', request: {method: 'OPTIONS', url: actionUrl},
        responseStatusCode: 200, responseHeaders: [{name: 'access-control-allow-origin', value: origin}]});
      if (withPost) await onIntercept({requestId: 'synthetic-post', request: {method: 'POST', url: actionUrl},
        responseStatusCode: 200});
      throw originalError;
    },
    async evaluate() { reads.push('ui'); return {}; },
    async fetch(url, options) {
      assert.equal(url, `${api}/matches/${fixture.id}`); assert.equal(options.method, 'GET');
      reads.push('canonical'); return {ok: true, json: async () => ({revision: withPost ? 1 : 0})};
    },
    setTimeout(_callback, milliseconds) { timerBudgets.push(milliseconds); return 1; },
    clearTimeout() {},
    console: {error(label) { legacy.push(label); }},
  };
  const recover = vm.runInNewContext(`(${source.slice(start, end)})`, context, {timeout: 1000});
  await assert.rejects(recover(fixture), error => error === originalError);
  assert.equal(writes.length, 1);
  const record = frameRecord(writes[0]);
  const wanted = withPost ? expected({dropped: true, post_response_observed: true,
    responses: {retained: 2, omitted: 0, options_200: 1, current_post_200: 1,
      continue_ack: 1, drop_ack: 1, error: 0, pending: 0},
    canonical: {status: 'available', revision: 1}}) : expected();
  assert.deepEqual(record, wanted);
  assert.deepEqual(commands.map(([method]) => method), withPost
    ? ['Network.enable', 'Fetch.enable', 'Fetch.continueResponse', 'Fetch.failRequest', 'Fetch.disable']
    : ['Network.enable', 'Fetch.enable', 'Fetch.continueResponse', 'Fetch.disable']);
  assert.deepEqual(reads, ['observer', 'ui', 'canonical', 'runtime', 'final']);
  assert.deepEqual(timerBudgets, [1000]);
  assert.deepEqual(legacy, ['DROP_RESPONSE_TRACE']);
}

test('the actual failed recovery path projects its existing OPTIONS-only collector without new IO', async () => {
  await actualFailurePath(false, false);
});

test('the actual failed path retains an acknowledged POST drop and rethrows its original error after sink failure', async () => {
  await actualFailurePath(true, true);
});
