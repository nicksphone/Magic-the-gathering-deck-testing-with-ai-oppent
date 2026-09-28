from __future__ import annotations

import json

import pytest

from ai.agent import AIAgent
from analytics.decision_quality import (
    build_decision_quality_artifact,
    build_trace_payload,
    summarize_trace_rows,
)
from analytics.service import AnalyticsService
from game_state.serializers import serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine
from rules_engine.prevention import add_player_prevention_shield
from scripts import overnight_verbose_round_robin


class _DummyRepo:
    def save_snapshot(self, label: str, stats: dict) -> None:
        self.last = (label, stats)


def _attack_trace_state(*, power: int, opponent_life: int, keywords: list[str] | None = None):
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = 1
    state.step = Step.DECLARE_ATTACKERS
    attacker_id = state.players[1].hand.pop()
    state.players[1].battlefield.append(attacker_id)
    attacker = state.cards[attacker_id]
    attacker.zone = Zone.BATTLEFIELD
    attacker.types = ["Creature"]
    attacker.power = power
    attacker.toughness = power
    attacker.keywords = keywords or []
    attacker.summoning_sick = False
    state.players[2].life = opponent_life
    return state, attacker_id


def test_trace_payload_uses_resolved_double_strike_damage_for_lethal() -> None:
    state, _ = _attack_trace_state(power=2, opponent_life=4, keywords=["double strike"])
    legal = RulesEngine().legal_moves(state, 1)

    payload = build_trace_payload(state, 1, legal, {"type": "pass_priority"})

    assert payload["lethal_attack_available"] is True


def test_trace_payload_uses_damage_prevention_for_lethal() -> None:
    state, _ = _attack_trace_state(power=4, opponent_life=4)
    add_player_prevention_shield(state, 2, 1)
    legal = RulesEngine().legal_moves(state, 1)

    payload = build_trace_payload(state, 1, legal, {"type": "pass_priority"})

    assert payload["lethal_attack_available"] is False


def _block_trace_state(
    *,
    attacker_power: int = 3,
    attacker_toughness: int = 3,
    attacker_keywords: list[str] | None = None,
    blocker_power: int = 1,
    blocker_toughness: int = 1,
    blocker_keywords: list[str] | None = None,
):
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.priority_player = 2
    state.step = Step.DECLARE_BLOCKERS

    attacker_id = state.players[1].hand.pop()
    blocker_id = state.players[2].hand.pop()
    for player_id, card_id, power, toughness, keywords in (
        (1, attacker_id, attacker_power, attacker_toughness, attacker_keywords),
        (2, blocker_id, blocker_power, blocker_toughness, blocker_keywords),
    ):
        state.players[player_id].battlefield.append(card_id)
        card = state.cards[card_id]
        card.zone = Zone.BATTLEFIELD
        card.types = ["Creature"]
        card.power = power
        card.toughness = toughness
        card.summoning_sick = False
        card.keywords = keywords or []
    state.attackers = [attacker_id]
    state.attack_targets = {attacker_id: "player:2"}
    state.attackers_declared = True
    return state, attacker_id, blocker_id


def test_trace_payload_counts_ordinary_losing_block_from_resolved_combat() -> None:
    state, attacker_id, blocker_id = _block_trace_state()
    action = {"type": "block", "blocks": {attacker_id: blocker_id}}

    payload = build_trace_payload(state, 2, RulesEngine().legal_moves(state, 2), action)

    assert payload["bad_blocks"] == 1


def test_trace_board_includes_effective_keywords_and_marked_damage() -> None:
    state, attacker_id, blocker_id = _block_trace_state(
        attacker_power=1, attacker_toughness=1, attacker_keywords=["deathtouch"],
        blocker_power=4, blocker_toughness=5,
    )
    state.cards[blocker_id].counters["__damage_marked"] = 2

    payload = build_trace_payload(state, 2, RulesEngine().legal_moves(state, 2), {"type": "pass_priority"})

    own = next(card for card in payload["battlefield"] if card["id"] == blocker_id)
    opponent = next(card for card in payload["opp_battlefield"] if card["id"] == attacker_id)
    assert own["damage_marked"] == 2
    assert "deathtouch" in opponent["keywords"]


