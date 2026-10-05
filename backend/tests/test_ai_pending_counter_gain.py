"""Canonical public stack prevention, with explicit unknown/private boundaries."""
from unittest.mock import patch

import pytest

from ai.pending_effects import decision_projection_scope, pending_counter_gain
from effects.registry import resolve_effect
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_ai_search_prefix import bare_state
from tests.test_ai_recurring_engines import add
from tests.regression_agent_wave2.support import add as add_golden


def announced_removal(seat, target_name, spell_name):
    state = bare_state(seat)
    target = (add_golden(state, target_name, seat, Zone.BATTLEFIELD)
              if target_name == 'Memnite' else add(state, target_name, seat))
    opponent = 3 - seat
    spell = add(state, spell_name, opponent, Zone.HAND)
    state.priority_player = opponent
    state.players[opponent].mana_pool.update({'C': 1, 'G': 1, 'B': 1})
    state = checked_action(state, RulesEngine(), opponent,
                          {'type': 'cast_spell', 'card_id': spell.id,
                           'targets': {'target_card_id': target.id}})
    return state, target.id, state.stack[-1].id


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('target_name,spell_name', [
    ('Memnite', 'Naturalize'), ('The Meathook Massacre', 'Naturalize'),
    ('Sheoldred, the Apocalypse', 'Go for the Throat')])
def test_prevention_values_actual_permanent_loss_without_mutation(seat, target_name, spell_name):
    state, _target_id, stack_id = announced_removal(seat, target_name, spell_name)
    before = serialize_match_snapshot(state)
    with decision_projection_scope(state, seat):
        first = pending_counter_gain(state, seat, stack_id)
        assert first > 0
        assert pending_counter_gain(state, seat, stack_id) == first
    assert serialize_match_snapshot(state) == before
    restored = deserialize_match_snapshot(before)
    assert pending_counter_gain(restored, seat, stack_id) == first


@pytest.mark.parametrize('seat', [1, 2])
def test_fizzled_removal_does_not_create_a_prevention_payoff(seat):
    state, target_id, stack_id = announced_removal(seat, 'Sheoldred, the Apocalypse', 'Go for the Throat')
    resolve_effect(state, seat, 'destroy_permanent', {'target_card_id': target_id})
    assert pending_counter_gain(state, seat, stack_id) == 0


def test_unknown_choice_and_counterability_are_not_assumed_away():
    state, _target_id, stack_id = announced_removal(1, 'Memnite', 'Naturalize')
    state.pending_mechanic_choice = {'kind': 'scry', 'player_id': 2}
    before = serialize_match_snapshot(state)
    assert pending_counter_gain(state, 1, stack_id) is None
    assert serialize_match_snapshot(state) == before
    state.pending_mechanic_choice = None
    # Admission guard only; do not invent a new printed uncounterable card.
    with patch('rules_engine.targeting.spell_cant_be_countered', return_value=True):
        assert pending_counter_gain(state, 1, stack_id) == 0
    assert pending_counter_gain(state, 1, 'missing-stack-object') == 0


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['activated', 'triggered'])
@pytest.mark.parametrize('protected', [False, True])
def test_public_ability_prevention_uses_the_ability_counter_handler(seat, kind, protected):
    state = bare_state(seat)
    opponent = 3-seat
    state.active_player = state.priority_player = opponent
    if kind == 'activated':
        from tests.test_ai_priority_shortlists import add as add_priority_card
        from game_state.state import assign_static_order_on_battlefield_entry
        source = add_priority_card(state, 'Nissa, Who Shakes the World', opponent, Zone.BATTLEFIELD)
        land_id = state.players[opponent].library.pop()
        state.cards[land_id].move_to_zone(Zone.BATTLEFIELD)
        state.players[opponent].battlefield.append(land_id)
        assign_static_order_on_battlefield_entry(state, land_id)
        ability = next(move for move in RulesEngine().legal_moves(state, opponent)
                       if move.get('type') == 'activate_loyalty' and move.get('card_id') == source.id
                       and move.get('ability_index') == 0)
        state = checked_action(state, RulesEngine(), opponent,
                               {**ability, 'targets': {'target_card_id': land_id}})
    else:
        source = add(state, 'Blood Artist', opponent)
        victim = add(state, 'Grizzly Bears', opponent)
        resolve_effect(state, opponent, 'destroy_permanent', {'target_card_id': victim.id})
    from rules_engine.targeting import stack_object_kind
    item = next(item for item in state.stack if item.source_card_id == source.id)
    assert stack_object_kind(state, item) == kind
    if protected:
        # Supported runtime admission flag, not invented printed protection text.
        item.payload['uncounterable'] = True
    before = serialize_match_snapshot(state)
    gain = pending_counter_gain(state, seat, item.id)
    assert gain is not None
    assert gain == 0 if protected else gain > 0
    if protected:
        from ai.agent import AIAgent
        assert AIAgent(archetype='Control')._stack_item_threat_score(state, item.id, seat) > 0
    assert serialize_match_snapshot(state) == before
    assert pending_counter_gain(deserialize_match_snapshot(before), seat, item.id) == gain
