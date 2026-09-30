"""Gameplay identities must be repeatable independently of match UUIDs."""
from copy import deepcopy
from uuid import UUID

from analytics.replay_tools import first_log_divergence, normalize_log_line
from effects.handlers import create_token, _copy_stack_object
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory
from rules_engine.stack_engine import add_to_stack


def fixture():
    deck = [{"quantity": 60, "card_name": "Island"}]
    return MatchFactory.from_decks(deck, deck, seed=74)


def test_object_ids_are_repeatable_unique_and_do_not_consume_shuffle_rng():
    left, right = fixture(), fixture()
    assert left.id != right.id
    rng = left.rng.getstate()
    ids = [left.allocate_object_id() for _ in range(100)]
    assert ids == [right.allocate_object_id() for _ in range(100)]
    assert len(set(ids)) == 100
    assert all(str(UUID(value)) == value for value in ids)
    assert left.rng.getstate() == rng


def test_token_and_stack_share_sequence_and_resume_without_reuse():
    state = fixture()
    create_token(state, 1, {"amount": 2, "name": "Soldier", "power": 1, "toughness": 1})
    tokens = list(state.players[1].battlefield)
    item = add_to_stack(state, tokens[0], 1, "Test action", "draw", {"amount": 1}, is_spell=False)
    assert len(set(tokens + [item.id])) == 3
    _copy_stack_object(state, 1, {"target_stack_id": item.id}, "ability")
    assert len(set(tokens + [entry.id for entry in state.stack])) == 4
    snapshot = serialize_match_snapshot(state)
    restored = deserialize_match_snapshot(snapshot)
    assert restored.allocate_object_id() == state.allocate_object_id()
    legacy = deepcopy(snapshot)
    legacy.pop("next_object_id")
    restored_legacy = deserialize_match_snapshot(legacy)
    assert restored_legacy.allocate_object_id() not in tokens + [entry.id for entry in state.stack]


def test_planning_clone_allocations_leave_authoritative_cursor_unchanged():
    state = fixture()
    copied = deepcopy(state)
    expected = state.next_object_id
    copied.allocate_object_id()
    assert state.next_object_id == expected
    assert copied.next_object_id == expected + 1


def test_replay_keeps_gameplay_identity_drift_but_normalizes_legacy_uuid():
    state = fixture()
    left, right = state.allocate_object_id(), state.allocate_object_id()
    assert normalize_log_line(left) == left
    assert normalize_log_line(state.id) == "<id>"
    assert first_log_divergence([f"Block {left}"], [f"Block {right}"])["index"] == 0
