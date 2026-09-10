from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from analytics.service import AnalyticsService
from scripts import baseline_report
from scripts.baseline_report import _deck_archetypes, build_report, render_report


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_baseline_report_contains_required_metrics_and_is_byte_stable(tmp_path: Path) -> None:
    oracle = tmp_path / "oracle.json"
    gate = tmp_path / "gate.json"
    priors = tmp_path / "log_priors.json"
    games = tmp_path / "games.jsonl"
    _write_json(
        oracle,
        {
            "status_unique": {"structured_effect": 1, "missing_oracle": 1},
            "status_weighted": {"structured_effect": 4, "missing_oracle": 2},
            "cards": [
                {"name": "Bolt", "cached": True, "oracle_source": "cache"},
                {"name": "Mystery", "cached": False, "oracle_source": "missing"},
            ],
        },
    )
    _write_json(
        gate,
        {
            "decks": [
                {"id": 1, "name": "Fast Deck", "archetype": "Aggro"},
                {"id": 2, "name": "Slow Deck", "archetype": "Control"},
            ],
            "totals": {
                "timeouts": 0,
                "long_game_timeouts": 1,
                "stall_streaks": 2,
                "invalid_targets": 3,
                "cost_failures": 4,
                "additional_cost_failures": 5,
            },
        },
    )
    _write_json(priors, {"cards": {"Bolt": {}}, "samples": {"games": 7, "logs": 11}})
    rows = [
        {
            "deck_a": "Fast Deck",
            "deck_b": "Slow Deck",
            "winner": 1,
            "log": [
                'AI TRACE {"pid":1,"step":"Step.PRECOMBAT_MAIN","legal_non_pass":true,"legal_has_land":true,"mana_pool":{"R":1},"action":{"type":"pass_priority"}}',
                'AI TRACE {"pid":1,"step":"Step.DECLARE_ATTACKERS","legal_non_pass":false,"mana_pool":{},"lethal_attack_available":true,"action":{"type":"pass_priority"}}',
                'AI TRACE {"pid":2,"step":"Step.UPKEEP","action":{"type":"keep_hand"}}',
            ],
        },
        {
            "deck_a": "Fast Deck",
            "deck_b": "Slow Deck",
            "winner": 2,
            "log": [
                'AI TRACE {"pid":1,"step":"Step.UPKEEP","action":{"type":"keep_hand"}}',
                'AI TRACE {"pid":2,"step":"Step.UPKEEP","action":{"type":"keep_hand"}}',
            ],
        },
    ]
    games.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    report = build_report(
        oracle_path=oracle,
        gate_path=gate,
        log_priors_path=priors,
        games_jsonl_path=games,
    )

    assert set(report) == {
        "win_rates_by_archetype_pair",
        "anomalies",
        "decision_quality_by_archetype",
        "oracle_status_counts",
        "card_cache_completeness",
        "log_priors",
        "unavailable_metrics",
    }
    matchup = report["win_rates_by_archetype_pair"]["Aggro vs Control"]
    assert matchup["win_rate_a"] == 50.0
    assert matchup["wilson_ci_a"] == AnalyticsService._wilson_interval(1, 2)
    assert report["anomalies"] == {
        "timeouts": 0,
        "long_game_timeouts": 1,
        "stall_streaks": 2,
        "invalid_targets": 3,
        "cost_failures": 4,
        "additional_cost_failures": 5,
    }
    assert report["decision_quality_by_archetype"]["Aggro"] == {
        "missed_land_drops": 1,
        "unused_mana_passes": 1,
        "lethal_misses": 1,
    }
    assert report["card_cache_completeness"] == {
        "cached_cards": 1,
        "total_cards": 2,
        "missing_cards": 1,
        "completeness_percent": 50.0,
    }
    assert report["oracle_status_counts"]["unique"]["missing_oracle"] == 1
    assert report["log_priors"] == {"cards": 1, "samples": {"games": 7, "logs": 11}}
    assert report["unavailable_metrics"] == {
        "bad_blocks": "not present in current gate or card-play analytics artifacts"
    }
    assert render_report(report) == render_report(
        build_report(
            oracle_path=oracle,
            gate_path=gate,
            log_priors_path=priors,
            games_jsonl_path=games,
        )
    )


