"""Actual paid copy choices do not upgrade old target/source incarnations."""
from copy import deepcopy

import pytest

import domain_paid_support as g
import test_paid_exchange_desired as original
import test_exchange_edges as edges
import test_qualifier_paid_controls as controls
from game_state.state import Zone, object_incarnation
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.counter_placement import counter_placement_forbidden

facts = controls.facts


def player_mode(state, seat):
    options = [option for move in original.moves(state, seat) if move['type'] == 'choose_mechanic'
               for option in move.get('options', [])
               if move.get('option_labels', {}).get(option, '').startswith('Target opponent loses all counters')]
    assert len(options) == 1
    state = g.act(state, seat, 'choose_mechanic', choice_id=options[0])
    targets = [move for move in original.moves(state, seat) if move['type'] == 'choose_trigger_target']
    if targets:
        assert len(targets) == 1 and targets[0]['target_player'] == 3-seat
        state = checked_action(state, RulesEngine(), seat, targets[0])
    return state


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case', ['keep', 'keep-target-blink', 'new-target-blink',
                                'new-target-departure', 'source-departure', 'source-blink'])
def test_paid_trigger_copy_keep_and_lifetime_oldobject_negatives(facts, seat, case):
    state = g.position(facts, seat)
    target = g.add(state, facts, 'Raging Goblin', 3-seat)
    own = g.add(state, facts, 'Raging Goblin', seat)
    for cid in (target, own):
        state.cards[cid].counters['+1/+1'] = 1  # Explicit initial resources.
    state, copier = controls.paid_permanent(state, facts, seat, 'Strionic Resonator', {'C': 2})
    state, source = controls.paid_permanent(state, facts, seat, 'Suncleanser', {'C': 1, 'W': 1})
    options = [option for move in original.moves(state, seat) if move['type'] == 'choose_mechanic'
               for option in move.get('options', [])
               if move.get('option_labels', {}).get(option, '').startswith('Remove all counters from target creature')]
    assert len(options) == 1
    state = g.act(state, seat, 'choose_mechanic', choice_id=options[0])
    choice = next(move for move in original.moves(state, seat)
                  if move['type'] == 'choose_trigger_target' and move.get('target_card_id') == target)
    state = checked_action(state, RulesEngine(), seat, choice)
    original_item = state.stack[-1].id
    original_payload = deepcopy(state.stack[-1].payload)
    source_incarnation = object_incarnation(state.cards[source])
    state.players[seat].mana_pool = {'C': 2}
    public = original.moves(state, seat)
    activate = next(move for move in public if move['type'] == 'activate_ability' and move.get('card_id') == copier)
    state = g.act(state, seat, 'activate_ability', card_id=copier,
                  ability_index=activate['ability_index'], targets={'target_stack_id': original_item})
    assert state.cards[copier].tapped and not sum(state.players[seat].mana_pool.values())
    state = edges.settle(state)
    copied = next(item for item in state.stack if item.payload.get('__stack_copy_kind'))
    copied_id = copied.id
    keep = case.startswith('keep')
    selected = target if keep else own
    pending = state.pending_mechanic_choice
    assert pending['kind'] == 'copy_target'
    option = 'keep' if keep else next(option for option in pending['options'] if option.endswith(':' + own))
    state = g.act(g.restore(state), seat, 'choose_mechanic', card_ids=[option])
    copied = next(item for item in state.stack if item.id == copied_id)
    assert next(item for item in state.stack if item.id == original_item).payload == original_payload
    reference = deepcopy(copied.payload['__trigger_target_reference'])
    assert reference == [object_incarnation(state.cards[selected]), state.cards[selected].zone_change_sequence]
    if keep:
        assert copied.payload['__trigger_target_reference'] == original_payload['__trigger_target_reference']
    if case.endswith('target-blink'):
        state = edges.paid_instant(state, facts, seat, 'Flicker of Fate', {'C': 1, 'W': 1}, selected)
        assert object_incarnation(state.cards[selected]) != reference[0]
    elif case == 'new-target-departure':
        state = edges.paid_instant(state, facts, seat, 'Unsummon', {'U': 1}, selected)
        assert state.cards[selected].zone == Zone.HAND
    elif case == 'source-departure':
        state = edges.paid_instant(state, facts, seat, 'Unsummon', {'U': 1}, source)
        assert state.cards[source].zone == Zone.HAND
    elif case == 'source-blink':
        state = edges.paid_instant(state, facts, seat, 'Flicker of Fate', {'C': 1, 'W': 1}, source)
        assert object_incarnation(state.cards[source]) != source_incarnation
        state = player_mode(state, seat)
    if 'target-' in case:
        copied = next(item for item in state.stack if item.id == copied_id)
        assert copied.payload['__trigger_target_reference'] == reference
    state = edges.settle(g.restore(state))
    assert not state.stack and not state.pending_mechanic_choice
    if 'target-' in case:
        assert any('Suncleanser ETB (copy) does not resolve because its target is illegal.' == line
                   for line in state.log)
        assert not counter_placement_forbidden(state, '+1/+1', target_card_id=selected)
    else:
        assert state.cards[selected].counters.get('+1/+1', 0) == 0
        assert counter_placement_forbidden(state, '+1/+1', target_card_id=selected) == (case == 'keep')
    original.record(f'qualifier-trigger-lifetime-{case}-{seat}', state,
                    copied_id=copied_id, retained_target_reference=reference, original_payload=original_payload)
