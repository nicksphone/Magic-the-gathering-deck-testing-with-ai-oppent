import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import * as diagnostics from './browser-source-diagnostic.mjs';

const source = readFileSync(new URL('./browser-start-recovery.mjs', import.meta.url), 'utf8');
const secret = 'PRIVATE_MESSAGE_STACK_URL_ID_PAYLOAD';
const phases = ['setup', 'lost-prepare', 'lost-recover', 'lost-verify',
  'reload-prepare', 'reload-pending', 'reload-replay', 'reload-verify',
  'click-prepare', 'click-pending', 'click-replay', 'click-verify',
  'legacy-prepare', 'legacy-pending', 'legacy-reload', 'legacy-review',
  'legacy-replay', 'legacy-verify'];
const expected = (phase, errorClass = 'Error') => ({schema: 1,
  program: 'browser-start-recovery.mjs', phase, error_class: errorClass});

function required(name) {
  assert.equal(typeof diagnostics[name], 'function', `Missing actual helper export ${name}`);
  return diagnostics[name];
}

function reporter(writeSync) {
  const actual = required('reportStartRecoveryPhaseFailure');
  return vm.runInNewContext(`(${actual.toString()})`, {
    startRecoveryPhaseFailureMetadata: required('startRecoveryPhaseFailureMetadata'), writeSync,
  });
}

const pending = `  await waitFor("document.querySelector('[role=alert]') && !document.body.innerText.includes('Match operation pending') && !!localStorage.getItem('mtg.pendingStart')");`;
const lostBoard = `  await waitFor("document.querySelector('.battlefield') && !document.body.innerText.includes('Match operation pending') && !localStorage.getItem('mtg.pendingStart')", 75000);`;
const disable = "  await observeFetchControl('Fetch.disable');";
const resume = '  await resumeRequestCapture();';
const sites = [
  ['setup', `  startWithDroppedResponses.requestSignals = createRequestSignalObserver(process.env.MTG_FRONTEND_ORIGIN || 'http://127.0.0.1:15173', backend);`],
  ['lost-prepare', '  await selectDecks();', 0],
  ['lost-recover', lostBoard],
  ['lost-verify', disable, 0],
  ['reload-prepare', '  await selectDecks();', 1],
  ['reload-pending', pending, 0],
  ['reload-replay', resume, 0],
  ['reload-verify', disable, 2],
  ['click-prepare', '  await selectDecks();', 2],
  ['click-pending', pending, 1],
  ['click-replay', resume, 1],
  ['click-verify', disable, 4],
  ['legacy-prepare', '  await selectDecks();', 3],
  ['legacy-pending', pending, 2],
  ['legacy-reload', resume, 2],
  ['legacy-review', '  const recoverLabel = await reviewStart(browser, { recover: true });'],
  ['legacy-replay', '  await click(recoverLabel);'],
  ['legacy-verify', disable, 6],
];

