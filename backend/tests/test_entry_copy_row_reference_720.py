"""Strict retained row references through real paid entry producers."""
from copy import deepcopy

import pytest

from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected
from rules_engine.entry_copy import PLAN, plan_matches
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_entry_copy_native_936 import pending_steel
from tests.test_entry_two_route_bindings_662 import waiting_copy
from tests.test_entry_unadapted_two_families_641 import action, loyalty_return, roundtrip


def pending_recipient(route, seat):
    if route == 'live_stack':
        state, steel, target, _ = pending_steel(seat)
    elif route == 'loyalty_gy':
        state, steel, cost, _, target, _, _ = loyalty_return(seat)
        assert not resolve_top_of_stack(state)
        state = action(roundtrip(state), seat, type='choose_mechanic', card_ids=[cost])
        assert state.cards[cost].zone == state.cards[steel].zone == Zone.GRAVEYARD
    else:
        assert route == 'detached'
        state, steel, target, _, _ = waiting_copy(seat)
    pending = state.pending_mechanic_choice
    assert pending['kind'] == 'entry_copy' and pending['player_id'] == seat
    assert target in pending['options']
    row, = pending['effect_payload'][PLAN]['entries']
    assert plan_matches(state, pending['effect_payload'])
    assert all(type(row['reference'][key]) is int for key in ('incarnation', 'sequence'))
    if route == 'detached':
        assert row['id'] not in state.cards and 'candidate' in row
        assert row['reference']['zone'] == 'stack'
    else:
        assert row['id'] == steel and 'candidate' not in row
        assert state.cards[steel].zone == (Zone.GRAVEYARD if route == 'loyalty_gy' else Zone.STACK)
    return state, steel, target


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('route', ['live_stack', 'loyalty_gy', 'detached'])
@pytest.mark.parametrize('field', ['incarnation', 'sequence'])
@pytest.mark.parametrize('scalar', ['float', 'bool'])
def test_row_reference_scalar_alias_rejects_before_selection_clear_or_entry(seat, route, field, scalar):
    state, steel, target = pending_recipient(route, seat)
    row = state.pending_mechanic_choice['effect_payload'][PLAN]['entries'][0]
    row['reference'][field] = float(row['reference'][field]) if scalar == 'float' else bool(row['reference'][field])
    state = roundtrip(state)
    reference = state.pending_mechanic_choice['effect_payload'][PLAN]['entries'][0]['reference']
    assert type(reference[field]) is (float if scalar == 'float' else bool)
    before = serialize_match_snapshot(state)
    allocation = state.next_object_id
    with pytest.raises(ActionRejected):
        action(state, seat, type='choose_mechanic', choice_id=target)
    assert serialize_match_snapshot(state) == before
    assert state.next_object_id == allocation
    assert state.pending_mechanic_choice['kind'] == 'entry_copy'
    assert state.cards[steel].zone == (Zone.GRAVEYARD if route == 'loyalty_gy' else Zone.STACK)
    assert not any(card.is_token for card in state.cards.values())
    assert not plan_matches(state, state.pending_mechanic_choice['effect_payload'])


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('route', ['live_stack', 'loyalty_gy', 'detached'])
@pytest.mark.parametrize('decline', [False, True])
def test_real_integer_row_reference_retains_select_decline_and_committed_snapshot(seat, route, decline):
    state, steel, target = pending_recipient(route, seat)
    row = state.pending_mechanic_choice['effect_payload'][PLAN]['entries'][0]
    cid = row['id']
    frame = deepcopy(state.pending_mechanic_choice['resolving_item'])
    stock = deepcopy(state.sideboard_facts['inventory'])
    allocation = state.next_object_id
    state = action(roundtrip(state), seat, type='choose_mechanic',
                   **({'card_ids': []} if decline else {'choice_id': target}))
    assert not state.pending_mechanic_choice and not state.pending_replacement_choice
    entered = state.cards[cid]
    assert entered.zone == Zone.BATTLEFIELD and entered.owner == entered.controller == seat
    assert entered.name == ('Sculpting Steel' if decline else 'Sol Ring')
    assert entered.is_token is (route == 'detached')
    assert state.next_object_id == allocation
    assert state.sideboard_facts['inventory'] == stock
    assert entered.characteristic_record['physical']['name'] == 'Sculpting Steel'
    restored = roundtrip(state)
    assert restored.cards[cid].characteristic_record == entered.characteristic_record
    assert restored.cards[cid].zone == Zone.BATTLEFIELD
    assert restored.sideboard_facts['inventory'] == stock
    assert all(item.id != frame['id'] for item in state.stack)
    if route == 'detached':
        assert cid != frame['source_card_id'] == steel
        assert state.cards[steel].zone == Zone.STACK
        assert len([card for card in state.cards.values() if card.is_token]) == 1
    else:
        assert cid == steel and not state.stack
