"""Visible, fail-closed gaps are not narrower eligible lists or entry claims."""
import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests.graveyard_batch_native_support_bf62 import cast_vaults, choose, place, snapshot
from tests.test_entry_copy_native_936 import cast, position


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('route', ['spell', 'vaults'])
def test_genuine_eligible_aura_is_not_filtered_or_silently_partially_entered(seat, route):
    names = ['Sculpting Steel', 'Open the Vaults', 'Liquimetal Coating', 'Rancor', 'Grizzly Bears']
    state = position(names, names, seat)
    creature = place(state, 'Grizzly Bears', Zone.BATTLEFIELD, seat)
    state, aura = cast(state, seat, 'Rancor', target_card_id=creature)
    assert resolve_top_of_stack(state) and state.cards[aura].attached_to == creature
    coating = place(state, 'Liquimetal Coating', Zone.BATTLEFIELD, seat)
    state = checked_action(state, RulesEngine(), seat, {'type': 'activate_ability',
        'card_id': coating, 'ability_index': 0, 'targets': {'target_card_id': aura}})
    assert resolve_top_of_stack(state)
    if route == 'spell':
        state, steel = cast(state, seat, 'Sculpting Steel')
    else:
        steel = place(state, 'Sculpting Steel', Zone.GRAVEYARD, seat)
        state, _ = cast_vaults(state, seat)
    assert not resolve_top_of_stack(state)
    assert aura in state.pending_mechanic_choice['options']
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected, match='copied Aura entry'):
        choose(state, seat, aura)
    assert serialize_match_snapshot(state) == before
    assert state.cards[steel].name == 'Sculpting Steel'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad_record', [{'version': 0}, {'version': 1, 'physical': {}, 'values': {}}])
def test_inadequate_legacy_record_cannot_break_ordinary_noncopy_departure(seat, bad_record):
    from rules_engine.attached_token_payment import copiable_lki
    state = position(['Grizzly Bears', 'Cloudshift'], ['Grizzly Bears', 'Cloudshift'], seat)
    bear = place(state, 'Grizzly Bears', Zone.BATTLEFIELD, seat)
    saved = serialize_match_snapshot(state)
    saved['cards'][bear]['characteristic_record'] = bad_record
    state = deserialize_match_snapshot(saved)
    lki = copiable_lki(state, state.cards[bear])
    assert lki['descriptor'] is None and lki['unavailable'] == 'missing_copiable_characteristics'
    state, _ = cast(state, seat, 'Cloudshift', target_card_id=bear)
    assert resolve_top_of_stack(state)
    assert snapshot(state).cards[bear].zone == Zone.BATTLEFIELD
