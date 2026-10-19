"""Copied-land continuation validates before clearing its retained pending root."""
import pytest

from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests.graveyard_batch_native_support_bf62 import choose, place, snapshot
from tests.test_entry_copy_native_936 import cast, position


def pending_land(seat):
    names = ['Sculpting Steel', 'Liquimetal Coating', 'Breeding Pool']
    state = position(names, names, seat)
    pool = place(state, 'Breeding Pool', Zone.BATTLEFIELD, 3-seat)
    coating = place(state, 'Liquimetal Coating', Zone.BATTLEFIELD, seat)
    state = checked_action(state, RulesEngine(), seat, {'type': 'activate_ability',
        'card_id': coating, 'ability_index': 0, 'targets': {'target_card_id': pool}})
    assert resolve_top_of_stack(state)
    state, steel = cast(state, seat, 'Sculpting Steel')
    assert not resolve_top_of_stack(state)
    state = choose(snapshot(state), seat, pool)
    assert state.pending_mechanic_choice['kind'] == 'land_entry'
    assert state.cards[steel].zone == Zone.STACK
    return state, steel


@pytest.mark.parametrize('seat', [1, 2])
def test_ordinary_paid_copy_of_coated_land_has_real_deferred_payment(seat):
    state, steel = pending_land(seat)
    before = state.players[seat].life
    state = choose(snapshot(state), seat, 'pay_two_life')
    assert state.players[seat].life == before-2
    assert state.cards[steel].zone == Zone.BATTLEFIELD and not state.cards[steel].tapped
    assert 'Artifact' not in state.cards[steel].types
    assert snapshot(state).cards[steel].printed_characteristics['name'] == 'Sculpting Steel'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('mutation', ['frame', 'life'])
def test_changed_copy_land_packet_or_payment_rejects_without_clearing_pending(seat, mutation):
    state, steel = pending_land(seat)
    if mutation == 'frame':
        state.pending_mechanic_choice['effect_payload']['__entry_copy_plan']['frame']['controller'] = 3-seat
    else:
        state.players[seat].life = 1
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        choose(state, seat, 'pay_two_life')
    assert serialize_match_snapshot(state) == before
    assert state.cards[steel].zone == Zone.STACK
