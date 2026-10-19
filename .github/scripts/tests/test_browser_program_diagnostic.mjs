import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import test from 'node:test';

// Inert shell contracts only: no browser, API, database, or game is started.
const root = fileURLToPath(new URL('../../../', import.meta.url));
const helper = path.join(root, 'frontend/tests/browser-program-diagnostic.sh');
const program = 'browser-ui-v2.mjs';
const prefix = '::error title=Browser program failure::';
const bootstrapPrefix = '::error title=Browser bootstrap failure::';
const environment = {PATH: '/usr/bin:/bin', LANG: 'C.UTF-8', GITHUB_ACTIONS: 'true'};

function shell(body, args, extra = {}) {
  return spawnSync('/bin/bash', ['--noprofile', '--norc', '-c',
    `set -euo pipefail\nsource "$1"\nshift\n${body}`, 'protocol-test', helper, ...args],
  {encoding: 'utf8', timeout: 5000, env: {...environment, ...extra}});
}

function run(label, command, extra) {
  return shell('run_browser_program "$@"', [label, ...command], extra);
}

function annotations(result, expectedPrefix = prefix) {
  return result.stderr.split('\n').filter(line => line.startsWith(expectedPrefix))
    .map(line => JSON.parse(line.slice(expectedPrefix.length)));
}

function assertFailureStreams(result, record, stdout = '', stderr = '', expectedPrefix = prefix) {
  const marker = `\n${expectedPrefix}`;
  const start = result.stderr.lastIndexOf(marker);
  assert.ok(start >= 0, 'A failure annotation requires its own framing newline');
  const frame = result.stderr.slice(start);
  assert.ok(frame.endsWith('\n'));
  assert.deepEqual(JSON.parse(frame.slice(marker.length, -1)), record);
  assert.equal(result.stdout, stdout);
  assert.equal(result.stderr, `${stderr}${frame}`);
}

test('successful commands preserve both streams without a failure annotation', () => {
  const result = run(program, ['/bin/bash', '-c', 'printf out; printf err >&2']);
  assert.equal(result.status, 0);
  assert.equal(result.signal, null);
  assert.equal(result.stdout, 'out');
  assert.equal(result.stderr, 'err');
  assert.deepEqual(annotations(result), []);
});

test('failed commands execute once and retain their original exit status', () => {
  const result = run(program, ['/bin/bash', '-c', 'printf called-once; exit 42']);
  assert.equal(result.status, 42);
  assertFailureStreams(result, {schema: 1, program, exit_code: 42}, 'called-once');
});

test('numeric timeout status is forwarded without claiming an actual deadline test', () => {
  const result = run(program, ['/bin/bash', '-c', 'exit 124']);
  assert.equal(result.status, 124);
  assertFailureStreams(result, {schema: 1, program, exit_code: 124});
});

test('annotations exclude child error bodies while preserving the original stream', () => {
  const detail = 'UNREVIEWED-SYNTHETIC-DETAIL';
  const result = run(program, ['/bin/bash', '-c', 'printf "%s\\n" "$1" >&2; exit 7', 'child', detail]);
  assert.equal(result.status, 7);
  assertFailureStreams(result, {schema: 1, program, exit_code: 7}, '', `${detail}\n`);
  assert.ok(!JSON.stringify(annotations(result)).includes(detail));
});

test('arguments and environment are forwarded without evaluation', () => {
  const argument = 'literal;$(printf MUST_NOT_RUN)';
  const result = run(program, ['/bin/bash', '-c', 'printf "%s|%s" "$1" "$PROBE_FLAG"', 'child', argument],
    {PROBE_FLAG: 'retained'});
  assert.equal(result.status, 0);
  assert.equal(result.stdout, `${argument}|retained`);
  assert.equal(result.stderr, '');
});

for (const [kind, label] of [
  ['newline', 'browser-ui-v2.mjs\nPRIVATE'],
  ['path', '../browser-ui-v2.mjs'],
  ['long', 'x'.repeat(81)],
  ['empty', ''],
  ['unregistered', 'browser-protocol-never-registered.mjs'],
]) {
  test(`invalid ${kind} labels are rejected before running the command`, () => {
    const result = run(label, ['/bin/bash', '-c', 'printf MUST_NOT_EXECUTE']);
    assert.equal(result.status, 2);
    assert.equal(result.stdout, '');
    assert.equal(result.stderr, '');
  });
}

test('bootstrap errors expose only the source line and original numeric status', () => {
  const result = shell('report_browser_bootstrap_failure "$1" "$2"\nexit "$1"', ['17', '84']);
  assert.equal(result.status, 17);
  assertFailureStreams(result, {schema: 1, program: 'bootstrap', source_line: 84, exit_code: 17},
    '', '', bootstrapPrefix);
});

test('malformed bootstrap locations are rejected without printing their contents', () => {
  const result = shell('report_browser_bootstrap_failure "$1" "$2"', ['17', '84\nPRIVATE']);
  assert.equal(result.status, 2);
  assert.equal(result.stdout, '');
  assert.equal(result.stderr, '');
});

const sourceHelper = new URL('../../../frontend/tests/browser-source-diagnostic.mjs', import.meta.url);
const uiSource = new URL('../../../frontend/tests/browser-ui-v2.mjs', import.meta.url).href;
const sourcePrefix = '::error title=Browser source failure::';
const sourceDiagnostic = () => import(sourceHelper);
const locatedError = (frames, message = 'PRIVATE_ERROR_BODY') => {
  const error = new Error(message);
  error.stack = `${String(error)}\n${frames.join('\n')}`;
  return error;
};
const sourceRecord = (source_line = null, error_class = 'Error') =>
  ({schema: 1, program, source_line, error_class});