def test_trace_payload_does_not_call_lethal_preventing_chump_a_bad_block() -> None:
    state, attacker_id, blocker_id = _block_trace_state(attacker_power=5, attacker_toughness=5)
    state.players[2].life = 5
    action = {"type": "block", "blocks": {attacker_id: blocker_id}}

    payload = build_trace_payload(state, 2, RulesEngine().legal_moves(state, 2), action)

    assert payload["bad_blocks"] == 0


def test_trace_payload_does_not_call_deathtouch_trade_a_bad_block() -> None:
    state, attacker_id, blocker_id = _block_trace_state(
        attacker_power=5,
        attacker_toughness=5,
        blocker_power=1,
        blocker_toughness=1,
        blocker_keywords=["deathtouch"],
    )
    action = {"type": "block", "blocks": {attacker_id: blocker_id}}

    payload = build_trace_payload(state, 2, RulesEngine().legal_moves(state, 2), action)

    assert payload["bad_blocks"] == 0


def test_trace_payload_uses_first_strike_combat_outcome() -> None:
    state, attacker_id, blocker_id = _block_trace_state(
        attacker_power=2,
        attacker_toughness=2,
        attacker_keywords=["first strike"],
        blocker_power=2,
        blocker_toughness=2,
    )
    action = {"type": "block", "blocks": {attacker_id: blocker_id}}

    payload = build_trace_payload(state, 2, RulesEngine().legal_moves(state, 2), action)

    assert payload["bad_blocks"] == 1


def test_trace_payload_combat_evidence_does_not_mutate_original_state() -> None:
    state, attacker_id, blocker_id = _block_trace_state()
    before = serialize_match_snapshot(state)
    action = {"type": "block", "blocks": {attacker_id: blocker_id}}

    build_trace_payload(state, 2, RulesEngine().legal_moves(state, 2), action)

    assert serialize_match_snapshot(state) == before


def test_decision_quality_overall_ignores_nonparticipating_pool_decks() -> None:
    metrics = {
        "missed_land_drops": 1,
        "unused_mana_passes": 2,
        "lethal_misses": 3,
        "bad_blocks": 4,
        "stall_streaks": 5,
    }
    availability = {metric: True for metric in metrics}
    decks = [
        {"id": 1, "name": "Deck A"},
        {"id": 2, "name": "Deck B"},
        {"id": 3, "name": "Deck C"},
    ]

    artifact = build_decision_quality_artifact(
        decks,
        [{"decks": [
            {
                "deck_key": "source::id:int:1",
                "counts": metrics,
                "availability": availability,
            },
            {
                "deck_key": "source::id:int:2",
                "counts": metrics,
                "availability": availability,
            },
        ]}],
    )

    assert all(value is None for value in artifact["per_deck"][2]["metrics"].values())
    assert artifact["overall"] == {metric: value * 2 for metric, value in metrics.items()}
    assert artifact["unavailable_metrics"] == {}


def test_decision_quality_malformed_trace_invalidates_all_metrics() -> None:
    complete_rows = [
        "AI TRACE " + json.dumps({
            "pid": pid,
            "step": "Step.UPKEEP",
            "legal_non_pass": False,
            "stall_actionable_options": False,
            "mana_pool": {},
            "action": {"type": "pass_priority"},
        })
        for pid in (1, 2)
    ]
    summary = summarize_trace_rows(({"log": [*complete_rows, "AI TRACE {not-json"]},))

    assert all(not available for pid in ("1", "2") for available in summary["availability"][pid].values())


def test_decision_quality_complete_non_applicable_windows_are_measured_zero() -> None:
    traces = [
        "AI TRACE " + json.dumps({
            "pid": pid,
            "step": "Step.UPKEEP",
            "legal_non_pass": False,
            "stall_actionable_options": False,
            "mana_pool": {},
            "action": {"type": "pass_priority"},
        })
        for pid in (1, 2)
    ]

    summary = summarize_trace_rows(({"log": traces},))

    assert all(available for pid in ("1", "2") for available in summary["availability"][pid].values())
    assert all(count == 0 for pid in ("1", "2") for count in summary["counts"][pid].values())


