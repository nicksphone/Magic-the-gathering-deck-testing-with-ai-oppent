"""Actual checked combat; animation is an explicit trusted continuous-effect seam."""
from copy import deepcopy

import pytest

from .test_full_vraska import born, settle, activate, advance, act, Step, Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.targeting import stack_object_kind
from rules_engine.type_effects import add_type_effect, effective_types
from rules_engine.loyalty_combat import collect_retaliation
from effects.handlers import set_base_stats


@pytest.mark.parametrize('seat', [1, 2])
def test_same_animated_paid_walker_receives_real_creature_combat_retaliation(seat):
    state, walker, attacker = born(seat)
    state = settle(activate(state, seat, walker, 0))
    assert state.cards[walker].loyalty == 6
    state = advance(state, 3-seat, Step.DECLARE_ATTACKERS)
    # No Oracle rewrite or paid-animation claim: install the existing object-bound effects.
    add_type_effect(state, walker, ['Creature'])
    set_base_stats(state, seat, {'target_card_id': walker, 'base_power': 0,
                                'base_toughness': 6, 'until_end_of_turn': False})
    assert {'Creature', 'Planeswalker'}.issubset(effective_types(state, walker))
    state = act(state, 3-seat, {'type': 'attack', 'attackers': [attacker],
                               'attack_targets': {attacker: 'player:'+str(seat)}})
    for _ in range(40):
        if state.step == Step.DECLARE_BLOCKERS and state.priority_player == seat:
            break
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    assert state.step == Step.DECLARE_BLOCKERS and state.priority_player == seat
    state = act(state, seat, {'type': 'block', 'blocks': {attacker: [walker]}})
    for _ in range(40):
        if state.stack or state.step == Step.END_COMBAT:
            break
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    assert state.cards[walker].counters['__damage_marked'] == 2
    assert state.cards[walker].zone == state.cards[attacker].zone == Zone.BATTLEFIELD
    assert len(state.stack) == 1, 'Actual creature-target combat must publish retained +1 trigger'
    trigger = state.stack[-1]
    assert trigger.effect_key == 'loyalty_combat_retaliation_destroy'
    assert trigger.source_card_id == walker and trigger.controller == seat
    assert trigger.payload['target_card_id'] == attacker
    assert stack_object_kind(state, trigger) == 'triggered'
    # Predicate-only negatives retain the genuine source/reference and reject unrelated damage.
    event = {'source_card_id': attacker, 'target_card_id': attacker, 'amount': 2}
    assert collect_retaliation(state, 'combat_damage_dealt', event) == []
    event['target_card_id'] = walker
    stale = deepcopy(state)
    stale.loyalty_permissions[0]['source_reference']['incarnation'] += 1
    assert collect_retaliation(stale, 'combat_damage_dealt', event) == []
    event['amount'] = 0
    assert collect_retaliation(state, 'combat_damage_dealt', event) == []
    state = settle(deserialize_match_snapshot(serialize_match_snapshot(state)))
    assert state.cards[attacker].zone == Zone.GRAVEYARD
    assert state.cards[walker].zone == Zone.BATTLEFIELD and state.winner is None
