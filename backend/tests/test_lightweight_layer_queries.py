"""Metadata-light query views remain valid with and without real layer sources."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from game_state.state import Zone
from rules_engine.basic_land_layer import layer_four_view
from rules_engine.hooks import CostContext, apply_cost_modifiers
from rules_engine.type_effects import effective_types
from tests.test_basic_land_layer_goldens import add, position


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('setter', [None, 'Blood Moon', 'Spreading Seas', 'Song of the Dryads'])
def test_lightweight_forest_queries_preserve_root_with_real_layer_sources(seat, setter):
    state = position(seat)
    # Deliberately omit optional metadata on this query-only view, not a new card.
    forest = SimpleNamespace(id='lightweight-forest', name='Forest', controller=seat,
                             zone=Zone.BATTLEFIELD, types=['Land'])
    state.cards[forest.id] = forest
    state.players[seat].battlefield.append(forest.id)
    if setter:
        source = add(state, setter, 3-seat)
        if setter != 'Blood Moon':
            # Controlled attachment seam; no sorcery-in-response claim.
            source.attached_to = forest.id
    before = deepcopy(state)
    context = apply_cost_modifiers(CostContext(
        player_id=seat, card_name='Young Pyromancer', mana_cost='{1}{R}',
        state=state, spell_types={'Creature'}))
    assert context.generic_increase == context.generic_reduction == 0
    assert effective_types(state, forest) == ['Land']
    assert layer_four_view(state) == layer_four_view(state, entering=forest, controller=seat)
    assert state.rng.getstate() == before.rng.getstate()
    assert {key: value for key, value in vars(state).items() if key != 'rng'} == {
        key: value for key, value in vars(before).items() if key != 'rng'}
