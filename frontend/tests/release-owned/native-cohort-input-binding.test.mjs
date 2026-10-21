import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import vm from 'node:vm';

// PROTOCOL ONLY: actual public input bytes and the actual isolated guard block.
// Selection, child creation, application imports and real runner reads never run.
const launcher = readFileSync(new URL('./run-current-built-acceptance.mjs', import.meta.url), 'utf8');
const cohortBytes = readFileSync(new URL('./fixtures/current-built-cohort.json', import.meta.url));
const recoveryBytes = readFileSync(new URL('./fixtures/current-built-recovery-fixtures.json', import.meta.url));
const lengthAnchor = 'assert.equal(cohort.length,40);';
const anchor = launcher.indexOf(lengthAnchor);
const end = launcher.indexOf('process.env.MTG_CDP_DIAGNOSTIC_DIR=', anchor + lengthAnchor.length);
assert.ok(anchor >= 0 && end > anchor + lengthAnchor.length,
  'Actual cohort-length and diagnostic-assignment extraction boundaries required');
const actualGuard = launcher.slice(anchor + lengthAnchor.length, end);
const project = '/protocol/owned', root = project + '/source';
const readsInOrder = [
  path.join(project, 'runner/cohort.json'),
  path.join(root, 'frontend/tests/release-owned/fixtures/current-built-cohort.json'),
  path.join(project, 'runner/recovery-fixtures.json'),
  path.join(root, 'frontend/tests/release-owned/fixtures/current-built-recovery-fixtures.json'),
];
const digest = bytes => createHash('sha256').update(bytes).digest('hex');

async function observe(vendor, mode, {badCohort = false, badRecovery = false} = {}) {
  const appendSpace = bytes => Buffer.concat([Buffer.from(bytes), Buffer.from(' ')]);
  // Separate runner/source copies: only runner bytes change, never source facts.
  const files = new Map([
    [readsInOrder[0], badCohort ? appendSpace(cohortBytes) : Buffer.from(cohortBytes)],
    [readsInOrder[1], Buffer.from(cohortBytes)],
    [readsInOrder[2], badRecovery ? appendSpace(recoveryBytes) : Buffer.from(recoveryBytes)],
    [readsInOrder[3], Buffer.from(recoveryBytes)],
  ]);
  const reads = [];
  const context = vm.createContext({assert, path, project, root, digest,
    browserVendor: vendor, strictNative: mode === '0',
    async readFile(file) {
      const bytes = files.get(file);
      if (!bytes) throw new Error('Inert cohort fixture rejected an undeclared read');
      reads.push(file);
      return Buffer.from(bytes);
    },
  });
  let error;
  try {
    await new vm.Script(`(async () => {${actualGuard}})()`,
      {filename: 'actual-cohort-input-guard.protocol.mjs'})
      .runInContext(context, {timeout: 1000});
  } catch (caught) { error = caught; }
  return {reads, error};
}

async function acceptsExactBytes(vendor) {
  const result = await observe(vendor, '0');
  assert.equal(result.error, undefined);
  assert.deepEqual(result.reads, readsInOrder,
    'Native admission must compare both actual runner/source byte pairs');
}

async function rejectsChangedBytes(vendor, which) {
  const result = await observe(vendor, '0', {
    badCohort: which === 'cohort', badRecovery: which === 'recovery'});
  assert.equal(result.error?.name, 'AssertionError',
    'Actual raw-byte mismatch must reject, not skip or fail a fixture binding');
  assert.equal(result.error?.code, 'ERR_ASSERTION');
  assert.deepEqual(result.reads, readsInOrder.slice(0, which === 'cohort' ? 2 : 4),
    'Stop on the actual mismatching runner/source comparison');
}

test('[protocol] Chrome0 native input binding reads both exact runner-source byte pairs', async () => {
  await acceptsExactBytes('chrome');
});

