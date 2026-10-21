import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import * as diagnostic from './browser-source-diagnostic.mjs';

// Public synthetic transport controls, not native/browser or causal evidence.
const helperUrl = new URL('./browser-source-diagnostic.mjs', import.meta.url);
const programUrl = new URL('./browser-start-recovery.mjs', import.meta.url);
const traceUrl = new URL('./browser-start-recovery-diagnostics.mjs', import.meta.url);
const reviewUrl = new URL('./review-start.mjs', import.meta.url);
const prefix = '::error title=Browser start recovery failure::';
const programSha = '70046c622e8f61f0b5554daffe9c1b13a9922b1a01896e801c2efa46b4cac4ee';
const helperSha = '13e1e1c8267bb7a65ca64784b5e039afd6debb00983b93b4adccec55e46a5a07';
const hash = value => createHash('sha256').update(value).digest('hex');
const plain = value => JSON.parse(JSON.stringify(value));
const importLine = "import { reportStartRecoveryFailure } from './browser-source-diagnostic.mjs';\n";
const phaseImportLine = "import { reportStartRecoveryFailure, reportStartRecoveryPhaseFailure } from './browser-source-diagnostic.mjs';\n";
const phasePrefix = '::error title=Browser start recovery phase failure::';
const phaseReportLine = '  try { reportStartRecoveryPhaseFailure(recoveryPhase, error); } catch { /* Preserve the original scenario result. */ }\n';
const originalReporter = "  }, process.env.MTG_FRONTEND_ORIGIN || 'http://127.0.0.1:15173', undefined,\n";
const snapshotReporter = "  }, process.env.MTG_FRONTEND_ORIGIN || 'http://127.0.0.1:15173', value => {\n"
  + '    startWithDroppedResponses.failureSnapshot = value;\n'
  + "    console.error('START_RECOVERY_RESPONSE_TRACE', JSON.stringify(value));\n  },\n";
const reportLine = '  try { reportStartRecoveryFailure(startWithDroppedResponses.failureSnapshot); } catch { /* Preserve the original scenario result. */ }\n';

function withoutKnownPhaseAdditions(source) {
  const checkpoints = ['lost-prepare', 'lost-recover', 'lost-verify',
    'reload-prepare', 'reload-pending', 'reload-replay', 'reload-verify',
    'click-prepare', 'click-pending', 'click-replay', 'click-verify',
    'legacy-prepare', 'legacy-pending', 'legacy-reload', 'legacy-review',
    'legacy-replay', 'legacy-verify'];
  // Only the authorized DIAG10 additions are projected for the older inverse.
  for (const [added, original] of [[phaseImportLine, importLine],
    ["let recoveryPhase = 'setup';\n", ''],
    ...checkpoints.map(phase => [`  recoveryPhase = '${phase}';\n`, '']),
    [phaseReportLine, '']]) {
    assert.equal(source.split(added).length - 1, 1, 'Exact known DIAG10 addition required');
    source = source.replace(added, original);
  }
  return source;
}

function project(value) {
  assert.equal(typeof diagnostic.startRecoveryFailureMetadata, 'function', 'Missing start-recovery projector');
  return diagnostic.startRecoveryFailureMetadata(value);
}

function row(overrides = {}) {
  return {method: 'OPTIONS', status: 200, commands: [
    {method: 'Fetch.continueResponse', acknowledgment: 'accepted', errorCode: null},
  ], omittedCommands: 0, ...overrides};
}

function snapshot(overrides = {}) {
  return {responses: [row()], omittedResponses: 0, pendingCommands: 0, activeCallbacks: 0,
    causal: {generationState: 'enabled', enableGeneration: 1}, ...overrides};
}

function expected(overrides = {}) {
  return {schema: 1, program: 'browser-start-recovery.mjs', scope: 'latest-existing-trace', available: true,
    responses: {retained: 1, omitted: 0, options: 1, post: 0, other: 0, http_200: 1, without_status: 0},
    commands: {retained: 1, omitted: 0, pending: 0, accepted: 1, error: 0},
    latest: {method: 'OPTIONS', status: 200, command: 'Fetch.continueResponse', ack: 'accepted', error_code: null},
    pending_commands: 0, active_callbacks: 0, control: {state: 'enabled', enable_generation: 1}, ...overrides};
}

function unavailable() {
  return expected({available: false, responses: null, commands: null, latest: null,
    pending_commands: null, active_callbacks: null, control: null});
}