def test_baseline_report_consolidates_reversed_pairs_and_swaps_player_attribution(tmp_path: Path) -> None:
    oracle = tmp_path / "oracle.json"
    gate = tmp_path / "gate.json"
    priors = tmp_path / "log_priors.json"
    games = tmp_path / "games.jsonl"
    _write_json(oracle, {"status_unique": {}, "status_weighted": {}, "cards": []})
    _write_json(
        gate,
        {
            "decks": [
                {"id": 1, "name": "Fast Deck", "archetype": "Aggro"},
                {"id": 2, "name": "Slow Deck", "archetype": "Control"},
            ],
            "totals": {},
        },
    )
    _write_json(priors, {"cards": {}, "samples": {}})
    rows = [
        {
            "deck_a": "Fast Deck",
            "deck_b": "Slow Deck",
            "winner": 1,
            "log": [
                'AI TRACE {"pid":1,"step":"Step.UPKEEP","action":{"type":"keep_hand"}}',
                'AI TRACE {"pid":2,"step":"Step.UPKEEP","action":{"type":"keep_hand"}}',
            ],
        },
        {
            "deck_a": "Slow Deck",
            "deck_b": "Fast Deck",
            "winner": 2,
            "log": [
                'AI TRACE {"pid":1,"step":"Step.PRECOMBAT_MAIN","legal_non_pass":true,"legal_has_land":true,"mana_pool":{},"action":{"type":"pass_priority"}}',
                'AI TRACE {"pid":2,"step":"Step.PRECOMBAT_MAIN","legal_non_pass":true,"legal_has_land":false,"mana_pool":{"R":1},"action":{"type":"pass_priority"}}',
            ],
        },
    ]
    games.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    report = build_report(
        oracle_path=oracle,
        gate_path=gate,
        log_priors_path=priors,
        games_jsonl_path=games,
    )

    assert list(report["win_rates_by_archetype_pair"]) == ["Aggro vs Control"]
    assert report["win_rates_by_archetype_pair"]["Aggro vs Control"]["wins_a"] == 2
    assert report["decision_quality_by_archetype"]["Aggro"]["unused_mana_passes"] == 1
    assert report["decision_quality_by_archetype"]["Control"]["missed_land_drops"] == 1


def test_baseline_report_uses_ids_when_deck_names_are_ambiguous(tmp_path: Path) -> None:
    oracle = tmp_path / "oracle.json"
    gate = tmp_path / "gate.json"
    priors = tmp_path / "log_priors.json"
    games = tmp_path / "games.jsonl"
    _write_json(oracle, {"status_unique": {}, "status_weighted": {}, "cards": []})
    _write_json(
        gate,
        {
            "decks": [
                {"id": 11, "name": "Mirror", "archetype": "Aggro"},
                {"id": 22, "name": "Mirror", "archetype": "Control"},
            ],
            "totals": {},
        },
    )
    _write_json(priors, {"cards": {}, "samples": {}})
    rows = [
        {"deck_a": "Mirror", "deck_a_id": 11, "deck_b": "Mirror", "deck_b_id": 22, "winner": 1, "log": []},
        {"deck_a": "Mirror", "deck_b": "Mirror", "winner": 1, "log": []},
    ]
    games.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    report = build_report(
        oracle_path=oracle,
        gate_path=gate,
        log_priors_path=priors,
        games_jsonl_path=games,
    )

    assert report["win_rates_by_archetype_pair"]["Aggro vs Control"]["games"] == 1
    assert report["unavailable_metrics"]["unmapped_game_archetypes"] == (
        "1 game row(s) lack unambiguous deck-to-archetype metadata"
    )


