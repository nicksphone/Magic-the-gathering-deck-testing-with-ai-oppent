import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';

// Exercise the actual fixture-switch helper without opening a browser or API.
const source = await readFile(new URL('./browser-ui-v2.mjs', import.meta.url), 'utf8');
const start = source.indexOf('async function setup(path) {');
const end = source.indexOf('\nasync function select(', start);
assert.ok(start >= 0 && end > start);
const helper = source.slice(start, end);

function harness({ readinessError, status = 200 } = {}) {
  let pending = true;
  const calls = [];
  const setup = vm.runInNewContext(`(${helper})`, {
    assert, api: 'http://fixture.invalid',
    waitFor: async (condition) => {
      calls.push(['wait', condition]);
      if (readinessError) throw readinessError;
      if (condition.includes('Match operation pending')) pending = false;
    },
    fetch: async (url, options) => {
      assert.equal(pending, false, 'Finish the old mutation before publishing another fixture');
      calls.push(['fetch', url, options.method]);
      return { status, json: async () => ({ id: 'next-fixture', revision: 0 }) };
    },
    evaluate: async (expression) => { calls.push(['evaluate', expression]); },
    reload: async () => { calls.push(['reload']); },
  });
  return { setup, calls };
}

const success = harness();
assert.equal((await success.setup('/fixture')).id, 'next-fixture');
assert.equal(success.calls[0][0], 'wait');
assert.deepEqual(success.calls.find(([kind]) => kind === 'fetch'),
  ['fetch', 'http://fixture.invalid/fixture', 'POST']);
assert.equal(success.calls.filter(([kind]) => kind === 'fetch').length, 1);
assert.ok(success.calls.at(-1)[1].includes('next-fixture'),
  'Restore readiness must identify the requested fixture, not any old battlefield');
assert.ok(success.calls.at(-1)[1].includes('dataset.matchId'),
  'Stored identity alone does not prove which match is rendered');

const readinessError = new Error('Previous mutation is still unresolved');
const unresolved = harness({ readinessError });
await assert.rejects(unresolved.setup('/fixture'), (error) => error === readinessError);
assert.ok(unresolved.calls.every(([kind]) => kind === 'wait'));

const rejected = harness({ status: 500 });
await assert.rejects(rejected.setup('/fixture'));
assert.equal(rejected.calls.filter(([kind]) => kind === 'fetch').length, 1);
assert.ok(!rejected.calls.some(([kind]) => kind === 'evaluate' || kind === 'reload'));
console.log('PASS fixture handoff waits for the old mutation, restores the requested ID, and never retries writes');