function frame(text) {
  assert.ok(text.startsWith(`\n${prefix}`) && text.endsWith('\n'));
  const body = text.slice(`\n${prefix}`.length, -1);
  assert.doesNotMatch(body, /[\r\n]/);
  assert.ok(Buffer.byteLength(body) <= 768);
  return JSON.parse(body);
}

function phaseFrame(text) {
  assert.ok(text.startsWith(`\n${phasePrefix}`) && text.endsWith('\n'));
  const body = text.slice(`\n${phasePrefix}`.length, -1);
  assert.doesNotMatch(body, /[\r\n]/);
  assert.ok(Buffer.byteLength(body) <= 512);
  assert.doesNotMatch(body, /PRIVATE_|PUBLIC_SYNTHETIC|Idempotency|https?:|stack|body/);
  return JSON.parse(body);
}

function actualModule(url, globals, imports = []) {
  const original = readFileSync(url, 'utf8');
  let body = original;
  for (const line of imports) {
    assert.equal(body.split(line).length - 1, 1);
    body = body.replace(line, '');
  }
  body = body.replaceAll('import.meta.url', JSON.stringify(url.href)).replace(/^export /gm, '');
  assert.doesNotMatch(body, /^\s*(?:import|export)\s/m);
  const context = vm.createContext({URL, Buffer, TextEncoder, structuredClone, ...globals});
  vm.runInContext(body, context, {timeout: 1000});
  return context;
}

function actualReporter(writeSync) {
  const source = readFileSync(helperUrl, 'utf8');
  assert.equal(source.split("import {writeSync} from 'node:fs';").length - 1, 1);
  return actualModule(helperUrl, {writeSync, Error}, ["import {writeSync} from 'node:fs';"]);
}

test('OPTIONS-only trace cannot claim an observed or dropped POST', () => {
  assert.deepEqual(project(snapshot()), expected());
});

test('retained method status acknowledgment and numeric error are projected distinctly', () => {
  const input = snapshot({responses: [row(), row({method: 'POST', status: null, commands: [
    {method: 'Fetch.continueRequest', acknowledgment: 'pending', errorCode: null},
  ]}), row({method: 'other', status: 503, omittedCommands: 2, commands: [
    {method: 'Network.getRequestPostData', acknowledgment: 'accepted', errorCode: null},
    {method: 'Fetch.failRequest', acknowledgment: 'error', errorCode: -32602},
  ]})], omittedResponses: 3, pendingCommands: 1, activeCallbacks: 1});
  assert.deepEqual(project(input), expected({
    responses: {retained: 3, omitted: 3, options: 1, post: 1, other: 1, http_200: 1, without_status: 1},
    commands: {retained: 4, omitted: 2, pending: 1, accepted: 2, error: 1},
    latest: {method: 'other', status: 503, command: 'Fetch.failRequest', ack: 'error', error_code: -32602},
    pending_commands: 1, active_callbacks: 1,
  }));
});

test('unavailable snapshot is distinct from a valid empty retained trace', () => {
  for (const input of [undefined, null]) assert.deepEqual(project(input), unavailable());
  assert.deepEqual(project(snapshot({responses: []})), expected({
    responses: {retained: 0, omitted: 0, options: 0, post: 0, other: 0, http_200: 0, without_status: 0},
    commands: {retained: 0, omitted: 0, pending: 0, accepted: 0, error: 0}, latest: null,
  }));
  assert.equal(project(snapshot({responses: [row({commands: []})]})).latest.command, null);
});

test('existing control states and overflow generation remain enums and never invented phases', () => {
  for (const state of ['unknown', 'enable-pending', 'enabled', 'disable-pending', 'disabled']) {
    for (const generation of [0, 16, null]) {
      assert.deepEqual(project(snapshot({causal: {generationState: state, enableGeneration: generation}})).control,
        {state, enable_generation: generation});
    }
  }
});