def _complete_trace(pid: int, turn: int, step: str, action_type: str, **fields: object) -> str:
    payload = {
        "pid": pid,
        "turn": turn,
        "step": step,
        "legal_non_pass": False,
        "legal_has_land": False,
        "stall_actionable_options": False,
        "mana_pool": {},
        "action": {"type": action_type},
        **fields,
    }
    return "AI TRACE " + json.dumps(payload)


def test_missed_land_drop_is_cleared_by_later_land_play_same_turn() -> None:
    summary = summarize_trace_rows(({"log": [
        _complete_trace(1, 3, "Step.PRECOMBAT_MAIN", "cast_spell", legal_non_pass=True, legal_has_land=True),
        _complete_trace(1, 3, "Step.PRECOMBAT_MAIN", "play_land", legal_non_pass=True, legal_has_land=True),
        _complete_trace(1, 3, "Step.END_STEP", "pass_priority"),
        _complete_trace(2, 3, "Step.UPKEEP", "pass_priority"),
    ]},))

    assert summary["counts"]["1"]["missed_land_drops"] == 0
    assert summary["availability"]["1"]["missed_land_drops"] is True


def test_missed_land_drop_counts_once_per_player_turn() -> None:
    summary = summarize_trace_rows(({"log": [
        _complete_trace(1, 3, "Step.PRECOMBAT_MAIN", "pass_priority", legal_non_pass=True, legal_has_land=True),
        _complete_trace(1, 3, "Step.PRECOMBAT_MAIN", "pass_priority", legal_non_pass=True, legal_has_land=True),
        _complete_trace(1, 3, "Step.END_STEP", "pass_priority"),
        _complete_trace(1, 5, "Step.POSTCOMBAT_MAIN", "cast_spell", legal_non_pass=True, legal_has_land=True),
        _complete_trace(1, 5, "Step.END_STEP", "pass_priority"),
        _complete_trace(2, 4, "Step.UPKEEP", "pass_priority"),
    ]},))

    assert summary["counts"]["1"]["missed_land_drops"] == 2


def test_incomplete_turn_does_not_count_as_a_missed_land_drop() -> None:
    summary = summarize_trace_rows(({"log": [
        _complete_trace(
            1,
            3,
            "Step.PRECOMBAT_MAIN",
            "cast_spell",
            legal_non_pass=True,
            legal_has_land=True,
        ),
        _complete_trace(2, 3, "Step.UPKEEP", "pass_priority"),
    ]},))

    assert summary["counts"]["1"]["missed_land_drops"] == 0


def test_missing_turn_makes_relevant_land_metric_unavailable() -> None:
    trace = json.loads(_complete_trace(1, 3, "Step.PRECOMBAT_MAIN", "cast_spell", legal_has_land=True)[9:])
    trace.pop("turn")
    summary = summarize_trace_rows(({"log": [
        "AI TRACE " + json.dumps(trace),
        _complete_trace(2, 3, "Step.UPKEEP", "pass_priority"),
    ]},))

    assert summary["availability"]["1"]["missed_land_drops"] is False


@pytest.mark.parametrize("malformed_mana", ["bogus", None, [], {"nested": 1}])
def test_decision_quality_malformed_mana_only_invalidates_unused_mana(
    malformed_mana: object,
) -> None:
    malformed = {
        "pid": 1,
        "step": "Step.UPKEEP",
        "legal_non_pass": True,
        "stall_actionable_options": False,
        "mana_pool": {"U": malformed_mana},
        "action": {"type": "pass_priority"},
    }
    complete = {
        "pid": 2,
        "step": "Step.UPKEEP",
        "legal_non_pass": False,
        "stall_actionable_options": False,
        "mana_pool": {},
        "action": {"type": "pass_priority"},
    }

    summary = summarize_trace_rows(
        ({"log": ["AI TRACE " + json.dumps(malformed), "AI TRACE " + json.dumps(complete)]},)
    )

    assert summary["availability"]["1"]["unused_mana_passes"] is False
    assert all(
        available
        for metric, available in summary["availability"]["1"].items()
        if metric != "unused_mana_passes"
    )
    assert all(summary["availability"]["2"].values())


_MISSING_ACTION = object()


