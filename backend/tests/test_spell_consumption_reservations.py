"""Strict acceptance over unchanged canonical overlap investigation fixtures."""
import pytest

from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.casting_resources import resource_payment
from rules_engine.engine import RulesEngine
from rules_engine.mana import _payment_requirements, _spell_payment_plan, auto_pay_cost, can_pay_with_pool_and_lands
from tests import test_spell_cost_overlap_investigation as repro
from tests import test_cast_resource_payments as substitutions


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Village Rites', 'Tormenting Voice'])
def test_source_overlap_is_controlled_rejection(seat, name):
    repro.test_casting_source_cannot_fund_its_own_mana_payment(seat, name)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('explicit', [False, True])
def test_external_delve_reservations_are_forwarded(seat, explicit):
    repro.test_resource_substitution_respects_external_reservation_contract(seat, explicit)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Village Rites', 'Tormenting Voice'])
def test_availability_protects_source_with_caller_announced_victim(seat, name):
    state, spell, held, _, _ = repro.source_overlap(seat, name)
    with repro.unchanged_root(state):
        assert not can_pay_with_pool_and_lands(state, seat, spell.mana_cost,
            source_card_id=spell.id, cast_resource_card=spell, reserved_card_ids=[held.id])
        assert not auto_pay_cost(state, seat, spell.mana_cost,
            source_card_id=spell.id, cast_resource_card=spell, reserved_card_ids=[held.id])


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Village Rites', 'Tormenting Voice'])
def test_replay_uses_disjoint_fuel_with_source_first_in_hand(seat, name):
    state, spell, held, fuel, action = repro.source_overlap(seat, name, extra_fuel=True)
    assert state.players[seat].hand[0] == spell.id
    with repro.unchanged_root(state):
        result = checked_action(state, RulesEngine(), seat, action)
    assert result.cards[spell.id].zone == Zone.STACK
    assert result.cards[held.id].zone == result.cards[fuel.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('explicit', [False, True])
def test_delve_can_use_other_fuel_and_never_exiles_reserved_fuel(seat, explicit):
    state = repro.position(seat)
    spell = repro.add(state, 'Treasure Cruise', seat, Zone.HAND)
    ids = [repro.add(state, 'Island', seat, Zone.GRAVEYARD).id for _ in range(8)]
    state.players[seat].mana_pool['U'] = 1
    choices = {'delve': ids[1:]} if explicit else None
    with repro.unchanged_root(state):
        req = _payment_requirements(spell.mana_cost, False, 0, 0, 0)[0]
        plan = _spell_payment_plan(state, seat, req, payment_context=('spell', {'Sorcery'}),
            card=spell, resource_choices=choices, reserved_card_ids=[ids[0]])
        assert plan is not None and set(plan[1].delve) == set(ids[1:])
    assert auto_pay_cost(state, seat, spell.mana_cost, source_card_id=spell.id,
        cast_resource_card=spell, resource_choices=choices, reserved_card_ids=[ids[0]])
    assert state.cards[ids[0]].zone == Zone.GRAVEYARD
    assert all(state.cards[cid].zone == Zone.EXILE for cid in ids[1:])


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,keyword,resource,color,count', [
    ('Siege Wurm', 'convoke', 'Llanowar Elves', 'G', 7),
    ('Reverse Engineer', 'improvise', 'Sol Ring', 'U', 3),
])
@pytest.mark.parametrize('explicit', [False, True])
def test_consumption_reservation_does_not_forbid_substitution_tap(seat, name, keyword, resource, color, count, explicit):
    state, spell = substitutions.position(seat, name)
    ids = [substitutions.add(state, resource, seat, cards=substitutions.ROWS).id for _ in range(count)]
    if keyword == 'improvise':
        state.players[seat].mana_pool[color] = 2
    values = ([{'card_id': cid, 'pay_as': color if i < 2 else 'generic'} for i, cid in enumerate(ids)]
              if keyword == 'convoke' else ids)
    choices = {keyword: values} if explicit else None
    req = substitutions.cost(spell)
    with repro.unchanged_root(state):
        # Preserve the old no-touch and tap-unavailable contracts independently.
        assert resource_payment(state, seat, spell, req, {keyword: values}, reserved_card_ids=ids) is None
        assert resource_payment(state, seat, spell, req, {keyword: values}, unavailable_tap_ids=ids) is None
        assert resource_payment(state, seat, spell, req, {keyword: values}, reserved_consumption_ids=ids)
    assert auto_pay_cost(state, seat, spell.mana_cost, source_card_id=spell.id,
        cast_resource_card=spell, resource_choices=choices, reserved_card_ids=ids)
    if explicit:
        assert all(state.cards[cid].tapped for cid in ids)
    assert all(state.cards[cid].zone == Zone.BATTLEFIELD for cid in ids)
