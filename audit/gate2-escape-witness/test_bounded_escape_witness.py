"""Bounded post-payment eligibility is a witness, not a completeness claim."""
import pytest

from rules_engine.mana import can_pay_with_pool_and_lands
from rules_engine.spell_cost_witness import escape_payment_condition
from tests.test_spell_cost_overlap_investigation import escape_position, unchanged_root


@pytest.mark.parametrize('seat', [1, 2])
def test_pending_physical_resource_is_not_escape_fuel(seat):
    state, _, _, spell, grave = escape_position(seat, initial=4)
    automatic = escape_payment_condition(seat, spell.id, 4)
    exact = escape_payment_condition(seat, spell.id, 4, grave)
    assert automatic(state) and exact(state)
    assert not automatic.with_pending([grave[0]])(state)
    assert not exact.with_pending([grave[0]])(state)
    assert automatic(state) and exact(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_selected_ids_are_frozen_without_manufacturing_future_fuel(seat):
    state, _, creature, spell, grave = escape_position(seat)
    selected = [*grave, creature.id]
    goal = escape_payment_condition(seat, spell.id, 4, selected)
    assert goal.valid and not goal(state)
    selected[:] = ['unknown'] * 4
    assert goal.valid and not goal(state)
    invalid = escape_payment_condition(seat, spell.id, True)
    assert not invalid.valid and not invalid.visit() and not invalid(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_physical_branches_share_one_finite_budget(seat):
    state, _, _, spell, _ = escape_position(seat, initial=4)
    goal = escape_payment_condition(seat, spell.id, 4, max_nodes=2)
    first, second = goal.with_pending([]), goal.with_pending([])
    assert first.visit() and second.visit()
    assert not goal.visit()
    assert goal.budget == {'nodes': 2, 'exhausted': True}
    assert first.budget is second.budget is goal.budget


@pytest.mark.parametrize('seat', [1, 2])
def test_exhausted_planning_fails_closed_without_mutation(seat):
    state, _, _, spell, _ = escape_position(seat)
    goal = escape_payment_condition(seat, spell.id, 4, max_nodes=0)
    with unchanged_root(state):
        assert not can_pay_with_pool_and_lands(
            state, seat, '{3}{B}{B}', source_card_id=spell.id,
            post_payment_condition=goal)
    assert goal.budget == {'nodes': 0, 'exhausted': True}
