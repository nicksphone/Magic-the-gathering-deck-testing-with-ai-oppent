import assert from 'node:assert/strict';
import {parseLegalMoves} from '../src/api/match-contract.ts';

const candidates = [{id: 'island', name: 'Island'}, {id: 'fertilid', name: 'Fertilid'}];
const permanent = {required_distinct_target_count: 2, permanent_targets: candidates};
const counters = {required_distinct_target_count: 3, creature_targets: candidates,
  ordered_counter_amounts: [0, 2, 3], ordered_counter_type: '+1/+1'};
const envelope = hints => ({player_id: 1, revision: 1,
  moves: [{type: 'cast_spell', target_hints: hints}]});

for (const hints of [permanent, {...permanent, permanent_targets: []}, counters,
  {...permanent, permanent_targets: [{...candidates[0], owner: 2, controller: 1}]}]) {
  for (const costSpecific of [false, true]) {
    const value = envelope(hints);
    if (costSpecific) value.moves = [{type: 'cast_spell', cost_options: [{id: 'base',
      discard_cards: 0, sacrifice_creatures: 0, target_hints: hints}]}];
    assert.equal(parseLegalMoves(value).moves[0], value.moves[0], 'Valid hints are preserved, not normalized or completed');
  }
}
const invalid = [
  ...[null, true, 0, 1, 2.5, '2', 251, Infinity].map(required_distinct_target_count => ({...permanent, required_distinct_target_count})),
  {required_distinct_target_count: 2},
  ...[null, {}, [null], [{id: '', name: 'Island'}], [{id: 'island'}], [candidates[0], candidates[0]]]
    .map(permanent_targets => ({...permanent, permanent_targets})),
  ...[null, [{id: 'island', name: ''}], [candidates[0], candidates[0]]]
    .map(creature_targets => ({...counters, creature_targets})),
  {...permanent, required_target_instance_count: 2},
  {...permanent, ordered_creature_modifiers: []},
  {...counters, ordered_counter_amounts: [1, 2]},
  {...counters, ordered_counter_amounts: [1, -2, 3]},
  {...counters, ordered_counter_amounts: [1, 2.5, 3]},
  {...counters, ordered_counter_amounts: null},
  {...counters, ordered_counter_type: ''},
  {...counters, ordered_counter_type: null},
  {...counters, ordered_counter_type: undefined},
  {...permanent, ordered_counter_type: '+1/+1'},
  {ordered_counter_amounts: [1, 2], ordered_counter_type: '+1/+1'},
];
for (const hints of invalid) {
  for (const costSpecific of [false, true]) {
    const value = envelope(hints);
    if (costSpecific) value.moves = [{type: 'cast_spell', cost_options: [{id: 'base',
      discard_cards: 0, sacrifice_creatures: 0, target_hints: hints}]}];
    assert.throws(() => parseLegalMoves(value), /legal-moves/, 'Malformed distinct-target metadata must fail before rendering');
  }
}
console.log(`PASS ${invalid.length * 2} malformed distinct-target responses rejected across move/cost-specific contracts, with valid views preserved`);