function callerSite([phase, line, ordinal = 0]) {
  // Read declarations/checkpoints from the actual caller, not a fixture-only cursor.
  const declaration = source.match(/^let ([A-Za-z_$][\w$]*)\s*=\s*(['"])setup\2;\s*$/m);
  assert.ok(declaration, 'Actual caller needs its own outer setup-initialized phase cursor');
  let index = -1;
  for (let i = 0; i <= ordinal; i++) index = source.indexOf(line, index + 1);
  assert.ok(index >= 0, `Retain original caller site ${phase}/${ordinal}`);
  let assignment = '';
  if (phase !== 'setup') {
    const prefix = source.slice(0, index).trimEnd();
    assignment = prefix.slice(prefix.lastIndexOf('\n') + 1);
    const match = assignment.match(/^\s*([A-Za-z_$][\w$]*)\s*=\s*(['"])([a-z-]+)\2;\s*$/);
    assert.ok(match, `Actual ${phase} site must assign a literal immediately before its original operation`);
    assert.equal(match[1], declaration[1]);
    assert.equal(match[3], phase);
  }
  const catchStart = source.lastIndexOf('} catch (error) {');
  assert.ok(catchStart > index, 'Use the actual existing outer catch/finally');
  return {phase, declaration: declaration[0], body: `${assignment}\n${line}`,
    tail: source.slice(catchStart)};
}

async function failActualSite(site, {sinkThrows = false} = {}) {
  const selected = callerSite(site);
  const project = required('startRecoveryPhaseFailureMetadata');
  const primary = new TypeError(secret);
  const stale = {fixtureOnly: secret};
  const reports = [], oldSnapshots = [];
  let closeCount = 0;
  const start = () => {};
  start.trace = {reportFailure() { start.failureSnapshot = stale; }};
  const fail = async () => { throw primary; };
  const context = {process: {env: {}}, backend: 'http://fixture.invalid', browser: {},
    startWithDroppedResponses: start, selectDecks: fail, waitFor: fail,
    matchIds: fail, reviewStart: fail,
    observeFetchControl: fail, resumeRequestCapture: fail, click: fail,
    recoverLabel: 'fixture-only-control',
    createRequestSignalObserver() { throw primary; },
    reportStartRecoveryFailure(value) { oldSnapshots.push(value); },
    reportStartRecoveryPhaseFailure(phase, error) {
      assert.equal(error, primary);
      reports.push(project(phase, error));
      if (sinkThrows) throw new Error(secret);
    },
    async close() { closeCount++; },
  };
  const program = `(async () => {${selected.declaration}\ntry {${selected.body}\n${selected.tail}\n})()`;
  await assert.rejects(vm.runInNewContext(program, context), error => error === primary);
  assert.equal(closeCount, 1, 'Actual existing finally must still close once');
  assert.deepEqual(reports, [expected(selected.phase, 'TypeError')]);
  assert.deepEqual(oldSnapshots, [stale], 'Latest trace remains separately scoped, not the current phase oracle');
}

test('actual projector admits only the caller checkpoint enum and exact four-field schema', () => {
  const project = required('startRecoveryPhaseFailureMetadata');
  for (const phase of phases) assert.deepEqual(project(phase, new Error(secret)), expected(phase));
});

test('actual projector preserves a finite error class, not an arbitrary name or body', () => {
  const project = required('startRecoveryPhaseFailureMetadata');
  for (const Constructor of [Error, TypeError, RangeError, ReferenceError, SyntaxError, URIError, EvalError]) {
    assert.deepEqual(project('lost-verify', new Constructor(secret)), expected('lost-verify', Constructor.name));
  }
  const assertion = new Error(secret); assertion.name = 'AssertionError';
  assert.deepEqual(project('lost-verify', assertion), expected('lost-verify', 'AssertionError'));
  const other = new Error(secret); other.name = secret;
  for (const value of [other, null, undefined, {}, secret]) {
    assert.deepEqual(project('lost-verify', value), expected('lost-verify', 'other'));
  }
});

test('invalid or secret-like phases reject before reading or coercing the error', () => {
  const project = required('startRecoveryPhaseFailureMetadata');
  const error = new Error(secret);
  let reads = 0;
  Object.defineProperty(error, 'name', {get() { reads++; throw new Error(secret); }});
  const forbidden = {toString() { throw new Error(secret); }};
  for (const phase of ['', 'lost', 'setup\n' + secret, 'https://private.invalid/',
    'setup/' + secret, 'a'.repeat(81), 0, true, null, undefined, forbidden]) {
    assert.equal(project(phase, error), null);
  }
  assert.equal(reads, 0);
});

test('error name is read once and message stack serialization and coercion are never read', () => {
  const project = required('startRecoveryPhaseFailureMetadata');
  const error = new Error(secret);
  void error.stack; // Materialize the native fixture stack before installing poison getters.
  let names = 0;
  Object.defineProperty(error, 'name', {get() { assert.equal(++names, 1); return 'TypeError'; }});
  for (const key of ['message', 'stack', 'toJSON', 'toString', 'payload', 'url', 'id']) {
    Object.defineProperty(error, key, {get() { throw new Error(`Forbidden ${key} ${secret}`); }});
  }
  assert.deepEqual(project('click-verify', error), expected('click-verify', 'TypeError'));
  assert.equal(names, 1);
});

test('throwing error-name getters retain a safe other classification', () => {
  const project = required('startRecoveryPhaseFailureMetadata');
  const error = new Error(secret);
  Object.defineProperty(error, 'name', {get() { throw new Error(secret); }});
  assert.deepEqual(project('legacy-review', error), expected('legacy-review', 'other'));
});

test('actual reporter emits exactly one bounded typed annotation and no private content', () => {
  const writes = [];
  const report = reporter((fd, text) => writes.push([fd, text]));
  report('reload-replay', new TypeError(secret));
  assert.equal(writes.length, 1);
  assert.equal(writes[0][0], 2);
  const prefix = '\n::error title=Browser start recovery phase failure::';
  assert.ok(writes[0][1].startsWith(prefix));
  assert.ok(writes[0][1].endsWith('\n'));
  const body = writes[0][1].slice(prefix.length, -1);
  assert.ok(Buffer.byteLength(body) <= 512);
  const metadata = JSON.parse(body);
  assert.deepEqual(metadata, expected('reload-replay', 'TypeError'));
  assert.equal(writes[0][1], prefix + JSON.stringify(metadata) + '\n');
  assert.equal(writes[0][1].includes(secret), false);
});

test('actual reporter is quiet on invalid phase and cannot replace a primary failure on sink error', () => {
  let writes = 0;
  const report = reporter(() => { writes++; throw new Error(secret); });
  assert.doesNotThrow(() => report(secret, new Error(secret)));
  assert.equal(writes, 0);
  assert.doesNotThrow(() => report('reload-verify', new Error(secret)));
  assert.equal(writes, 1);
});

test('all existing caller blocks have literal current checkpoints and the actual reporter import', () => {
  assert.match(source, /import\s*\{[^}]*\breportStartRecoveryPhaseFailure\b[^}]*\}\s*from\s*['"]\.\/browser-source-diagnostic\.mjs['"]/);
  assert.deepEqual([...new Set(sites.map(site => site[0]))], phases);
  for (const site of sites) callerSite(site);
});

test('actual caller checkpoints and catch report the current primary error despite a stale trace', async () => {
  for (const site of sites) await failActualSite(site);
});

test('actual caller catch preserves the original error and finally when the phase reporter fails', async () => {
  await failActualSite(sites.find(site => site[0] === 'legacy-replay'), {sinkThrows: true});
});
