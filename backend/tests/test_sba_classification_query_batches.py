"""Bounded per-card SBA query reuse with canonical attachment/state-change controls."""
from contextlib import contextmanager, nullcontext
from copy import deepcopy
from unittest.mock import patch

import pytest

from effects.registry import resolve_effect
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone
from rules_engine import bestow, land_types, state_based_actions as sba
from rules_engine.attachments import is_aura, is_equipment, is_fortification
from rules_engine.bestow import is_bestowed
from rules_engine.query_context import query_cache, rule_query_scope
from tests.test_basic_land_hooks import add, attached, cast_song
from tests.test_basic_land_layer_goldens import position


def reference(state):
    # Only this function's new classification scope is disabled, not other SBA scopes.
    with patch.object(sba, 'rule_query_scope', lambda state: nullcontext()):
        sba._apply_attachment_state_checks(state)


def check_wave(state):
    baseline = deepcopy(state)
    candidate = deepcopy(state)
    reference(baseline)
    scopes = []

    @contextmanager
    def bounded(current):
        assert current is candidate
        assert query_cache(current) is None
        before = serialize_match_snapshot(current)
        with rule_query_scope(current):
            yield
            assert serialize_match_snapshot(current) == before
        assert query_cache(current) is None
        scopes.append(before)

    original_legal = sba.attachment_target_is_legal
    original_grave = sba.put_into_graveyard
    original_end_bestow = bestow.end_bestow

    def end_bestow(card):
        assert query_cache(candidate) is None
        return original_end_bestow(card)

    def outside(function):
        def call(current, *args, **kwargs):
            assert query_cache(current) is None
            return function(current, *args, **kwargs)
        return call

    with patch.object(sba, 'rule_query_scope', bounded), \
         patch.object(sba, 'attachment_target_is_legal', outside(original_legal)), \
         patch.object(sba, 'put_into_graveyard', outside(original_grave)), \
         patch.object(bestow, 'end_bestow', end_bestow):
        sba._apply_attachment_state_checks(candidate)
    assert len(scopes) == sum(card.zone == Zone.BATTLEFIELD for card in state.cards.values())
    assert serialize_match_snapshot(candidate) == serialize_match_snapshot(baseline)
    restarted = deserialize_match_snapshot(serialize_match_snapshot(candidate))
    reference(restarted)
    again = deepcopy(candidate)
    sba._apply_attachment_state_checks(again)
    assert serialize_match_snapshot(again) == serialize_match_snapshot(restarted)
    assert query_cache(candidate) is None
    return candidate


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Bonesplitter', 'Leafcrown Dryad', 'Spreading Seas'])
def test_actual_canonical_attachment_and_song_resolution_refresh(seat, name):
    state = position(seat)
    host = add(state, 'Forest' if name == 'Spreading Seas' else 'Royal Assassin', seat)
    state, cid = attached(state, name, seat, host)
    state = check_wave(state)
    state = cast_song(state, cid, seat)
    assert state.cards[cid].zone == Zone.BATTLEFIELD
    assert state.cards[cid].attached_to is None
    state = check_wave(state)
    song = next(card for card in state.cards.values()
                if card.name == 'Song of the Dryads' and card.attached_to == cid)
    # Controlled removal seam, not a claimed legally cast removal spell.
    resolve_effect(state, seat, 'destroy_permanent', {'target_card_id': song.id})
    state = check_wave(state)
    card = state.cards[cid]
    if name == 'Bonesplitter':
        assert is_equipment(card, state) and card.attached_to is None
    elif name == 'Leafcrown Dryad':
        assert not is_bestowed(card) and not is_aura(card, state)
        assert card.zone == Zone.BATTLEFIELD
    else:
        assert card.zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_source_death_between_cards_restores_later_equipment(seat):
    state = position(seat)
    host = add(state, 'Royal Assassin', seat)
    state, cid = attached(state, 'Bonesplitter', seat, host)
    state = cast_song(state, cid, seat)
    song = next(card for card in state.cards.values()
                if card.name == 'Song of the Dryads' and card.attached_to == cid)
    # Controlled invalid-attachment/order fixture: Song dies earlier in this wave.
    song.attached_to = None
    state.cards = {song.id: song, **{key: value for key, value in state.cards.items() if key != song.id}}
    state = check_wave(state)
    assert state.cards[song.id].zone == Zone.GRAVEYARD
    assert is_equipment(state.cards[cid], state)
    assert state.cards[cid].attached_to is None


@pytest.mark.parametrize('seat', [1, 2])
def test_control_change_and_host_departure_between_waves(seat):
    state = position(seat)
    host = add(state, 'Royal Assassin', seat)
    state, cid = attached(state, 'Bonesplitter', seat, host)
    state = check_wave(state)
    # Controlled controller change; attachment persists until a real legality change.
    state.players[seat].battlefield.remove(cid)
    state.players[3-seat].battlefield.append(cid)
    state.cards[cid].controller = 3-seat
    state = check_wave(state)
    assert state.cards[cid].attached_to == host.id
    resolve_effect(state, seat, 'destroy_permanent', {'target_card_id': host.id})
    state = check_wave(state)
    assert state.cards[cid].zone == Zone.BATTLEFIELD
    assert state.cards[cid].attached_to is None


@pytest.mark.parametrize('seat', [1, 2])
def test_bestow_ends_outside_scope_when_host_leaves(seat):
    state = position(seat)
    host = add(state, 'Royal Assassin', seat)
    state, cid = attached(state, 'Leafcrown Dryad', seat, host)
    # Controlled departure, then the real attachment SBA ends bestow.
    state.players[seat].battlefield.remove(host.id)
    state.players[seat].graveyard.append(host.id)
    state.cards[host.id].move_to_zone(Zone.GRAVEYARD)
    state = check_wave(state)
    assert not is_bestowed(state.cards[cid])
    assert state.cards[cid].zone == Zone.BATTLEFIELD
    assert state.cards[cid].attached_to is None


@pytest.mark.parametrize('seat', [1, 2])
def test_three_classifiers_share_only_this_cards_layer_query(seat):
    state = position(seat)
    add(state, 'Bonesplitter', seat)
    before = serialize_match_snapshot(state)
    with patch.object(land_types, 'land_type_instructions', wraps=land_types.land_type_instructions) as queries:
        reference(deepcopy(state))
        baseline_calls = queries.call_count
    with patch.object(land_types, 'land_type_instructions', wraps=land_types.land_type_instructions) as queries:
        sba._apply_attachment_state_checks(state)
        assert queries.call_count < baseline_calls
    assert serialize_match_snapshot(state) == before
    assert query_cache(state) is None
    assert not is_aura(state.cards[next(iter(state.cards))], state)
    assert not is_fortification(state.cards[next(iter(state.cards))], state)