test('[protocol] Brave0 native input binding reads both exact runner-source byte pairs', async () => {
  await acceptsExactBytes('brave');
});

test('[protocol] Chrome0 rejects runner cohort bytes with an appended space', async () => {
  await rejectsChangedBytes('chrome', 'cohort');
});

test('[protocol] Chrome0 rejects runner recovery bytes with an appended space', async () => {
  await rejectsChangedBytes('chrome', 'recovery');
});

test('[protocol] Brave0 rejects runner cohort bytes with an appended space', async () => {
  await rejectsChangedBytes('brave', 'cohort');
});

test('[protocol] Brave0 rejects runner recovery bytes with an appended space', async () => {
  await rejectsChangedBytes('brave', 'recovery');
});

test('[protocol] Firefox0 control reads both exact runner-source byte pairs', async () => {
  await acceptsExactBytes('firefox');
});

test('[protocol] Firefox0 control rejects runner cohort bytes with an appended space', async () => {
  await rejectsChangedBytes('firefox', 'cohort');
});

test('[protocol] Firefox0 control rejects runner recovery bytes with an appended space', async () => {
  await rejectsChangedBytes('firefox', 'recovery');
});

test('[protocol] legacy Chrome1 retains its separate nonqualifying cohort-binding bypass', async () => {
  const result = await observe('chrome', '1', {badCohort: true, badRecovery: true});
  assert.equal(result.error, undefined);
  assert.deepEqual(result.reads, []);
});

async function omittedVendorSelection(vendor, mode) {
  const start = launcher.indexOf('const browserVendor = ');
  const declaration = launcher.indexOf('const bodyCacheDirectory = ', start);
  const finish = launcher.indexOf(';\n', declaration) + 1;
  assert.ok(start >= 0 && declaration > start && finish > declaration,
    'Actual runtime-selection prefix extraction boundaries required');
  const prefix = launcher.slice(start, finish);
  const row = file => ({path: file, realpath: file, SHA256: 'a'.repeat(64)});
  const pins = {node: row('/protocol/runtime/node'), python: row('/protocol/runtime/python'),
    chrome: row('/protocol/runtime/chrome'), brave: row('/protocol/runtime/brave'),
    firefox: row('/protocol/runtime/firefox')};
  const context = vm.createContext({assert, path, project, process: {env: {
    MTG_BROWSER_VENDOR: vendor, MTG_BROWSER_NO_SANDBOX: mode,
    MTG_FRONTEND_DEPS: '/protocol/runtime/node_modules'}},
    async readFile(file, encoding) {
      if (file !== path.join(project, 'runner/executable-pins.json') || encoding !== 'utf8')
        throw new Error('Inert selection fixture rejected an undeclared read');
      return JSON.stringify(pins);
    },
  });
  const result = await new vm.Script(`(async () => {${prefix}
    return {browserVendor, python, deps, chrome};})()`,
    {filename: 'actual-omitted-vendor-selection.protocol.mjs'})
    .runInContext(context, {timeout: 1000});
  return JSON.parse(JSON.stringify(result));
}

test('[protocol] omitted or empty vendor retains exact legacy Chrome1 selection', async () => {
  for (const vendor of [undefined, '']) {
    const selected = await omittedVendorSelection(vendor, '1');
    assert.deepEqual(selected, {browserVendor: 'chrome',
      python: '/tmp/mtg-fresh-deps-restored-dVBzUV/venv/bin/python',
      deps: '/home/nick/mtg-deck-testing-lab/frontend/node_modules',
      chrome: '/snap/chromium/3551/usr/lib/chromium-browser/chrome'});
  }
});

test('[protocol] omitted or empty vendor rejects native0 without a browser fallback', async () => {
  for (const vendor of [undefined, ''])
    await assert.rejects(omittedVendorSelection(vendor, '0'),
      error => error?.name === 'AssertionError' && error.code === 'ERR_ASSERTION');
});
