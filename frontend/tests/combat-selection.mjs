import assert from 'node:assert/strict';
import { emptyCombatDraft, toggleAttacker, selectAttackers, bandAttackers, assignBlocker } from '../src/components/combat-selection.ts';

const empty = emptyCombatDraft();
assert.deepEqual(empty.attackers, []);
const selected = toggleAttacker(empty, 'hero');
assert.deepEqual(empty.attackers, []);
assert.deepEqual(selected.attackers, ['hero']);
assert.deepEqual(toggleAttacker(selected, 'hero').attackers, []);
const attack = {type: 'attack', options: ['hero', 'angel', 'elf', 'hero2'], banding_attackers: ['hero', 'hero2']};
const band = bandAttackers(empty, 'hero', 'angel', attack, 'player:2');
assert.equal(band.error, null);
assert.deepEqual(band.draft.bands, [['hero', 'angel']]);
assert.deepEqual(band.draft.attackers, ['hero', 'angel']);
assert.deepEqual(selectAttackers(band.draft, ['hero']).bands, []);
const extended = bandAttackers(band.draft, 'hero2', 'hero', attack, 'player:2');
assert.equal(extended.error, null);
assert.equal(extended.draft.bands.length, 1);
assert.equal(extended.draft.bands[0].length, 3);
for (const [draft, source, target] of [[empty, 'angel', 'elf'], [band.draft, 'elf', 'hero'],
  [empty, 'hero', 'hero'], [empty, 'outsider', 'hero'],
  [{...empty, attackTargets: {hero: 'player:2', angel: 'planeswalker:w'}}, 'hero', 'angel']]) {
  const before = structuredClone(draft);
  const rejected = bandAttackers(draft, source, target, attack, 'player:2');
  assert.ok(rejected.error);
  assert.deepEqual(rejected.draft, before);
  assert.deepEqual(draft, before);
}
const block = {type: 'block', attackers: [{id:'a'}, {id:'b'}, {id:'flying'}],
  blockers: [{id:'ground'}, {id:'two'}, {id:'wall'}],
  legal_blocks: {ground:['a','b'], two:['a','b','flying'], wall:['a','b','flying']},
  blocker_capacities: {ground:1, two:2, wall:null}};
const first = assignBlocker(empty, 'ground', 'a', block);
assert.equal(first.error, null);
assert.deepEqual(first.draft.blocks.a, ['ground']);
const team = assignBlocker(first.draft, 'wall', 'a', block);
assert.equal(team.error, null);
assert.deepEqual(team.draft.blocks.a, ['ground', 'wall'], 'several blockers may share one attacker');
assert.equal(assignBlocker(empty, 'ground', 'flying', block).draft, empty);
assert.ok(assignBlocker(empty, 'outsider', 'a', block).error);
assert.ok(assignBlocker(empty, 'ground', 'outsider', block).error);
const moved = assignBlocker(first.draft, 'ground', 'b', block);
assert.deepEqual(moved.draft.blocks.a, []);
assert.deepEqual(moved.draft.blocks.b, ['ground']);
assert.deepEqual(first.draft.blocks.a, ['ground']);
const two = assignBlocker(assignBlocker(empty, 'two', 'a', block).draft, 'two', 'b', block);
assert.equal(two.error, null);
assert.ok(assignBlocker(two.draft, 'two', 'flying', block).error);
let all = empty;
for (const attacker of ['a','b','flying']) all = assignBlocker(all, 'wall', attacker, block).draft;
assert.deepEqual(Object.values(all.blocks), [['wall'],['wall'],['wall']]);
assert.deepEqual(assignBlocker(all, 'wall', 'a', block).draft, all, 'repeated drops do not duplicate blockers');
assert.deepEqual(empty, emptyCombatDraft(), 'all selection operations preserve the original draft');
console.log('PASS direct combat selection, legal bands, defender consistency, legal block targets and 1/2/unlimited blocking capacities');
