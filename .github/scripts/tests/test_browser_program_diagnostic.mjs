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