def test_baseline_game_aggregation_consumes_rows_once() -> None:
    class OnePassRows:
        def __init__(self) -> None:
            self.iterations = 0

        def __iter__(self):
            self.iterations += 1
            if self.iterations > 1:
                raise AssertionError("rows were iterated more than once")
            yield {
                "deck_a": "Fast Deck",
                "deck_b": "Slow Deck",
                "winner": 1,
                "log": [
                    'AI TRACE {"pid":1,"step":"Step.UPKEEP","action":{"type":"keep_hand"}}',
                    'AI TRACE {"pid":2,"step":"Step.UPKEEP","action":{"type":"keep_hand"}}',
                ],
            }

    rows = OnePassRows()
    mapping = _deck_archetypes(
        {
            "decks": [
                {"id": 1, "name": "Fast Deck", "archetype": "Aggro"},
                {"id": 2, "name": "Slow Deck", "archetype": "Control"},
            ]
        }
    )

    aggregated = baseline_report._aggregate_game_rows(rows, mapping)  # type: ignore[attr-defined]

    assert rows.iterations == 1
    assert aggregated["matchups"][("Aggro", "Control")]["games"] == 1
    assert aggregated["matchups"][("Aggro", "Control")]["wins_a"] == 1


def test_baseline_report_rejects_explicit_archetype_conflicting_with_deck_id(tmp_path: Path) -> None:
    report = _minimal_report(
        tmp_path,
        oracle_payload={"status_unique": {}, "status_weighted": {}, "cards": []},
        gate_totals={},
        priors_payload={"cards": {}, "samples": {}},
        game_row={
            "deck_a": "Fast Deck",
            "deck_a_id": 1,
            "deck_a_archetype": "Control",
            "deck_b": "Slow Deck",
            "deck_b_id": 2,
            "deck_b_archetype": "Control",
            "winner": 1,
            "log": [],
        },
    )

    assert report["win_rates_by_archetype_pair"] == {}
    assert report["unavailable_metrics"]["conflicting_game_archetypes"] == (
        "1 game row(s) contain archetype metadata conflicting with stable deck IDs"
    )


def _minimal_report(
    tmp_path: Path,
    *,
    oracle_payload: dict,
    gate_totals: dict,
    priors_payload: dict,
    game_row: dict,
) -> dict:
    oracle = tmp_path / "oracle.json"
    gate = tmp_path / "gate.json"
    priors = tmp_path / "log_priors.json"
    games = tmp_path / "games.jsonl"
    _write_json(oracle, oracle_payload)
    _write_json(
        gate,
        {
            "decks": [
                {"id": 1, "name": "Fast Deck", "archetype": "Aggro"},
                {"id": 2, "name": "Slow Deck", "archetype": "Control"},
            ],
            "totals": gate_totals,
        },
    )
    _write_json(priors, priors_payload)
    games.write_text(json.dumps(game_row) + "\n", encoding="utf-8")
    return build_report(
        oracle_path=oracle,
        gate_path=gate,
        log_priors_path=priors,
        games_jsonl_path=games,
    )


def test_baseline_report_marks_absent_source_metrics_unavailable(tmp_path: Path) -> None:
    report = _minimal_report(
        tmp_path,
        oracle_payload={},
        gate_totals={},
        priors_payload={},
        game_row={"deck_a": "Fast Deck", "deck_b": "Slow Deck", "winner": 1},
    )

    assert report["anomalies"] == {key: None for key in (
        "timeouts",
        "long_game_timeouts",
        "stall_streaks",
        "invalid_targets",
        "cost_failures",
        "additional_cost_failures",
    )}
    assert report["decision_quality_by_archetype"] == {
        "Aggro": {"missed_land_drops": None, "unused_mana_passes": None, "lethal_misses": None},
        "Control": {"missed_land_drops": None, "unused_mana_passes": None, "lethal_misses": None},
    }
    assert report["oracle_status_counts"] == {"unique": None, "weighted": None}
    assert report["card_cache_completeness"] == {
        "cached_cards": None,
        "total_cards": None,
        "missing_cards": None,
        "completeness_percent": None,
    }
    assert report["log_priors"] == {"cards": None, "samples": None}
    assert "anomalies.timeouts" in report["unavailable_metrics"]
    assert "decision_quality_by_archetype.Aggro.missed_land_drops" in report["unavailable_metrics"]
    assert "oracle_status_counts.unique" in report["unavailable_metrics"]
    assert "card_cache_completeness.total_cards" in report["unavailable_metrics"]