@pytest.mark.parametrize(
    "action",
    [
        pytest.param(_MISSING_ACTION, id="missing-action"),
        pytest.param(None, id="null-action"),
        pytest.param({}, id="missing-action-type"),
        pytest.param({"type": None}, id="null-action-type"),
        pytest.param({"type": 7}, id="non-string-action-type"),
        pytest.param({"type": ""}, id="empty-action-type"),
    ],
)
def test_decision_quality_invalid_action_makes_stall_evidence_unavailable(
    action: object,
) -> None:
    invalid = {
        "pid": 1,
        "step": "Step.UPKEEP",
        "legal_non_pass": False,
        "stall_actionable_options": False,
        "mana_pool": {},
    }
    if action is not _MISSING_ACTION:
        invalid["action"] = action
    complete = {
        "pid": 2,
        "step": "Step.UPKEEP",
        "legal_non_pass": False,
        "stall_actionable_options": False,
        "mana_pool": {},
        "action": {"type": "pass_priority"},
    }

    summary = summarize_trace_rows(
        ({"log": ["AI TRACE " + json.dumps(invalid), "AI TRACE " + json.dumps(complete)]},)
    )

    assert summary["availability"]["1"]["stall_streaks"] is False
    assert all(summary["availability"]["2"].values())


@pytest.mark.parametrize(
    ("metric", "trace"),
    [
        (
            "missed_land_drops",
            {"pid": 1, "step": "Step.PRECOMBAT_MAIN", "legal_non_pass": True,
             "stall_actionable_options": False, "action": {"type": "cast_spell"}},
        ),
        (
            "unused_mana_passes",
            {"pid": 1, "step": "Step.UPKEEP", "legal_non_pass": False,
             "stall_actionable_options": False, "action": {"type": "pass_priority"}},
        ),
        (
            "lethal_misses",
            {"pid": 1, "step": "Step.DECLARE_ATTACKERS", "lethal_attack_available": "false",
             "stall_actionable_options": False, "action": {"type": "attack"}},
        ),
        (
            "bad_blocks",
            {"pid": 1, "step": "Step.DECLARE_BLOCKERS",
             "stall_actionable_options": False,
             "battlefield": [{"id": "b", "power": 1, "toughness": 1}],
             "opp_battlefield": [{"id": "a", "power": 3, "toughness": 3}],
             "action": {"type": "block", "blocks": {"a": "b"}}},
        ),
        (
            "stall_streaks",
            {"pid": 1, "step": "Step.UPKEEP", "legal_non_pass": False, "mana_pool": {},
             "action": {"type": "pass_priority"}},
        ),
    ],
)
def test_decision_quality_partial_trace_only_invalidates_affected_metric(metric: str, trace: dict) -> None:
    base = {
        "pid": 2,
        "step": "Step.UPKEEP",
        "legal_non_pass": False,
        "stall_actionable_options": False,
        "mana_pool": {},
        "action": {"type": "pass_priority"},
    }

    summary = summarize_trace_rows(({"log": [
        "AI TRACE " + json.dumps(trace),
        "AI TRACE " + json.dumps(base),
    ]},))

    assert summary["availability"]["1"][metric] is False
    assert all(
        available
        for other_metric, available in summary["availability"]["1"].items()
        if other_metric != metric
    )


def test_batch_does_not_auto_award_unresolved_games_to_deck_a() -> None:
    repo = _DummyRepo()
    service = AnalyticsService(repo)  # type: ignore[arg-type]
    deck_a = [{"quantity": 60, "card_name": "Island"}]
    deck_b = [{"quantity": 60, "card_name": "Island"}]
    out = service.run_batch(deck_a, deck_b, matches=5, difficulty="master", max_ticks=1)
    assert out["win_rate_deck_a"] == 0
    assert out["win_rate_deck_b"] == 0
    assert out["timeouts"] == 5
    assert out["resolved_games"] == 0
    assert all(item["kind"] == "insufficient_sample" for item in out["balance_alerts"])
    assert isinstance(out["sample_turn_summaries"], list)
    assert isinstance(out["sample_log_excerpt"], list)
    assert isinstance(out["game_results"], list)
    assert out["rules_coverage"] == {"status": "exploratory", "known_unsupported_cards": []}


