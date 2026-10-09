import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const json = JSON.stringify;
const cases = [
  {mode: 'player_vs_ai', controller: 'ai', flag: undefined, wait: true},
  {mode: 'player_vs_ai', controller: 'human', flag: true, wait: true},
  ...[false, undefined, null, 1, 'true'].map(flag => ({
    mode: 'player_vs_ai', controller: 'human', flag, wait: false,
  })),
  {mode: 'human_vs_human', controller: 'human', flag: true, wait: false},
];
const mismatches = [];
let checks = 0;

for (const name of ['browser-native-human-bo3.mjs', 'browser-native-human-bo3-seat2.mjs']) {
  const source = fs.readFileSync(path.join(here, 'release-owned', name), 'utf8');
  const start = source.indexOf("      if(raw.controllers[String(legal.player_id)]==='ai')");
  const end = source.indexOf('\n      const pid=legal.player_id', start);
  assert.ok(start >= 0 && end > start, 'Actual actor gate must exist');
  // Exercise the actual loop branch without launching a browser or submitting actions.
  const branch = source.slice(start, end).replaceAll('continue;', 'return true;');
  for (const seat of [1, 2]) for (const row of cases) {
    const calls = [], logs = [];
    const raw = {revision: 139, step: 'declare_blockers', controllers: {[seat]: row.controller}};
    const value = await vm.runInNewContext(`(async()=>{${branch};return false;})()`, {
      raw, mode: row.mode, legal: {player_id: seat, can_auto_pass: row.flag},
      Date, json, path, dir: '/no-real-write-control',
      appendFile: async (_file, line) => logs.push(JSON.parse(line)),
      changed: async (label, revision) => {
        calls.push({label, revision}); raw.revision = 140;
      },
    });
    if (value !== row.wait) mismatches.push({name, seat, ...row, actual: value});
    assert.equal(calls.length, value ? 1 : 0, 'Exactly one native wait, never an action');
    if (value) assert.equal(calls[0].revision, 139);
    if (row.controller === 'ai') assert.deepEqual(logs, []);
    if (row.controller === 'human' && value) {
      assert.equal(calls[0].label, 'native-empty-human-window');
      assert.deepEqual(logs.map(log => log.phase), ['await-native-autoplay', 'observed-native-advance']);
      assert.equal(logs[0].actor, seat);
      assert.equal(logs[0].can_auto_pass, true);
      assert.equal(logs[1].revision, 140);
    }
    checks++;
  }

  const selectStart = source.indexOf('  async function select(');
  const selectEnd = source.indexOf('  async function selections(', selectStart);
  assert.ok(selectStart >= 0 && selectEnd > selectStart, 'Actual select helper must exist');
  const readback = source.slice(selectStart, selectEnd).split('\n')
    .find(line => line.includes('await waitFor(') && line.includes('selectedOptions'));
  const template = readback?.match(/await waitFor\(`(.*)`\);/)?.[1];
  assert.ok(template, 'Actual selected-value readback must exist');
  const selected = values => ({selectedOptions: values.map(value => ({value}))});
  const evaluateReadback = (values, elements, index = 0, documentOverride) => {
    const expression = vm.runInNewContext('`' + template + '`', {
      selector: '#block-declaration select[multiple]', index, values, json,
    });
    return vm.runInNewContext(expression, {
      document: documentOverride ?? {querySelectorAll: () => elements},
    });
  };
  for (const row of [
    {values: ['chosen'], elements: [selected(['chosen'])], expected: true},
    {values: [], elements: [selected([])], expected: true},
    {values: ['chosen'], elements: [], expected: false},
    {values: [], elements: [], expected: false},
    {values: ['chosen'], elements: [selected(['other'])], expected: false},
    {values: ['chosen'], elements: [selected(['chosen', 'other'])], expected: false},
    {values: ['chosen'], elements: [selected(['other']), selected(['chosen'])], index: 1, expected: true},
  ]) {
    try {
      const actual = evaluateReadback(row.values, row.elements, row.index);
      if (actual !== row.expected) mismatches.push({name, readback: row, actual});
    } catch (error) {
      mismatches.push({name, readback: row, error: error.message});
    }
    checks++;
  }
  assert.throws(() => evaluateReadback([], [{}]), /iterable/);
  assert.throws(() => evaluateReadback([], [], 0, {
    querySelectorAll() {throw new Error('Unrelated selector error');},
  }), /Unrelated selector error/);
  checks += 2;
}

console.log(json({sourceExtractedChecks: checks, mismatches, noBrowserSqlNetwork: true}));
assert.deepEqual(mismatches, [], 'Safe native windows wait; missing selects never pass or throw');