test('malformed projected fields unknown categories and overflow suppress annotations', () => {
  for (const input of [[], false, 'PRIVATE_SYNTHETIC_VALUE', {}]) assert.equal(project(input), null);
  const changes = [
    d => { delete d.responses; }, d => { d.responses = {}; },
    d => { d.responses = Array.from({length: 17}, () => row()); },
    d => { d.omittedResponses = -1; }, d => { d.omittedResponses = '0'; },
    d => { d.pendingCommands = true; }, d => { d.activeCallbacks = 0.5; },
    d => { d.causal.generationState = 'PRIVATE_PHASE'; }, d => { d.causal.enableGeneration = 17; },
    d => { d.causal.enableGeneration = true; }, d => { delete d.causal; },
    d => { d.responses[0].method = 'GET'; }, d => { d.responses[0].status = '200'; },
    d => { d.responses[0].status = 600; }, d => { d.responses[0].status = 99; },
    d => { d.responses[0].commands = Array.from({length: 9}, () => row().commands[0]); },
    d => { d.responses[0].commands[0].method = 'PRIVATE_COMMAND'; },
    d => { d.responses[0].commands[0].acknowledgment = 'sent'; },
    d => { d.responses[0].commands[0].errorCode = 'PRIVATE_ERROR'; },
    d => { d.responses[0].commands[0].errorCode = Number.MAX_SAFE_INTEGER + 1; },
    d => { d.responses[0].omittedCommands = NaN; },
    d => { d.responses = [row({omittedCommands: Number.MAX_SAFE_INTEGER}), row({omittedCommands: 1})]; },
    d => { Object.defineProperty(d, 'responses', {get() { throw Error('PRIVATE_GETTER'); }}); },
  ];
  for (const change of changes) { const input = snapshot(); change(input); assert.equal(project(input), null); }
});

test('projection never reads private unprojected fields and preserves frozen input', () => {
  const input = snapshot();
  let reads = 0;
  const secret = () => { reads++; throw Error('PRIVATE_SYNTHETIC_UNPROJECTED'); };
  for (const object of [input, input.responses[0], input.responses[0].commands[0], input.causal]) {
    for (const key of ['requestId', 'networkId', 'url', 'body', 'key', 'name', 'message', 'stack', 'headers',
      'browserMetadata', 'requestSignals', 'responseError', 'cors', 'requestOrdinal', 'networkOrdinal']) {
      Object.defineProperty(object, key, {enumerable: true, get: secret});
    }
    Object.freeze(object);
  }
  Object.freeze(input.responses[0].commands); Object.freeze(input.responses);
  const output = project(input);
  assert.deepEqual(output, expected()); assert.equal(reads, 0);
  assert.notEqual(output.control, input.causal);
  assert.doesNotMatch(JSON.stringify(output), /PRIVATE_|requestId|networkId|https?:|stack|body|headers/);
});

test('maximum retained window and safe counters fit a finite 768-byte body', () => {
  const commands = Array.from({length: 8}, () => ({method: 'Fetch.continueResponse', acknowledgment: 'accepted', errorCode: null}));
  const output = project(snapshot({responses: Array.from({length: 16}, () => row({commands})),
    omittedResponses: Number.MAX_SAFE_INTEGER, pendingCommands: Number.MAX_SAFE_INTEGER,
    activeCallbacks: Number.MAX_SAFE_INTEGER}));
  assert.equal(output.responses.retained, 16); assert.equal(output.commands.retained, 128);
  assert.equal(output.commands.accepted, 128); assert.equal(output.responses.omitted, Number.MAX_SAFE_INTEGER);
  assert.ok(Buffer.byteLength(JSON.stringify(output)) <= 768);
});

test('actual reporter frames only finite records and never replaces a failure on sink error', () => {
  const writes = [];
  const reporter = actualReporter((fd, text) => writes.push([fd, text]));
  assert.equal(typeof reporter.reportStartRecoveryFailure, 'function', 'Missing start-recovery reporter');
  reporter.reportStartRecoveryFailure(snapshot());
  assert.deepEqual(writes.map(([fd]) => fd), [2]); assert.deepEqual(frame(writes[0][1]), expected());
  reporter.reportStartRecoveryFailure({}); assert.equal(writes.length, 1);
  reporter.reportStartRecoveryFailure(undefined); assert.deepEqual(frame(writes[1][1]), unavailable());
  const broken = actualReporter(() => { throw Error('PRIVATE_SYNTHETIC_SINK'); });
  assert.doesNotThrow(() => broken.reportStartRecoveryFailure(snapshot()));
});

test('exact caller inverse preserves all scenario bytes and the original diagnostic helper prefix', () => {
  const source = withoutKnownPhaseAdditions(readFileSync(programUrl, 'utf8'));
  for (const text of [importLine, snapshotReporter, reportLine]) assert.equal(source.split(text).length - 1, 1);
  const existingCatch = '  try { startWithDroppedResponses.trace?.reportFailure(); } catch { /* Preserve the original scenario result. */ }\n';
  assert.ok(source.includes(`${existingCatch}${reportLine}  throw error;`));
  assert.equal(hash(source.replace(importLine, '').replace(snapshotReporter, originalReporter).replace(reportLine, '')), programSha);
  const helper = readFileSync(helperUrl);
  // cd1's complete helper, including all old UI/drop exports, is an immutable prefix.
  assert.equal(hash(helper.subarray(0, 4163)), helperSha);
});