def test_baseline_report_preserves_measured_zero_values(tmp_path: Path) -> None:
    report = _minimal_report(
        tmp_path,
        oracle_payload={"status_unique": {}, "status_weighted": {}, "cards": []},
        gate_totals={key: 0 for key in (
            "timeouts",
            "long_game_timeouts",
            "stall_streaks",
            "invalid_targets",
            "cost_failures",
            "additional_cost_failures",
        )},
        priors_payload={"cards": {}, "samples": {}},
        game_row={
            "deck_a": "Fast Deck",
            "deck_b": "Slow Deck",
            "winner": 1,
            "log": [
                'AI TRACE {"pid":1,"step":"Step.PRECOMBAT_MAIN","legal_non_pass":true,"legal_has_land":true,"mana_pool":{},"action":{"type":"play_land"}}',
                'AI TRACE {"pid":1,"step":"Step.UPKEEP","legal_non_pass":false,"mana_pool":{},"action":{"type":"pass_priority"}}',
                'AI TRACE {"pid":1,"step":"Step.DECLARE_ATTACKERS","lethal_attack_available":false,"action":{"type":"attack"}}',
            ],
        },
    )

    assert set(report["anomalies"].values()) == {0}
    assert report["decision_quality_by_archetype"]["Aggro"] == {
        "missed_land_drops": 0,
        "unused_mana_passes": 0,
        "lethal_misses": 0,
    }
    assert report["oracle_status_counts"] == {"unique": {}, "weighted": {}}
    assert report["card_cache_completeness"] == {
        "cached_cards": 0,
        "total_cards": 0,
        "missing_cards": 0,
        "completeness_percent": None,
    }
    assert report["log_priors"] == {"cards": 0, "samples": {}}


@pytest.mark.parametrize(
    ("trace", "metric"),
    [
        (
            'AI TRACE {"pid":1,"step":"Step.PRECOMBAT_MAIN","legal_non_pass":true,"mana_pool":{},"action":{"type":"pass_priority"}}',
            "missed_land_drops",
        ),
        (
            'AI TRACE {"pid":1,"step":"Step.UPKEEP","legal_non_pass":true,"action":{"type":"pass_priority"}}',
            "unused_mana_passes",
        ),
        (
            'AI TRACE {"pid":1,"step":"Step.DECLARE_ATTACKERS","legal_action_types":["attack"],"battlefield":[],"opp_battlefield":[],"action":{"type":"pass_priority"}}',
            "lethal_misses",
        ),
    ],
)
def test_baseline_report_marks_metric_unavailable_for_incomplete_relevant_trace(
    tmp_path: Path,
    trace: str,
    metric: str,
) -> None:
    report = _minimal_report(
        tmp_path,
        oracle_payload={"status_unique": {}, "status_weighted": {}, "cards": []},
        gate_totals={},
        priors_payload={"cards": {}, "samples": {}},
        game_row={"deck_a": "Fast Deck", "deck_b": "Slow Deck", "winner": 1, "log": [trace]},
    )

    assert report["decision_quality_by_archetype"]["Aggro"][metric] is None
    assert f"decision_quality_by_archetype.Aggro.{metric}" in report["unavailable_metrics"]


@pytest.mark.parametrize("field", ["legal_non_pass", "legal_has_land"])
def test_baseline_report_marks_null_land_evidence_unavailable(
    tmp_path: Path,
    field: str,
) -> None:
    evidence: dict[str, object] = {"legal_non_pass": True, "legal_has_land": True}
    evidence[field] = None
    traces = [
        "AI TRACE "
        + json.dumps(
            {
                "pid": 1,
                "step": "Step.PRECOMBAT_MAIN",
                **evidence,
                "action": {"type": "pass_priority"},
            }
        ),
        'AI TRACE {"pid":2,"step":"Step.UPKEEP","action":{"type":"keep_hand"}}',
    ]

    report = _minimal_report(
        tmp_path,
        oracle_payload={"status_unique": {}, "status_weighted": {}, "cards": []},
        gate_totals={},
        priors_payload={"cards": {}, "samples": {}},
        game_row={"deck_a": "Fast Deck", "deck_b": "Slow Deck", "winner": 1, "log": traces},
    )

    assert report["decision_quality_by_archetype"]["Aggro"]["missed_land_drops"] is None
    assert "decision_quality_by_archetype.Aggro.missed_land_drops" in report["unavailable_metrics"]