def test_batch_result_names_known_unsupported_card_without_certifying_others() -> None:
    repo = _DummyRepo()
    service = AnalyticsService(repo)  # type: ignore[arg-type]
    deck_a = [{"quantity": 60, "card_name": "Old Fogey", "oracle_text": "bands with other Dinosaurs", "type_line": "Summon — Dinosaur", "power": 7, "toughness": 7}]
    deck_b = [{"quantity": 60, "card_name": "Island"}]

    out = service.run_batch(deck_a, deck_b, matches=1, difficulty="master", max_ticks=1)

    assert out["rules_coverage"] == {
        "status": "exploratory",
        "known_unsupported_cards": [{"deck": "A", "card_name": "Old Fogey", "mechanics": ["bands with other"]}],
    }


def test_batch_result_checks_oracle_for_known_gap() -> None:
    repo = _DummyRepo()
    service = AnalyticsService(repo)  # type: ignore[arg-type]
    deck_a = [{"quantity": 60, "card_name": "Willbender", "oracle_text": "Morph {1}{U}"}]
    deck_b = [{"quantity": 60, "card_name": "Island"}]

    out = service.run_batch(deck_a, deck_b, matches=1, difficulty="master", max_ticks=1)

    assert out["rules_coverage"]["known_unsupported_cards"] == [
        {"deck": "A", "card_name": "Willbender", "mechanics": ["morph"]}
    ]


def test_batch_summary_exports_decision_quality_with_honest_unavailable_metrics() -> None:
    repo = _DummyRepo()
    service = AnalyticsService(repo)  # type: ignore[arg-type]
    deck_a = [{"quantity": 60, "card_name": "Island"}]
    deck_b = [{"quantity": 60, "card_name": "Swamp"}]

    out = service.run_batch(deck_a, deck_b, matches=1, difficulty="master", max_ticks=1)

    expected_metrics = {
        "missed_land_drops",
        "unused_mana_passes",
        "lethal_misses",
        "bad_blocks",
        "stall_streaks",
    }
    decision_quality = out["decision_quality"]
    assert [(row["deck_name"], row["deck_key"]) for row in decision_quality["per_deck"]] == [
        ("Deck A", "pool:0"),
        ("Deck B", "pool:1"),
    ]
    assert all(row["deck_id"] is None for row in decision_quality["per_deck"])
    assert all(set(row["metrics"]) == expected_metrics for row in decision_quality["per_deck"])
    assert set(decision_quality["overall"]) == expected_metrics
    assert all(value == 0 for value in decision_quality["per_deck"][0]["metrics"].values())
    assert decision_quality["per_deck"][0]["unavailable_metrics"] == {}
    assert all(value is None for value in decision_quality["per_deck"][1]["metrics"].values())
    assert set(decision_quality["per_deck"][1]["unavailable_metrics"]) == expected_metrics
    assert all(value is None for value in decision_quality["overall"].values())
    assert set(decision_quality["unavailable_metrics"]) == expected_metrics
    assert repo.last == ("batch_simulation", out)


def test_batch_retains_only_compact_decision_evidence(monkeypatch) -> None:
    repo = _DummyRepo()
    service = AnalyticsService(repo)  # type: ignore[arg-type]
    retained: list[dict] = []
    original = AnalyticsService._decision_quality_summary

    def capture(games):
        retained.extend(games)
        return original(games)

    monkeypatch.setattr(service, "_decision_quality_summary", capture)
    deck = [{"quantity": 60, "card_name": "Island"}]

    service.run_batch(deck, deck, matches=2, difficulty="master", max_ticks=1)

    assert retained
    assert all("log" not in game and "decks" in game for game in retained)
    assert "AI TRACE" not in json.dumps(retained)


