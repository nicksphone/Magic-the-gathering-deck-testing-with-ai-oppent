"""Additive-field compatibility using an actual suspended canonical entry."""
from copy import deepcopy

import pytest

import test_saga_land_entry as entry
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone


def old_field_shape(value):
    if isinstance(value, dict):
        if value.get('activated_ability_effects') == []:
            value.pop('activated_ability_effects')
        for child in value.values():
            old_field_shape(child)
    elif isinstance(value, list):
        for child in value:
            old_field_shape(child)


@pytest.mark.parametrize('seat', [1, 2])
def test_pre_grant_schema_pending_land_receipt_restores_empty_default(seat):
    state = entry.position(seat)
    cid = entry.add(state, "Urza's Saga", seat, Zone.HAND)
    entry.add(state, 'Vorinclex, Monstrous Raider', seat, Zone.BATTLEFIELD)
    entry.add(state, 'Vorinclex, Monstrous Raider', 3-seat, Zone.BATTLEFIELD)
    state = entry.act(state, seat, dict(type='play_land', card_id=cid))
    assert state.pending_replacement_choice
    raw = deepcopy(serialize_match_snapshot(state))
    # The only schema conversion is omission of the formerly absent empty field.
    old_field_shape(raw)
    before = deepcopy(raw)
    state = deserialize_match_snapshot(raw)
    assert raw == before, 'Restore may not mutate its input snapshot'
    pending = state.pending_replacement_choice
    state = entry.act(state, pending['player_id'], dict(type='choose_replacement',
                      replacement_source_id=pending['options'][0]['source_id']))
    assert state.cards[cid].zone == Zone.BATTLEFIELD
    assert state.players[seat].lands_played_this_turn == 1
    assert not state.cards[cid].activated_ability_effects