def test_baseline_report_accepts_explicit_false_land_evidence_as_measured(tmp_path: Path) -> None:
    report = _minimal_report(
        tmp_path,
        oracle_payload={"status_unique": {}, "status_weighted": {}, "cards": []},
        gate_totals={},
        priors_payload={"cards": {}, "samples": {}},
        game_row={
            "deck_a": "Fast Deck",
            "deck_b": "Slow Deck",
            "winner": 1,
            "log": [
                'AI TRACE {"pid":1,"step":"Step.PRECOMBAT_MAIN","legal_non_pass":false,"legal_has_land":false,"action":{"type":"pass_priority"}}',
                'AI TRACE {"pid":2,"step":"Step.UPKEEP","action":{"type":"keep_hand"}}',
            ],
        },
    )

    assert report["decision_quality_by_archetype"]["Aggro"]["missed_land_drops"] == 0
    assert "decision_quality_by_archetype.Aggro.missed_land_drops" not in report["unavailable_metrics"]


def test_baseline_report_marks_null_pass_option_evidence_unavailable(tmp_path: Path) -> None:
    report = _minimal_report(
        tmp_path,
        oracle_payload={"status_unique": {}, "status_weighted": {}, "cards": []},
        gate_totals={},
        priors_payload={"cards": {}, "samples": {}},
        game_row={
            "deck_a": "Fast Deck",
            "deck_b": "Slow Deck",
            "winner": 1,
            "log": [
                'AI TRACE {"pid":1,"step":"Step.UPKEEP","legal_non_pass":null,"mana_pool":{},"action":{"type":"pass_priority"}}',
                'AI TRACE {"pid":2,"step":"Step.UPKEEP","action":{"type":"keep_hand"}}',
            ],
        },
    )

    assert report["decision_quality_by_archetype"]["Aggro"]["unused_mana_passes"] is None
    assert "decision_quality_by_archetype.Aggro.unused_mana_passes" in report["unavailable_metrics"]


def test_baseline_report_marks_null_attacker_power_unavailable(tmp_path: Path) -> None:
    report = _minimal_report(
        tmp_path,
        oracle_payload={"status_unique": {}, "status_weighted": {}, "cards": []},
        gate_totals={},
        priors_payload={"cards": {}, "samples": {}},
        game_row={
            "deck_a": "Fast Deck",
            "deck_b": "Slow Deck",
            "winner": 1,
            "log": [
                'AI TRACE {"pid":1,"step":"Step.DECLARE_ATTACKERS","legal_action_types":["attack"],"battlefield":[{"types":["Creature"],"power":null,"tapped":false}],"opp_battlefield":[],"life":{"opp":3},"action":{"type":"pass_priority"}}',
                'AI TRACE {"pid":2,"step":"Step.UPKEEP","action":{"type":"keep_hand"}}',
            ],
        },
    )

    assert report["decision_quality_by_archetype"]["Aggro"]["lethal_misses"] is None
    assert "decision_quality_by_archetype.Aggro.lethal_misses" in report["unavailable_metrics"]


def test_baseline_report_does_not_infer_lethal_from_raw_attacker_power(tmp_path: Path) -> None:
    report = _minimal_report(
        tmp_path,
        oracle_payload={"status_unique": {}, "status_weighted": {}, "cards": []},
        gate_totals={},
        priors_payload={"cards": {}, "samples": {}},
        game_row={
            "deck_a": "Fast Deck",
            "deck_b": "Slow Deck",
            "winner": 1,
            "log": [
                'AI TRACE {"pid":1,"step":"Step.DECLARE_ATTACKERS","legal_action_types":["attack"],"battlefield":[{"types":["Creature"],"power":0,"tapped":false}],"opp_battlefield":[],"life":{"opp":3},"action":{"type":"pass_priority"}}',
                'AI TRACE {"pid":2,"step":"Step.UPKEEP","action":{"type":"keep_hand"}}',
            ],
        },
    )

    assert report["decision_quality_by_archetype"]["Aggro"]["lethal_misses"] is None
    assert "decision_quality_by_archetype.Aggro.lethal_misses" in report["unavailable_metrics"]