def test_batch_and_overnight_decision_quality_share_exact_schema() -> None:
    complete = {
        metric: True
        for metric in (
            "missed_land_drops",
            "unused_mana_passes",
            "lethal_misses",
            "bad_blocks",
            "stall_streaks",
        )
    }
    batch = AnalyticsService._decision_quality_summary(
        [({"log": []}, True)]
    )
    decks = [
        {"id": 1, "name": "Deck A", "archetype": "Aggro"},
        {"id": 2, "name": "Deck B", "archetype": "Control"},
    ]
    overnight = overnight_verbose_round_robin._decision_quality_artifact(  # type: ignore[attr-defined]
        [{"decks": {
            overnight_verbose_round_robin._deck_quality_key(deck): {  # type: ignore[attr-defined]
                "counts": {},
                "availability": complete,
            }
            for deck in decks
        }}],
        decks,
    )

    assert set(batch) == set(overnight) == {"per_deck", "overall", "unavailable_metrics"}
    assert len(batch["per_deck"]) == len(overnight["per_deck"]) == 2
    assert all(value is None for value in batch["overall"].values())
    assert set(batch["unavailable_metrics"]) == set(complete)
    assert all(
        value is None
        for row in batch["per_deck"]
        for value in row["metrics"].values()
    )
    assert all(set(row["unavailable_metrics"]) == set(complete) for row in batch["per_deck"])
    for artifact in (batch, overnight):
        assert set(artifact["overall"]) == set(complete)
        assert set(artifact["unavailable_metrics"]) <= set(complete)
        for row in artifact["per_deck"]:
            assert set(row) == {
                "deck_id", "deck_name", "deck_key", "metrics", "unavailable_metrics"
            }
            assert set(row["metrics"]) == set(complete)
            assert set(row["unavailable_metrics"]) <= set(complete)


def test_overnight_real_trace_path_includes_shared_authoritative_evidence() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.UPKEEP
    state.active_player = 1
    state.priority_player = 1
    legal = RulesEngine().legal_moves(state, 1)

    payload = overnight_verbose_round_robin._build_overnight_trace_payload(  # type: ignore[attr-defined]
        state,
        1,
        legal,
        {"type": "pass_priority"},
        "No legal action",
        "pass_no_action",
    )

    assert type(payload["bad_blocks"]) is int
    assert isinstance(payload["stall_actionable_options"], bool)


def test_overnight_artifact_measures_all_five_metrics_from_complete_real_traces() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.UPKEEP
    state.active_player = 1
    traces = []
    for pid in (1, 2):
        state.priority_player = pid
        legal = RulesEngine().legal_moves(state, pid)
        payload = overnight_verbose_round_robin._build_overnight_trace_payload(  # type: ignore[attr-defined]
            state,
            pid,
            legal,
            {"type": "pass_priority"},
            "No legal action",
            "pass_no_action",
        )
        traces.append("AI TRACE " + json.dumps(payload))

    decks = [
        {"id": 1, "name": "Deck A", "archetype": "Aggro"},
        {"id": 2, "name": "Deck B", "archetype": "Control"},
    ]
    game = overnight_verbose_round_robin._decision_quality_game_summary(traces, *decks)  # type: ignore[attr-defined]
    artifact = overnight_verbose_round_robin._decision_quality_artifact([game], decks)  # type: ignore[attr-defined]

    assert len(artifact["overall"]) == 5
    assert all(type(value) is int for value in artifact["overall"].values())
    assert artifact["unavailable_metrics"] == {}
    assert all(row["unavailable_metrics"] == {} for row in artifact["per_deck"])


def test_batch_decision_quality_attributes_stall_streaks_across_reversed_seats() -> None:
    def game(deck_a_pid: int) -> tuple[dict[str, object], bool]:
        other_pid = 1 if deck_a_pid == 2 else 2
        traces = [
            "AI TRACE " + json.dumps({
                "pid": deck_a_pid,
                "step": "Step.PRECOMBAT_MAIN",
                "legal_non_pass": True,
                "legal_has_land": False,
                "stall_actionable_options": True,
                "mana_pool": {},
                "action": {"type": "pass_priority"},
            })
            for _ in range(3)
        ]
        traces.append("AI TRACE " + json.dumps({
            "pid": other_pid,
            "step": "Step.UPKEEP",
            "legal_non_pass": False,
            "stall_actionable_options": False,
            "mana_pool": {},
            "action": {"type": "pass_priority"},
        }))
        return {"log": traces}, deck_a_pid == 1

    artifact = AnalyticsService._decision_quality_summary([game(1), game(2)])

    assert artifact["per_deck"][0]["metrics"]["stall_streaks"] == 2
    assert artifact["per_deck"][1]["metrics"]["stall_streaks"] == 0
    assert artifact["overall"]["stall_streaks"] == 2


