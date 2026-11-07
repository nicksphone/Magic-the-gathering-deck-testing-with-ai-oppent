"""Canonical source permissions and deliberately stale continuation controls."""
import pytest

import test_saga_land_entry as entry
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.graveyard_permissions import graveyard_land_choices


@pytest.mark.parametrize('seat', [1, 2])
def test_real_graveyard_land_permission_is_consumed_once(seat):
    state = entry.position(seat)
    saga = entry.add(state, "Urza's Saga", seat, Zone.GRAVEYARD)
    entry.add(state, 'Muldrotha, the Gravetide', seat, Zone.BATTLEFIELD)
    key = graveyard_land_choices(state, seat, saga)[0]['key']
    state = entry.act(state, seat, dict(type='play_land', card_id=saga,
                                      from_graveyard=True, graveyard_permission_key=key))
    assert state.cards[saga].zone == Zone.BATTLEFIELD
    assert saga not in state.players[seat].graveyard
    assert state.cards[saga].counters['__lore'] == 1
    assert state.graveyard_permission_uses[key] == state.turn
    assert state.players[seat].land_plays_recorded_on_turn == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_exile_duration_permission_is_removed_on_actual_entry(seat):
    from rules_engine.card_faces import grant_exile_play_duration
    state = entry.position(seat)
    saga = entry.add(state, "Urza's Saga", seat, Zone.EXILE)
    grant_exile_play_duration(state, seat, saga, 'this_turn')
    state = entry.act(state, seat, dict(type='play_land', card_id=saga, from_exile=True))
    assert state.cards[saga].zone == Zone.BATTLEFIELD
    assert saga not in state.players[seat].exile
    assert saga not in state.players[seat].exile_play_durations
    assert state.cards[saga].counters['__lore'] == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_native_extra_land_quota_allows_exactly_two_entries(seat):
    state = entry.position(seat)
    entry.add(state, 'Exploration', seat, Zone.BATTLEFIELD)
    saga = entry.add(state, "Urza's Saga", seat, Zone.HAND)
    land = entry.add(state, 'Forest', seat, Zone.HAND)
    third = entry.add(state, 'Forest', seat, Zone.HAND)
    state = entry.act(state, seat, dict(type='play_land', card_id=saga))
    state = entry.settle(state)
    state = entry.act(state, seat, dict(type='play_land', card_id=land))
    assert state.players[seat].land_plays_recorded_on_turn == 2
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, dict(type='play_land', card_id=third))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('first', ['double', 'half'])
def test_both_real_counter_orders_commit_only_the_prepared_amount(seat, first):
    state = entry.position(seat)
    saga = entry.add(state, "Urza's Saga", seat, Zone.HAND)
    entry.add(state, 'Vorinclex, Monstrous Raider', seat, Zone.BATTLEFIELD)
    entry.add(state, 'Vorinclex, Monstrous Raider', 3-seat, Zone.BATTLEFIELD)
    state = entry.act(state, seat, dict(type='play_land', card_id=saga))
    pending = state.pending_replacement_choice
    assert pending
    option = next(x for x in pending['options'] if x['operation'] == first)
    state = entry.act(entry.restored(state), pending['player_id'], dict(
        type='choose_replacement', replacement_source_id=option['source_id']))
    assert not state.pending_replacement_choice
    assert state.cards[saga].counters.get('__lore', 0) == (1 if first == 'double' else 0)
    assert len([x for x in state.stack if x.source_card_id == saga]) == (1 if first == 'double' else 0)
    assert state.players[seat].lands_played_this_turn == 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('stale', ['incarnation', 'quota', 'permission'])
def test_stale_pending_land_receipt_is_rejected_without_mutation(seat, stale):
    state = entry.position(seat)
    saga = entry.add(state, "Urza's Saga", seat, Zone.GRAVEYARD)
    grant = entry.add(state, 'Muldrotha, the Gravetide', seat, Zone.BATTLEFIELD)
    entry.add(state, 'Vorinclex, Monstrous Raider', seat, Zone.BATTLEFIELD)
    entry.add(state, 'Vorinclex, Monstrous Raider', 3-seat, Zone.BATTLEFIELD)
    key = graveyard_land_choices(state, seat, saga)[0]['key']
    state = entry.act(state, seat, dict(type='play_land', card_id=saga,
                                      from_graveyard=True, graveyard_permission_key=key))
    assert state.pending_replacement_choice
    state = entry.restored(state)
    # Adversarial snapshot changes, not legal game actions or canonical rewrites.
    if stale == 'incarnation':
        state.cards[saga].zone_change_sequence += 1
    elif stale == 'quota':
        state.players[seat].lands_played_this_turn += 1
    else:
        state.players[seat].battlefield.remove(grant)
        state.players[seat].graveyard.append(grant)
        state.cards[grant].move_to_zone(Zone.GRAVEYARD)
    pending = state.pending_replacement_choice
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), pending['player_id'], dict(
            type='choose_replacement', replacement_source_id=pending['options'][0]['source_id']))
    assert serialize_match_snapshot(state) == before