def test_baseline_report_counts_missed_explicit_legal_lethal_opportunity(tmp_path: Path) -> None:
    report = _minimal_report(
        tmp_path,
        oracle_payload={"status_unique": {}, "status_weighted": {}, "cards": []},
        gate_totals={},
        priors_payload={"cards": {}, "samples": {}},
        game_row={
            "deck_a": "Fast Deck",
            "deck_b": "Slow Deck",
            "winner": 1,
            "log": [
                'AI TRACE {"pid":1,"step":"Step.DECLARE_ATTACKERS","lethal_attack_available":true,"action":{"type":"pass_priority"}}',
                'AI TRACE {"pid":2,"step":"Step.UPKEEP","action":{"type":"keep_hand"}}',
            ],
        },
    )

    assert report["decision_quality_by_archetype"]["Aggro"]["lethal_misses"] == 1
    assert "decision_quality_by_archetype.Aggro.lethal_misses" not in report["unavailable_metrics"]


@pytest.mark.parametrize("second_log", [None, []])
def test_baseline_report_requires_complete_evidence_in_every_game_row(
    tmp_path: Path,
    second_log: list[str] | None,
) -> None:
    complete_log = [
        'AI TRACE {"pid":1,"step":"Step.UPKEEP","action":{"type":"keep_hand"}}',
        'AI TRACE {"pid":2,"step":"Step.UPKEEP","action":{"type":"keep_hand"}}',
    ]
    second_row = {"deck_a": "Fast Deck", "deck_b": "Slow Deck", "winner": 2}
    if second_log is not None:
        second_row["log"] = second_log

    oracle = tmp_path / "oracle.json"
    gate = tmp_path / "gate.json"
    priors = tmp_path / "log_priors.json"
    games = tmp_path / "games.jsonl"
    _write_json(oracle, {"status_unique": {}, "status_weighted": {}, "cards": []})
    _write_json(
        gate,
        {
            "decks": [
                {"id": 1, "name": "Fast Deck", "archetype": "Aggro"},
                {"id": 2, "name": "Slow Deck", "archetype": "Control"},
            ],
            "totals": {},
        },
    )
    _write_json(priors, {"cards": {}, "samples": {}})
    rows = [
        {"deck_a": "Fast Deck", "deck_b": "Slow Deck", "winner": 1, "log": complete_log},
        second_row,
    ]
    games.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    report = build_report(
        oracle_path=oracle,
        gate_path=gate,
        log_priors_path=priors,
        games_jsonl_path=games,
    )

    unavailable = report["unavailable_metrics"]
    for archetype in ("Aggro", "Control"):
        assert report["decision_quality_by_archetype"][archetype] == {
            "missed_land_drops": None,
            "unused_mana_passes": None,
            "lethal_misses": None,
        }
        for metric in ("missed_land_drops", "unused_mana_passes", "lethal_misses"):
            assert f"decision_quality_by_archetype.{archetype}.{metric}" in unavailable


def test_baseline_report_marks_null_oracle_status_counts_unavailable(tmp_path: Path) -> None:
    report = _minimal_report(
        tmp_path,
        oracle_payload={"status_unique": None, "status_weighted": None, "cards": []},
        gate_totals={},
        priors_payload={"cards": {}, "samples": {}},
        game_row={"deck_a": "Fast Deck", "deck_b": "Slow Deck", "winner": 1, "log": []},
    )

    assert report["oracle_status_counts"] == {"unique": None, "weighted": None}
    assert "oracle_status_counts.unique" in report["unavailable_metrics"]
    assert "oracle_status_counts.weighted" in report["unavailable_metrics"]


