"""Observe real planner reservations without replacing payment semantics."""
import pytest

from game_state.state import Zone
from rules_engine import costs
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_fixed_spell_cost_witness import add, setup
from tests.test_spell_cost_overlap_investigation import position, unchanged_root


def observe(monkeypatch):
    original = costs.can_pay_with_pool_and_lands
    calls = []
    depth = 0

    def traced(*args, **kwargs):
        nonlocal depth
        # Nested mana witnesses have their own legitimate resource reservations.
        if depth == 0:
            calls.append(set(kwargs['reserved_card_ids']))
        depth += 1
        try:
            return original(*args, **kwargs)
        finally:
            depth -= 1

    monkeypatch.setattr(costs, 'can_pay_with_pool_and_lands', traced)
    return calls


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['tower', 'prospector', 'familiar'])
def test_explicit_finite_cost_keeps_reserved_resource(monkeypatch, seat, family):
    state, spell, option, victim, _, action = setup(seat, family, False)
    calls = observe(monkeypatch)
    with unchanged_root(state):
        assert not costs.check_cost_option_available(
            state, seat, spell, option, cost_choice=action['cost_choice'])
    assert calls and all({spell.id, victim.id} <= ids for ids in calls)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['tower', 'familiar'])
def test_exhaustive_resource_paid_after_real_mana(monkeypatch, seat, family):
    state = position(seat)
    if family == 'tower':
        add(state, 'Phyrexian Tower', seat)
        add(state, 'Swamp', seat)
        fuel = [add(state, 'Raging Goblin', seat)]
    else:
        add(state, 'Skirge Familiar', seat)
        fuel = [add(state, 'Island', seat, Zone.HAND) for _ in range(3)]
    leftover = add(state, 'Forest', seat, Zone.HAND)
    spell = add(state, "Kaervek's Spite", seat, Zone.HAND)
    option, = costs.collect_cost_options(state, seat, spell)
    assert option.discard_all and option.sacrifice_all
    calls = observe(monkeypatch)
    with unchanged_root(state):
        assert costs.check_cost_option_available(
            state, seat, spell, option, cost_choice={'id': 'base'})
        assert calls == [{spell.id}]
        paid = checked_action(state, RulesEngine(), seat, {
            'type': 'cast_spell', 'card_id': spell.id,
            'cost_choice': {'id': 'base'}, 'targets': {'target_player': 3-seat}})
    assert paid.cards[spell.id].zone == Zone.STACK
    assert all(paid.cards[c.id].zone == Zone.GRAVEYARD for c in [*fuel, leftover])
    assert not paid.players[seat].hand and not paid.players[seat].battlefield