async function actualFailurePath(mode, sinkThrows = false) {
  const writes = [], commands = [], fetches = [], waits = [], evaluations = [], clicks = [], legacy = [];
  const phaseWrites = [];
  let intercept, reviewed = false, acknowledged = false, closed = 0;
  const primary = new Error(mode === 'command-error'
    ? '{"code":-32602,"message":"PRIVATE_SYNTHETIC_COMMAND_FAILURE"}' : 'PRIVATE_SYNTHETIC_PRIMARY');
  const console = {log() {}, error(label, text) { legacy.push([label, text]); }};
  const reporter = actualReporter((fd, text) => {
    if (text.startsWith(`\n${phasePrefix}`)) {
      assert.equal(fd, 2); phaseWrites.push(text);
    } else {
      assert.equal(fd, 2); writes.push(text);
    }
    if (sinkThrows) throw Error('PRIVATE_SYNTHETIC_SINK');
  });
  const trace = actualModule(traceUrl, {console});
  const review = actualModule(reviewUrl, {assert}, ["import assert from 'node:assert/strict';"]);
  const api = 'http://127.0.0.1:10199', frontend = 'http://127.0.0.1:15173';
  const browser = {
    async command(method, params) {
      commands.push([method, params]);
      if (mode === 'setup' && method === 'Network.enable') throw primary;
      if (mode === 'command-error' && method === 'Fetch.continueResponse') throw primary;
      if (method === 'Network.getRequestPostData') return {postData: '{"synthetic":true}'};
      return {};
    },
    onIntercept(fn) { intercept = fn; },
    async close() { closed++; },
    async evaluate(expression) {
      evaluations.push(expression);
      if (expression.includes('Interactive match support preflight')) return 'not certification';
      if (expression.startsWith('Boolean(document.querySelector("[aria-label=')) return reviewed;
      if (expression.endsWith('.checked')) return acknowledged;
      if (expression.endsWith('.disabled')) return !acknowledged;
      if (expression.endsWith('.click()')) acknowledged = true;
    },
    async waitFor(expression, timeout) {
      waits.push([expression, timeout]);
      if (expression.includes("'.battlefield'")) throw primary;
    },
    async click(label) {
      clicks.push(label);
      if (!reviewed) { reviewed = true; return; }
      assert.equal(acknowledged, true);
      const event = {requestId: 'PUBLIC_SYNTHETIC_FETCH', networkId: 'PUBLIC_SYNTHETIC_NETWORK',
        request: {method: mode === 'request' || mode === 'drop' ? 'POST' : 'OPTIONS',
          url: `${api}/matches/start`, headers: {'Idempotency-Key': 'a'.repeat(32)}},
        resourceType: 'Fetch', ...(mode === 'request' ? {} : {responseStatusCode: 200})};
      await intercept(event);
      if (mode !== 'drop') throw primary;
    },
  };
  let source = readFileSync(programUrl, 'utf8');
  for (const line of ["import assert from 'node:assert/strict';\n",
    "import { openBrowser } from './browser-driver.mjs';\n",
    "import { reviewStart } from './review-start.mjs';\n",
    "import { continueRequestForPostResponse, traceStartRecoveryResponses, createRequestSignalObserver } from './browser-start-recovery-diagnostics.mjs';\n"]) {
    assert.equal(source.split(line).length - 1, 1); source = source.replace(line, '');
  }
  assert.equal(source.split(phaseImportLine).length - 1, 1);
  source = source.replace(phaseImportLine, '');
  assert.doesNotMatch(source, /^\s*import\s/m);
  const context = {assert, Buffer, URL, console, process: {env: {MTG_BACKEND_ORIGIN: api, MTG_FRONTEND_ORIGIN: frontend}},
    openBrowser: async url => { assert.equal(url, `${frontend}/`); return browser; },
    reviewStart: review.reviewStart, continueRequestForPostResponse: trace.continueRequestForPostResponse,
    traceStartRecoveryResponses: trace.traceStartRecoveryResponses, createRequestSignalObserver: trace.createRequestSignalObserver,
    reportStartRecoveryFailure: reporter.reportStartRecoveryFailure,
    reportStartRecoveryPhaseFailure: reporter.reportStartRecoveryPhaseFailure,
    async fetch(url, options) {
      fetches.push([url, options]);
      if (url === `${api}/fixture/start-decks`) { assert.equal(options.method, 'POST'); return {json: async () => ({a: 1, b: 2})}; }
      assert.equal(url, `${api}/matches`); return {json: async () => []};
    },
  };
  const run = vm.runInNewContext(`(async () => {\n${source}\n})`, context, {timeout: 1000});
  await assert.rejects(run(), error => error === primary);
  assert.equal(closed, 1); assert.equal(writes.length, 1);
  assert.equal(phaseWrites.length, 1);
  assert.deepEqual(phaseFrame(phaseWrites[0]), {schema: 1, program: 'browser-start-recovery.mjs',
    phase: mode === 'setup' ? 'setup' : mode === 'drop' ? 'lost-recover' : 'lost-prepare',
    error_class: 'Error'});
  const output = frame(writes[0]);
  assert.doesNotMatch(writes[0], /PRIVATE_|PUBLIC_SYNTHETIC|Idempotency|https?:|stack|body/);
  if (mode === 'setup') {
    assert.deepEqual(output, unavailable()); assert.deepEqual(commands.map(([name]) => name), ['Network.enable']);
    assert.equal(fetches.length, 1); assert.equal(evaluations.length, 0); assert.equal(legacy.length, 0);
    return;
  }
  assert.equal(fetches.length, 2); assert.equal(evaluations.length, 7);
  assert.deepEqual(clicks, ['Start Best-of-3 Match', 'Start Best-of-3 Match']);
  assert.deepEqual(waits.map(([, budget]) => budget), mode === 'drop'
    ? [undefined, undefined, 45000, undefined, 75000] : [undefined, undefined, 45000, undefined]);
  assert.deepEqual(commands.slice(0, 5).map(([name]) => name),
    ['Network.enable', 'Page.enable', 'Runtime.enable', 'Page.reload', 'Fetch.enable']);
  assert.deepEqual(plain(commands[4][1]), {patterns: [{urlPattern: '*/matches/start', requestStage: 'Request'}]});
  const tail = mode === 'request' ? ['Fetch.continueRequest']
    : mode === 'drop' ? ['Network.getRequestPostData', 'Fetch.failRequest'] : ['Fetch.continueResponse'];
  assert.deepEqual(commands.slice(5).map(([name]) => name), tail);
  assert.equal(legacy.length, 1); assert.equal(legacy[0][0], 'START_RECOVERY_RESPONSE_TRACE');
  assert.deepEqual(output.control, {state: 'enabled', enable_generation: 1});
  assert.equal(output.responses.retained, 1); assert.equal(output.responses.omitted, 0);
  assert.equal(output.pending_commands, 0);
  assert.equal(output.active_callbacks, mode === 'command-error' ? 1 : 0);
  assert.deepEqual(output.latest, mode === 'request'
    ? {method: 'POST', status: null, command: 'Fetch.continueRequest', ack: 'accepted', error_code: null}
    : mode === 'drop' ? {method: 'POST', status: 200, command: 'Fetch.failRequest', ack: 'accepted', error_code: null}
      : {method: 'OPTIONS', status: 200, command: 'Fetch.continueResponse',
        ack: mode === 'command-error' ? 'error' : 'accepted', error_code: mode === 'command-error' ? -32602 : null});
}