@pytest.mark.parametrize("card", [{"cached": None}, {}])
def test_baseline_report_does_not_count_unknown_cache_status_as_uncached(
    tmp_path: Path,
    card: dict,
) -> None:
    report = _minimal_report(
        tmp_path,
        oracle_payload={"status_unique": {}, "status_weighted": {}, "cards": [card]},
        gate_totals={},
        priors_payload={"cards": {}, "samples": {}},
        game_row={"deck_a": "Fast Deck", "deck_b": "Slow Deck", "winner": 1, "log": []},
    )

    assert report["card_cache_completeness"] == {
        "cached_cards": None,
        "total_cards": 1,
        "missing_cards": None,
        "completeness_percent": None,
    }
    assert "card_cache_completeness.missing_cards" in report["unavailable_metrics"]


def test_baseline_report_counts_false_cache_status_as_measured_uncached(tmp_path: Path) -> None:
    report = _minimal_report(
        tmp_path,
        oracle_payload={"status_unique": {}, "status_weighted": {}, "cards": [{"cached": False}]},
        gate_totals={},
        priors_payload={"cards": {}, "samples": {}},
        game_row={"deck_a": "Fast Deck", "deck_b": "Slow Deck", "winner": 1, "log": []},
    )

    assert report["card_cache_completeness"] == {
        "cached_cards": 0,
        "total_cards": 1,
        "missing_cards": 1,
        "completeness_percent": 0.0,
    }
    assert "card_cache_completeness.missing_cards" not in report["unavailable_metrics"]


def test_baseline_report_marks_win_rate_unavailable_without_resolved_games(tmp_path: Path) -> None:
    report = _minimal_report(
        tmp_path,
        oracle_payload={"status_unique": {}, "status_weighted": {}, "cards": []},
        gate_totals={},
        priors_payload={"cards": {}, "samples": {}},
        game_row={"deck_a": "Fast Deck", "deck_b": "Slow Deck", "winner": None, "log": []},
    )

    matchup = report["win_rates_by_archetype_pair"]["Aggro vs Control"]
    assert matchup["win_rate_a"] is None
    assert matchup["win_rate_b"] is None
    assert matchup["wilson_ci_a"] is None
    assert matchup["wilson_ci_b"] is None
    assert "win_rates_by_archetype_pair.Aggro vs Control.win_rate_a" in report["unavailable_metrics"]


def test_baseline_report_does_not_treat_absent_winner_as_timeout(tmp_path: Path) -> None:
    report = _minimal_report(
        tmp_path,
        oracle_payload={"status_unique": {}, "status_weighted": {}, "cards": []},
        gate_totals={},
        priors_payload={"cards": {}, "samples": {}},
        game_row={"deck_a": "Fast Deck", "deck_b": "Slow Deck", "log": []},
    )

    matchup = report["win_rates_by_archetype_pair"]["Aggro vs Control"]
    assert matchup["resolved_games"] is None
    assert matchup["timeouts"] is None
    assert matchup["wins_a"] is None
    assert matchup["wins_b"] is None
    assert "win_rates_by_archetype_pair.Aggro vs Control.timeouts" in report["unavailable_metrics"]


def test_baseline_report_cli_runs_from_backend_without_network(tmp_path: Path) -> None:
    oracle = tmp_path / "oracle.json"
    gate = tmp_path / "gate.json"
    priors = tmp_path / "log_priors.json"
    games = tmp_path / "games.jsonl"
    _write_json(oracle, {"status_unique": {}, "status_weighted": {}, "cards": []})
    _write_json(
        gate,
        {
            "decks": [
                {"id": 1, "name": "Fast Deck", "archetype": "Aggro"},
                {"id": 2, "name": "Slow Deck", "archetype": "Control"},
            ],
            "totals": {key: 0 for key in (
                "timeouts",
                "long_game_timeouts",
                "stall_streaks",
                "invalid_targets",
                "cost_failures",
                "additional_cost_failures",
            )},
        },
    )
    _write_json(priors, {"cards": {}, "samples": {}})
    games.write_text(
        json.dumps({"deck_a": "Fast Deck", "deck_b": "Slow Deck", "winner": 1, "log": []}) + "\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/baseline_report.py",
            "--oracle",
            str(oracle),
            "--gate",
            str(gate),
            "--games-jsonl",
            str(games),
            "--log-priors",
            str(priors),
        ],
        cwd=Path(__file__).resolve().parent.parent,
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout)["win_rates_by_archetype_pair"]["Aggro vs Control"]["wins_a"] == 1
