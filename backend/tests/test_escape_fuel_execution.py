"""Mana-created escape fuel must remain payable through the native engine."""
import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.spell_cost_witness import escape_fuel_proven_impossible, escape_payment_condition
from tests.test_escape_mana_fuel_bound import add, escape_position
from tests.test_spell_cost_overlap_investigation import unchanged_root


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['familiar', 'tower', 'pet'])
def test_native_escape_uses_fuel_created_by_real_mana_cost(seat, family):
    state, spell = escape_position(seat, fuel=3, treasure=False)
    if family == 'familiar':
        add(state, 'Skirge Familiar', seat)
        fuel = add(state, 'Island', seat, Zone.HAND)
    elif family == 'tower':
        add(state, 'Phyrexian Tower', seat)
        fuel = state.cards[state.players[seat].battlefield[-2]]
        assert fuel.name == 'Ornithopter'
    else:
        fuel = add(state, 'Blood Pet', seat)
    original_fuel = list(state.players[seat].graveyard)
    original_fuel.remove(spell.id)
    action = {'type': 'cast_spell', 'card_id': spell.id,
              'from_graveyard': True, 'cost_choice': {'id': 'escape'}}
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    results = []
    for root in (state, restored):
        with unchanged_root(root):
            result = checked_action(root, RulesEngine(), seat, action)
        assert result.cards[spell.id].zone == Zone.STACK
        assert all(result.cards[cid].zone == Zone.EXILE
                   for cid in [*original_fuel, fuel.id])
        results.append(serialize_match_snapshot(result))
    assert results[0] == results[1]


@pytest.mark.parametrize('seat', [1, 2])
def test_retained_linked_departure_context_is_not_a_zero_growth_proof(seat):
    state, spell = escape_position(seat)
    # Unknown retained engine context is a guard control, not a real-card fixture.
    state.linked_exiles = [{'uncovered_retained_departure': True}]
    with unchanged_root(state):
        assert not escape_fuel_proven_impossible(
            state, seat, escape_payment_condition(seat, spell.id, 4))
