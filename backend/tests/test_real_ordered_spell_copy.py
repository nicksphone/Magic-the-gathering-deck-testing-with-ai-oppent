"""Canonical Twincast is paid, resolved, suspended and resumed through the stack."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from game_state.state import MatchFactory, Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.continuous import effective_combat_stats
from tests.test_ordered_creature_modifiers import position

RAW = json.loads((Path(__file__).parent / 'fixtures/coupled_targets/twincast.json').read_text())


def pass_twice(state):
    for _ in range(2):
        state = checked_action(state, RulesEngine(), state.priority_player, {'type': 'pass_priority'})
    return state


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('own_copy', [False, True])
def test_real_twincast_payment_choice_resume_and_original_resolution(seat, own_copy):
    state, spell, first, second = position(seat)
    copier = seat if own_copy else 3-seat
    state.players[copier].mana_pool['U'] += 2
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'cast_spell', 'card_id': spell, 'targets': {'target_card_ids': [first, second]}})
    original = state.stack[-1].id
    sample = MatchFactory.from_decks([{**RAW, 'card_name': RAW['name'], 'quantity': 8}], [], seed=836)
    twincast = deepcopy(next(iter(sample.cards.values())))
    twincast.id = state.allocate_object_id()
    twincast.owner = twincast.controller = copier
    twincast.move_to_zone(Zone.HAND)
    state.cards[twincast.id] = twincast
    state.players[copier].hand.append(twincast.id)
    if not own_copy:
        state = checked_action(state, RulesEngine(), seat, {'type': 'pass_priority'})
    state = checked_action(state, RulesEngine(), copier, {
        'type': 'cast_spell', 'card_id': twincast.id, 'targets': {'target_stack_id': original}})
    assert state.players[copier].mana_pool['U'] == 0
    assert state.stack[-1].effect_key == 'copy_spell'
    state = pass_twice(state)
    assert state.pending_mechanic_choice['kind'] == 'copy_target'
    assert state.pending_mechanic_choice['player_id'] == copier
    assert state.pending_mechanic_choice['resolving_item']['source_card_id'] == twincast.id
    assert state.cards[twincast.id].zone == Zone.STACK
    for target in [second, first]:
        state = deserialize_match_snapshot(serialize_match_snapshot(state))
        state = checked_action(state, RulesEngine(), copier,
                               {'type': 'choose_mechanic', 'card_ids': [f'target_card_id:{target}']})
    assert state.pending_mechanic_choice is None
    assert state.cards[twincast.id].zone == Zone.GRAVEYARD
    assert len(state.stack) == 2
    assert state.stack[0].payload['__announced_targets']['target_card_ids'] == [first, second]
    state = pass_twice(state)
    assert effective_combat_stats(state, first) == (4, 2)
    assert effective_combat_stats(state, second) == (2, 6)
    assert len(state.stack) == 1
    state = pass_twice(state)
    assert not state.stack
    assert effective_combat_stats(state, first) == (1, 2)
    assert effective_combat_stats(state, second) == (2, 3)
    assert state.cards[spell].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_copy_keeping_old_ward_target_does_not_target_a_returned_object(seat):
    from effects.handlers import copy_spell
    from effects.registry import resolve_effect
    from tests.test_ward_resolution import add as add_ward
    state, spell, first, second = position(seat)
    warded = add_ward(state, 'Tolarian Terror', 3-seat)
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'cast_spell', 'card_id': spell,
                            'targets': {'target_card_ids': [warded.id, second]}})
    original = next(item.id for item in state.stack if item.source_card_id == spell)
    assert len([item for item in state.stack if item.effect_key == 'ward_payment']) == 1
    resolve_effect(state, seat, 'exile', {'target_card_id': warded.id})
    state.players[3-seat].exile.remove(warded.id)
    state.cards[warded.id].move_to_zone(Zone.BATTLEFIELD)
    state.players[3-seat].battlefield.append(warded.id)
    copy_spell(state, seat, {'target_stack_id': original, 'may_choose_new_targets': True})
    for _ in range(2):
        state = deserialize_match_snapshot(serialize_match_snapshot(state))
        state = checked_action(state, RulesEngine(), seat, {'type': 'choose_mechanic', 'card_ids': ['keep']})
    assert state.pending_mechanic_choice is None
    wards = [item for item in state.stack if item.effect_key == 'ward_payment']
    assert len(wards) == 1
    assert wards[0].payload['target_stack_id'] == original
