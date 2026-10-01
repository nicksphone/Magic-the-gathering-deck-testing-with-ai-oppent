"""Decision-local projection reuse must not change canonical decisions."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from copy import deepcopy
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from ai.agent import AIAgent
from ai import pending_effects
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.engine import RulesEngine
from tests.test_pending_removal import fixture, add_card


def dense_removal_state():
    state, victim, _ = fixture()
    add_card(state, "Sprite Dragon", Zone.BATTLEFIELD, 2)
    for _ in range(8):
        add_card(state, "Go for the Throat", Zone.HAND)
    return state, victim


@pytest.mark.parametrize("style", ["Control", "Aggro", "Tempo", "Ramp", "Tokens", "Drain", "Tribal"])
def test_production_decision_reuses_root_projection_without_changing_action(style):
    state, _ = dense_removal_state()
    before = serialize_match_snapshot(state)
    moves = RulesEngine().legal_moves(state, 1)
    settle = pending_effects._settle_announced_stack
    with patch.object(pending_effects, "_settle_announced_stack", wraps=settle) as calls:
        cached = AIAgent(difficulty="master", archetype=style).choose_action(state, moves, 1)
        cached_calls = calls.call_count
    with patch.object(pending_effects, "decision_projection_scope", lambda *_: nullcontext()):
        with patch.object(pending_effects, "_settle_announced_stack", wraps=settle) as calls:
            uncached = AIAgent(difficulty="master", archetype=style).choose_action(state, moves, 1)
            uncached_calls = calls.call_count
    assert cached == uncached
    assert cached_calls == 1 and uncached_calls > cached_calls
    assert serialize_match_snapshot(state) == before


def test_reusing_agent_after_same_object_changes_gets_fresh_projection():
    state, victim, _ = fixture()
    observed = []
    class ObservingAgent(AIAgent):
        def _choose_action(self, state, moves, player_id):
            observed.append(pending_effects.pending_removal_destinations(state, player_id))
            return super()._choose_action(state, moves, player_id)
    agent = ObservingAgent(archetype="Control", difficulty="master")
    assert agent.choose_action(state, RulesEngine().legal_moves(state, 1), 1).action["type"] == "pass_priority"
    state.stack.clear()
    agent.choose_action(state, RulesEngine().legal_moves(state, 1), 1)
    assert observed == [{victim: Zone.GRAVEYARD}, {}]


@pytest.mark.parametrize("kind", ["known", "empty", "unknown"])
def test_none_and_empty_results_are_cached_and_returned_maps_cannot_poison_memo(kind):
    state, victim, _ = fixture("Darksteel Myr", "Naturalize") if kind == "empty" else fixture()
    if kind == "unknown":
        state.pending_mechanic_choice = {"kind": "draw", "player_id": 1}
    with patch.object(pending_effects, "_pending_removal_destinations", wraps=pending_effects._pending_removal_destinations) as compute:
        with pending_effects.decision_projection_scope(state, 1):
            result = pending_effects.pending_removal_destinations(state, 1)
            expected = None if kind == "unknown" else {} if kind == "empty" else {victim: Zone.GRAVEYARD}
            assert result == expected
            if result:
                result.clear()
            assert pending_effects.pending_removal_destinations(state, 1) == expected
        assert compute.call_count == 1
        assert pending_effects.pending_removal_destinations(state, 1) == expected
        assert compute.call_count == 2


def test_projected_states_and_other_players_do_not_reuse_root_result():
    state, victim, _ = fixture()
    alternate = deepcopy(state)
    alternate.stack.clear()
    with pending_effects.decision_projection_scope(state, 1):
        assert pending_effects.pending_removal_destinations(state, 1) == {victim: Zone.GRAVEYARD}
        assert pending_effects.pending_removal_destinations(alternate, 1) == {}
        assert pending_effects.pending_removal_destinations(state, 2) == {}
        assert pending_effects.pending_removal_destinations(state, 1) == {victim: Zone.GRAVEYARD}


def test_nested_scope_restores_outer_result_even_after_exception():
    state, victim, _ = fixture()
    alternate = deepcopy(state)
    alternate.pending_mechanic_choice = {"kind": "draw", "player_id": 1}
    with patch.object(pending_effects, "_pending_removal_destinations", wraps=pending_effects._pending_removal_destinations) as compute:
        with pending_effects.decision_projection_scope(state, 1):
            assert pending_effects.pending_removal_destinations(state, 1) == {victim: Zone.GRAVEYARD}
            with pytest.raises(RuntimeError):
                with pending_effects.decision_projection_scope(alternate, 1):
                    assert pending_effects.pending_removal_destinations(alternate, 1) is None
                    raise RuntimeError("test interruption")
            assert pending_effects.pending_removal_destinations(state, 1) == {victim: Zone.GRAVEYARD}
        assert compute.call_count == 2
        pending_effects.pending_removal_destinations(state, 1)
        assert compute.call_count == 3


def test_concurrent_decisions_have_independent_contexts():
    barrier = Barrier(2)
    left, victim, _ = fixture()
    right, _, _ = fixture("Darksteel Myr", "Naturalize")
    def query(state):
        with pending_effects.decision_projection_scope(state, 1):
            barrier.wait(timeout=10)
            first = pending_effects.pending_removal_destinations(state, 1)
            barrier.wait(timeout=10)
            return first, pending_effects.pending_removal_destinations(state, 1)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = pool.submit(query, left), pool.submit(query, right)
        assert a.result(timeout=20) == ({victim: Zone.GRAVEYARD}, {victim: Zone.GRAVEYARD})
        assert b.result(timeout=20) == ({}, {})


def test_planning_copy_omits_only_history_and_preserves_rng_choices_and_source_state():
    state, _, _ = fixture()
    state.log.extend(["Diagnostic history"] * 10000)
    before = serialize_match_snapshot(state)
    copied = pending_effects.planning_copy(state)
    expected = {**before, "log": []}
    assert serialize_match_snapshot(copied) == expected
    copied.log.append("New speculative action")
    copied.players[1].mana_pool["U"] = 999
    assert serialize_match_snapshot(state) == before
    lightweight = SimpleNamespace(log=None, payload=None)
    assert pending_effects.planning_copy(lightweight).payload is None


def test_fast_card_copy_preserves_aliases_cycles_and_isolates_mutable_fields():
    state, victim, held = fixture()
    shared = [{"name": "Face", "keywords": ["flying"], "extra": {"nested": [1]}}]
    state.cards[victim].card_faces = shared
    state.cards[held].card_faces = shared
    state.cards[victim].test_cycle = state.cards[held]
    state.cards[held].test_cycle = state.cards[victim]
    state.cards[victim].test_attributes = state.cards[held].__dict__
    reference = deepcopy(state)
    reference.log = []
    clone = pending_effects.planning_copy(state)
    assert serialize_match_snapshot(clone) == serialize_match_snapshot(reference)
    assert clone.cards[victim].card_faces is clone.cards[held].card_faces
    assert clone.cards[victim].test_cycle is clone.cards[held]
    assert clone.cards[held].test_cycle is clone.cards[victim]
    assert clone.cards[victim].test_attributes is clone.cards[held].__dict__
    clone.cards[victim].card_faces[0]["extra"]["nested"].append(2)
    clone.cards[victim].keywords.append("haste")
    clone.cards[victim].counters["+1/+1"] = 5
    assert state.cards[victim].card_faces[0]["extra"]["nested"] == [1]
    assert "haste" not in state.cards[victim].keywords
    assert "+1/+1" not in state.cards[victim].counters


@pytest.mark.parametrize("value", [[], {}, set(), ["G", 2, None, Zone.BATTLEFIELD],
                                  {"+1/+1": 3}, {"flying", "haste"}, [[1]], {"nested": [1]}])
def test_flat_field_copy_matches_deepcopy_and_preserves_shared_alias(value):
    memo = {}
    cloned = pending_effects._copy_card_field(value, memo)
    assert cloned == deepcopy(value) and cloned is not value
    assert pending_effects._copy_card_field(value, memo) is cloned
    if isinstance(value, list):
        cloned.append("new")
        assert cloned != value
    elif isinstance(value, dict):
        cloned["new"] = 1
        assert "new" not in value
    else:
        cloned.add("new")
        assert "new" not in value


def test_flat_container_aliases_cross_cards_and_player_zones_without_leaking():
    state, victim, held = fixture()
    shared = ["flying"]
    state.cards[victim].keywords = state.cards[held].keywords = shared
    state.cards[victim].test_hand_alias = state.players[1].hand
    clone = pending_effects.planning_copy(state)
    assert clone.cards[victim].keywords is clone.cards[held].keywords
    assert clone.cards[victim].test_hand_alias is clone.players[1].hand
    clone.cards[victim].keywords.append("haste")
    clone.cards[victim].test_hand_alias.clear()
    assert shared == ["flying"] and state.players[1].hand


def test_container_subclass_retains_its_custom_deepcopy_contract():
    class CustomList(list):
        def __deepcopy__(self, memo):
            result = CustomList(["custom"])
            memo[id(self)] = result
            return result
    original = CustomList(["flying"])
    clone = pending_effects._copy_card_field(original, {})
    assert type(clone) is CustomList and clone == ["custom"]


def test_nested_cycles_and_mutable_scalar_subclasses_use_deepcopy():
    nested = []
    nested.append(nested)
    clone = pending_effects._copy_card_field(nested, {})
    assert clone is not nested and clone[0] is clone
    class MutableString(str):
        pass
    value = MutableString("flying")
    value.extra = [1]
    clone = pending_effects._copy_card_field([value], {})
    clone[0].extra.append(2)
    assert value.extra == [1]


@pytest.mark.parametrize("reference_mode", ["full", "copy-only", "card-fields", "hotpaths"])
def test_benchmark_checks_full_decision_and_state_without_timing_threshold(reference_mode):
    from scripts.benchmark_ai_decisions import benchmark
    state, _ = dense_removal_state()
    result = benchmark(serialize_match_snapshot(state), 1, iterations=2,
                       opponent_archetype="Tempo", reference_mode=reference_mode)
    assert result["actions_and_reasoning_equal"] and result["authoritative_state_unchanged"]
    assert result["timing"]["optimized"]["settle_calls"] == [1, 1]
    assert result["opponent_archetype"] == "Tempo"
    reference_key = {"full": "reference_ablation", "copy-only": "reference_copy", "card-fields": "reference_card_fields", "hotpaths": "reference_hotpaths"}[reference_mode]
    assert all(count > 1 if reference_mode == "full" else count == 1
               for count in result["timing"][reference_key]["settle_calls"])
    with pytest.raises(ValueError):
        benchmark(serialize_match_snapshot(state), 1, iterations=0)
    with pytest.raises(ValueError):
        benchmark(serialize_match_snapshot(state), 1, reference_mode="unknown")