def test_batch_decision_quality_aggregates_traces_by_deck_across_reversed_seats(monkeypatch) -> None:
    original_choose_action = AIAgent.choose_action

    def choose_action_with_trace(self, state, legal_moves, player_id):
        for pid in (1, 2):
            deck_name = state.players[pid].name
            main_phase_count = 1 if deck_name == "Deck A" else 2
            for _ in range(main_phase_count):
                state.log.append(
                    "AI TRACE "
                    + json.dumps(
                        {
                            "pid": pid,
                            "turn": 1,
                            "step": "Step.PRECOMBAT_MAIN",
                            "legal_non_pass": True,
                            "legal_has_land": True,
                            "mana_pool": {"U": 1},
                            "action": {"type": "pass_priority"},
                        }
                    )
                )
            state.log.append(
                "AI TRACE "
                + json.dumps(
                    {
                        "pid": pid,
                        "turn": 1,
                        "step": "Step.END_STEP",
                        "legal_non_pass": False,
                        "legal_has_land": False,
                        "stall_actionable_options": False,
                        "mana_pool": {},
                        "action": {"type": "pass_priority"},
                    }
                )
            )
            state.log.append(
                "AI TRACE "
                + json.dumps(
                    {
                        "pid": pid,
                        "step": "Step.DECLARE_ATTACKERS",
                        "legal_non_pass": True,
                        "legal_has_land": False,
                        "mana_pool": {},
                        "lethal_attack_available": deck_name == "Deck A",
                        "action": {"type": "pass_priority"},
                    }
                )
            )
            state.log.append(
                "AI TRACE "
                + json.dumps(
                    {
                        "pid": pid,
                        "step": "Step.DECLARE_BLOCKERS",
                        "legal_non_pass": True,
                        "legal_has_land": False,
                        "mana_pool": {},
                        "bad_blocks": 1 if deck_name == "Deck A" else 0,
                        "battlefield": [{"id": "blocker", "power": 1, "toughness": 1}],
                        "opp_battlefield": [{"id": "attacker", "power": 3, "toughness": 3}],
                        "action": {
                            "type": "block",
                            "blocks": {"attacker": "blocker"} if deck_name == "Deck A" else {},
                        },
                    }
                )
            )
        return original_choose_action(self, state, legal_moves, player_id)

    monkeypatch.setattr(AIAgent, "choose_action", choose_action_with_trace)
    repo = _DummyRepo()
    service = AnalyticsService(repo)  # type: ignore[arg-type]
    deck_a = [{"quantity": 60, "card_name": "Island"}]
    deck_b = [{"quantity": 60, "card_name": "Swamp"}]

    out = service.run_batch(deck_a, deck_b, matches=2, difficulty="master", max_ticks=1)

    assert out["decision_quality"]["per_deck"] == [
        {
            "deck_id": None,
            "deck_name": "Deck A",
            "deck_key": "pool:0",
            "metrics": {
                "missed_land_drops": 2,
                "unused_mana_passes": 2,
                "lethal_misses": 2,
                "bad_blocks": 2,
                "stall_streaks": None,
            },
            "unavailable_metrics": {
                "stall_streaks": "complete per-player AI decision trace evidence absent",
            },
        },
        {
            "deck_id": None,
            "deck_name": "Deck B",
            "deck_key": "pool:1",
            "metrics": {
                "missed_land_drops": 2,
                "unused_mana_passes": 4,
                "lethal_misses": 0,
                "bad_blocks": 0,
                "stall_streaks": None,
            },
            "unavailable_metrics": {
                "stall_streaks": "complete per-player AI decision trace evidence absent",
            },
        },
    ]
    assert out["decision_quality"]["overall"] == {
        "missed_land_drops": 4,
        "unused_mana_passes": 6,
        "lethal_misses": 2,
        "bad_blocks": 2,
        "stall_streaks": None,
    }
    assert out["decision_quality"]["unavailable_metrics"] == {
        "stall_streaks": "complete per-player AI decision trace evidence absent",
    }


def test_batch_real_agents_emit_complete_decision_quality_evidence() -> None:
    repo = _DummyRepo()
    service = AnalyticsService(repo)  # type: ignore[arg-type]
    deck_a = [{"quantity": 60, "card_name": "Island", "types": ["Land"]}]
    deck_b = [{"quantity": 60, "card_name": "Swamp", "types": ["Land"]}]

    out = service.run_batch(deck_a, deck_b, matches=1, difficulty="master", max_ticks=8)

    for row in out["decision_quality"]["per_deck"]:
        assert all(value is not None for value in row["metrics"].values())
        assert row["unavailable_metrics"] == {}
    assert out["decision_quality"]["unavailable_metrics"] == {}
    assert any(line.startswith("AI TRACE ") for line in out["sample_log_excerpt"])


