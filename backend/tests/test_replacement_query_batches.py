"""Replacement source construction reuses only an immutable query batch."""
from contextlib import contextmanager, nullcontext
from copy import deepcopy
from unittest.mock import patch

import pytest

from ai.information import decision_view
from effects.registry import resolve_effect
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from rules_engine import land_types, replacement
from rules_engine.continuous import printed_abilities_suppressed
from rules_engine.query_context import query_cache, rule_query_scope
from tests.test_basic_land_hooks import cast_song
from tests.test_basic_land_layer_goldens import add, position
from tests.test_life_conversion import permanent


def rows(state, **kwargs):
    return [(card.id, text) for card, text in replacement._battlefield_oracle_texts(state, **kwargs)]


def reference(state, **kwargs):
    with patch.object(replacement, 'rule_query_scope', side_effect=lambda _: nullcontext(), create=True):
        return rows(state, **kwargs)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('controller', [None, 1, 2])
@pytest.mark.parametrize('filtered', [False, True])
def test_exact_order_controller_and_filter_parity_without_state_writes(seat, controller, filtered):
    state = position(seat)
    for name, owner in [('River Boa', seat), ('Blood Artist', 3-seat),
                        ('Hallowed Fountain', seat), ('Blood Moon', 3-seat), ('Humility', seat)]:
        add(state, name, owner)
    before = serialize_match_snapshot(state)
    options = {'controller': controller}
    if filtered:
        options['text_filter'] = lambda text: 'creature' in text
    assert rows(state, **options) == reference(state, **options)
    assert serialize_match_snapshot(state) == before
    assert query_cache(state) is None


@pytest.mark.parametrize('seat', [1, 2])
def test_real_layer_scan_work_is_reduced_not_source_rows(seat):
    state = position(seat)
    for index in range(8):
        add(state, 'Llanowar Elves', seat if index % 2 else 3-seat)
    original = land_types.land_type_instructions
    with patch.object(land_types, 'land_type_instructions', wraps=original) as query:
        expected = reference(state)
        baseline = query.call_count
    with patch.object(land_types, 'land_type_instructions', wraps=original) as query:
        assert rows(state) == expected
        assert 0 < query.call_count < baseline / 2
    assert len(expected) == 8


@pytest.mark.parametrize('seat', [1, 2])
def test_scope_closed_before_yield_and_source_departure_refreshes_new_scan(seat):
    state = position(seat)
    elf = add(state, 'Llanowar Elves', seat)
    humility = add(state, 'Humility', 3-seat)
    iterator = replacement._battlefield_oracle_texts(state)
    first, _ = next(iterator)
    assert first.id == humility.id
    assert query_cache(state) is None
    # Controlled departure between yields; the old list intentionally stays captured.
    resolve_effect(state, seat, 'destroy_permanent', {'target_card_id': humility.id})
    assert not printed_abilities_suppressed(state, elf.id)
    assert list(iterator) == []
    assert [cid for cid, _ in rows(state)] == [elf.id]
    assert query_cache(state) is None


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_song_resolution_and_controlled_removal_refresh_game_loss_source(seat):
    state = position(seat)
    angel = permanent(state, 'platinum-angel', seat)
    assert replacement.player_cant_lose_game(state, seat)
    state = cast_song(state, angel.id, seat)
    assert not replacement.player_cant_lose_game(state, seat)
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert not replacement.player_cant_lose_game(state, seat)
    song = next(card for card in state.cards.values()
                if card.name == 'Song of the Dryads' and card.attached_to == angel.id)
    # This is a controlled effect seam, not an announced spell episode.
    resolve_effect(state, seat, 'destroy_permanent', {'target_card_id': song.id})
    assert replacement.player_cant_lose_game(state, seat)
    assert query_cache(state) is None


@pytest.mark.parametrize('seat', [1, 2])
def test_each_construction_scope_is_immutable_and_nests_without_leaking(seat):
    state = position(seat)
    add(state, 'Royal Assassin', seat)
    add(state, 'Humility', 3-seat)
    scopes = []

    @contextmanager
    def audited_scope(current):
        before = serialize_match_snapshot(current)
        with rule_query_scope(current):
            yield
            assert serialize_match_snapshot(current) == before
        scopes.append(before)

    with patch.object(replacement, 'rule_query_scope', side_effect=audited_scope, create=True):
        iterator = replacement._battlefield_oracle_texts(state)
        next(iterator)
        assert len(scopes) == 1 and query_cache(state) is None
        iterator.close()
        with rule_query_scope(state):
            cache = query_cache(state)
            assert rows(state)
            assert query_cache(state) is cache
    assert query_cache(state) is None


def test_filter_exception_resets_query_scope():
    state = position(1)
    add(state, 'Royal Assassin', 1)

    def fail(text):
        raise ValueError('filter failed')

    with pytest.raises(ValueError, match='filter failed'):
        rows(state, text_filter=fail)
    assert query_cache(state) is None


@pytest.mark.parametrize('seat', [1, 2])
def test_private_opponent_metadata_cannot_affect_source_scan(seat):
    state = position(seat)
    add(state, 'River Boa', seat)
    add(state, 'Humility', 3-seat)
    before = serialize_match_snapshot(state)
    changed = deepcopy(state)
    opponent = changed.players[3-seat]
    for cid in opponent.hand + opponent.library:
        changed.cards[cid].oracle_text = 'private counterfactual, not a gameplay card'
        changed.cards[cid].colors = ['R']
    assert rows(changed) == rows(state)
    view, _ = decision_view(state, seat, [])
    alternative, _ = decision_view(changed, seat, [])
    assert serialize_match_snapshot(view) == serialize_match_snapshot(alternative)
    assert serialize_match_snapshot(state) == before