test('actual program OPTIONS-only failure preserves legacy reporting and adds no transport or DOM reads', async () => {
  await actualFailurePath('options');
});

test('actual program POST request-stage continuation never invents response success or a drop', async () => {
  await actualFailurePath('request');
});

test('actual program captures a real synthetic POST-drop ACK and preserves the original exception after sink failure', async () => {
  await actualFailurePath('drop', true);
});

test('actual trace callback failure is annotated once with its existing numeric command error', async () => {
  await actualFailurePath('command-error');
});

test('actual program failure before trace creation emits unavailable instead of invented observations', async () => {
  await actualFailurePath('setup');
});

test('known phase inverse retains unrelated source changes for the original hash check', () => {
  const source = readFileSync(programUrl, 'utf8');
  const unrelated = '\n// PUBLIC_SYNTHETIC_UNRELATED_CHANGE\n';
  const projected = withoutKnownPhaseAdditions(source + unrelated);
  assert.ok(projected.endsWith(unrelated));
  assert.notEqual(hash(projected.replace(importLine, '').replace(snapshotReporter, originalReporter).replace(reportLine, '')), programSha);
});

test('known phase inverse rejects an unknown checkpoint instead of erasing it', () => {
  const source = readFileSync(programUrl, 'utf8');
  const changed = source.replace("  recoveryPhase = 'lost-recover';\n", "  recoveryPhase = 'unknown-checkpoint';\n");
  assert.notEqual(changed, source);
  assert.throws(() => withoutKnownPhaseAdditions(changed), /Exact known DIAG10 addition required/);
});