test('source metadata selects the first exact public program frame', async () => {
  const {uiV2FailureMetadata} = await sourceDiagnostic();
  const error = locatedError([`    at run (${uiSource}:31:9)`, `    at ${uiSource}:42:2`]);
  assert.deepEqual(uiV2FailureMetadata(error), sourceRecord(31));
});

test('foreign source paths and URLs never become failure metadata', async () => {
  const {uiV2FailureMetadata} = await sourceDiagnostic();
  const result = uiV2FailureMetadata(locatedError([
    '    at file:///PRIVATE_ROOT/browser-ui-v2.mjs:77:8',
    '    at https://PRIVATE_HOST/browser-ui-v2.mjs:78:9',
  ]));
  assert.deepEqual(result, sourceRecord());
  assert.doesNotMatch(JSON.stringify(result), /PRIVATE_|file:|https:/);
});

test('frames forged inside a multiline error message are excluded', async () => {
  const {uiV2FailureMetadata} = await sourceDiagnostic();
  const error = locatedError([`    at ${uiSource}:32:4`],
    `PRIVATE_ERROR\n    at ${uiSource}:999:1`);
  assert.deepEqual(uiV2FailureMetadata(error), sourceRecord(32));
});

test('invalid public source coordinates remain unavailable', async () => {
  const {uiV2FailureMetadata} = await sourceDiagnostic();
  for (const line of ['0', '-1', '9999999', 'PRIVATE_LINE']) {
    assert.deepEqual(uiV2FailureMetadata(locatedError([`    at ${uiSource}:${line}:1`])), sourceRecord());
  }
});

test('unknown exception labels cannot publish arbitrary text', async () => {
  const {uiV2FailureMetadata} = await sourceDiagnostic();
  const error = locatedError([`    at ${uiSource}:33:1`]);
  error.name = 'PRIVATE_CLASS';
  error.stack = `${String(error)}\n    at ${uiSource}:33:1`;
  assert.deepEqual(uiV2FailureMetadata(error), sourceRecord(33, 'other'));
  assert.deepEqual(uiV2FailureMetadata('PRIVATE_NON_ERROR'), sourceRecord(null, 'other'));
});

test('untrusted stack values and stale headers fail closed without throwing', async () => {
  const {uiV2FailureMetadata} = await sourceDiagnostic();
  for (const stack of [null, {}, 'x'.repeat(131073)]) {
    const error = new Error('PRIVATE_ERROR');
    error.stack = stack;
    assert.deepEqual(uiV2FailureMetadata(error), sourceRecord());
  }
  const stale = locatedError([`    at ${uiSource}:36:1`]);
  stale.message = 'CHANGED_PRIVATE_MESSAGE';
  assert.deepEqual(uiV2FailureMetadata(stale), sourceRecord());
  const getter = new Error('PRIVATE_GETTER');
  Object.defineProperty(getter, 'stack', {get() { throw new Error('PRIVATE_STACK_GETTER'); }});
  assert.deepEqual(uiV2FailureMetadata(getter), sourceRecord());
  Object.defineProperty(getter, 'name', {get() { throw new Error('PRIVATE_NAME_GETTER'); }});
  assert.deepEqual(uiV2FailureMetadata(getter), sourceRecord(null, 'other'));
});

test('native assertion errors retain their finite category', async () => {
  const {uiV2FailureMetadata} = await sourceDiagnostic();
  let error;
  try { assert.fail('PRIVATE_ASSERTION'); } catch (failure) { error = failure; }
  error.stack += `\n    at ${uiSource}:34:3`;
  assert.deepEqual(uiV2FailureMetadata(error), sourceRecord(34, 'AssertionError'));
});

test('importing the source helper does not install listeners or emit output', async () => {
  await sourceDiagnostic();
  const result = spawnSync(process.execPath, ['--input-type=module', '-e',
    `const before=process.listenerCount('uncaughtExceptionMonitor'); await import(${JSON.stringify(sourceHelper.href)}); if(process.listenerCount('uncaughtExceptionMonitor')!==before)process.exit(99);`],
  {encoding: 'utf8', timeout: 5000, env: environment});
  assert.equal(result.status, 0, result.stderr);
  assert.equal(result.stdout, '');
  assert.equal(result.stderr, '');
});

test('the monitor adds only its typed frame while preserving uncaught exit and streams', async () => {
  await sourceDiagnostic();
  const script = `import {observeUiV2Failures} from ${JSON.stringify(sourceHelper.href)};
if(process.env.REGISTER==='1')observeUiV2Failures();
process.stdout.write('original-output');
const error=new Error('PRIVATE_UNCAUGHT_BODY');
error.stack=String(error)+'\\n    at '+${JSON.stringify(uiSource)}+':35:7';
throw error;`;
  const child = REGISTER => spawnSync(process.execPath, ['--input-type=module', '-e', script],
    {encoding: 'utf8', timeout: 5000, env: {...environment, REGISTER}});
  const baseline = child('0'), observed = child('1');
  assert.equal(baseline.status, 1);
  assert.equal(observed.status, baseline.status);
  assert.equal(observed.signal, baseline.signal);
  assert.equal(observed.stdout, baseline.stdout);
  const frames = observed.stderr.split('\n').filter(line => line.startsWith(sourcePrefix));
  assert.equal(frames.length, 1);
  assert.deepEqual(JSON.parse(frames[0].slice(sourcePrefix.length)), sourceRecord(35));
  assert.equal(observed.stderr.replace(`\n${frames[0]}\n`, ''), baseline.stderr);
});