def test_batch_is_deterministic_for_same_inputs() -> None:
    repo = _DummyRepo()
    service = AnalyticsService(repo)  # type: ignore[arg-type]
    deck_a = [{"quantity": 60, "card_name": "Island"}]
    deck_b = [{"quantity": 60, "card_name": "Island"}]
    out1 = service.run_batch(deck_a, deck_b, matches=2, difficulty="master", max_ticks=1)
    out2 = service.run_batch(deck_a, deck_b, matches=2, difficulty="master", max_ticks=1)
    assert out1["deterministic_replay_fingerprint"] == out2["deterministic_replay_fingerprint"]
    assert out1["game_results"] == out2["game_results"]
    assert [row["deck_a_on_play"] for row in out1["game_results"]] == [True, False]


def test_batch_exposes_first_divergence_report() -> None:
    repo = _DummyRepo()
    service = AnalyticsService(repo)  # type: ignore[arg-type]
    calls: list[tuple[list[str], list[str]]] = []

    def compare(left_log: list[str], right_log: list[str]) -> dict:
        calls.append((left_log, right_log))
        return {"category": "mock", "index": 9}

    service.compare_replay_logs = compare  # type: ignore[method-assign]
    deck_a = [{"quantity": 60, "card_name": "Island"}]
    deck_b = [{"quantity": 60, "card_name": "Swamp"}]
    out = service.run_batch(deck_a, deck_b, matches=2, difficulty="master", max_ticks=1)
    assert calls
    assert out["first_divergence"] == {"category": "mock", "index": 9}


def test_batch_exposes_first_divergence_excerpt() -> None:
    repo = _DummyRepo()
    service = AnalyticsService(repo)  # type: ignore[arg-type]
    excerpt = service._first_divergence_excerpt(
        ["Turn 1.", "Player A plays Island.", "Player A passes priority."],
        ["Turn 1.", "Player A plays Island.", "Player A casts Lightning Bolt."],
    )

    assert excerpt["index"] == 2
    assert excerpt["category"] == "pass_vs_action"
    assert excerpt["line_a"] == "Player A passes priority."
    assert excerpt["line_b"] == "Player A casts Lightning Bolt."


def test_batch_first_divergence_excerpt_includes_trace_context() -> None:
    repo = _DummyRepo()
    service = AnalyticsService(repo)  # type: ignore[arg-type]
    excerpt = service._first_divergence_excerpt(
        [
            'AI TRACE {"pid":1,"turn":4,"step":"precombat_main","hand":["Counterspell"],"opp_hand":["Threat"],"battlefield":[{"id":"c1","types":["Land"]}],"opp_battlefield":[{"id":"c2","types":["Creature"]}],"life":{"self":16,"opp":12},"legal_non_pass":true,"legal_has_land":false,"action":{"type":"cast_spell","card_name":"Counterspell"}}'
        ],
        [
            'AI TRACE {"pid":1,"turn":4,"step":"precombat_main","hand":["Counterspell"],"opp_hand":["Threat"],"battlefield":[{"id":"c1","types":["Land"]}],"opp_battlefield":[{"id":"c2","types":["Creature"]}],"life":{"self":16,"opp":12},"legal_non_pass":true,"legal_has_land":false,"action":{"type":"pass_priority"}}'
        ],
    )

    assert excerpt["trace_context_a"]["hand_size"] == 1
    assert excerpt["trace_context_a"]["opp_hand_size"] == 1
    assert excerpt["trace_context_b"]["action_type"] == "pass_priority"


def test_batch_reports_confidence_intervals_and_small_sample_balance_alert() -> None:
    interval = AnalyticsService._wilson_interval(10, 10)
    alerts = AnalyticsService._balance_alerts(10, 0, 10)

    assert interval["low"] < 100.0 <= interval["high"]
    assert any(item["kind"] == "extreme_win_rate" and item["severity"] == "high" for item in alerts)
    assert AnalyticsService._balance_alerts(0, 0, 0, 5)[0]["kind"] == "insufficient_sample"
