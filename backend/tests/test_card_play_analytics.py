from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.card_play_analytics import _summarize_card_play_lines, summarize_card_play_logic


def _games_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")


def test_card_play_analytics_separates_meaningful_main_phase_passes(tmp_path: Path) -> None:
    games = tmp_path / "games.jsonl"
    _games_jsonl(
        games,
        [
            {
                "winner": 1,
                "log": [
                    'AI TRACE {"pid":1,"turn":3,"step":"Step.PRECOMBAT_MAIN","hand":["Island","Memory Deluge"],"battlefield":[{"id":"c1"}],"opp_battlefield":[{"id":"c2"}],"mana_pool":{"U":1},"legal_non_pass":true,"legal_has_land":true,"reason_code":"hold_up_interaction","action":{"type":"pass_priority"}}',
                    'AI TRACE {"pid":1,"turn":3,"step":"Step.END_STEP","mana_pool":{},"legal_non_pass":false,"legal_has_land":false,"stall_actionable_options":false,"action":{"type":"pass_priority"}}',
                    'AI TRACE {"pid":2,"turn":3,"step":"Step.DECLARE_BLOCKERS","hand":[],"battlefield":[{"id":"c3"}],"opp_battlefield":[{"id":"c4"}],"mana_pool":{},"legal_non_pass":true,"legal_has_land":false,"reason_code":"pass_response_window","action":{"type":"pass_priority"}}',
                ],
            }
        ],
    )

    out = summarize_card_play_logic(games)

    assert out["games"] == 1
    assert out["pass_with_options"]["1"] == 1
    assert out["pass_with_meaningful_options"]["1"] == 1
    assert out["main_phase_passes"]["1"] == 1
    assert out["missed_land_windows"]["1"] == 1
    assert out["unused_mana_with_options"]["1"] == 1
    assert out["main_phase_land_not_first"].get("1", 0) == 0
    assert out["pass_with_options"].get("2", 0) == 1
    assert out["pass_with_meaningful_options"].get("2", 0) == 0
    assert out["main_phase_passes"].get("2", 0) == 0
    assert out["reason_codes"]["hold_up_interaction"] == 1
    assert out["pass_reason_codes"]["pass_response_window"] == 1


def test_card_play_analytics_reports_combat_quality(tmp_path: Path) -> None:
    games = tmp_path / "games.jsonl"
    _games_jsonl(
        games,
        [
            {
                "winner": 1,
                "log": [
                    'AI TRACE {"pid":1,"turn":5,"step":"Step.DECLARE_ATTACKERS","life":{"self":12,"opp":4},"battlefield":[{"id":"a","types":["Creature"],"power":4,"toughness":4,"tapped":false}],"opp_battlefield":[],"action":{"type":"attack","attackers":["a"]}}',
                    'AI TRACE {"pid":2,"turn":6,"step":"Step.DECLARE_BLOCKERS","life":{"self":8,"opp":10},"battlefield":[{"id":"b","types":["Creature"],"power":3,"toughness":3,"tapped":false}],"opp_battlefield":[{"id":"c","types":["Creature"],"power":2,"toughness":2,"tapped":false}],"action":{"type":"block","blocks":{"c":["b"]}}}',
                    'AI TRACE {"pid":1,"turn":7,"step":"Step.DECLARE_ATTACKERS","life":{"self":12,"opp":2},"battlefield":[{"id":"a","types":["Creature"],"power":4,"toughness":4,"tapped":false}],"opp_battlefield":[],"legal_action_types":["attack"],"action":{"type":"pass_priority"},"legal_non_pass":true}',
                ],
            }
        ],
    )

    out = summarize_card_play_logic(games)

    assert out["combat_quality"]["attack_actions"]["1"] == 1
    assert out["combat_quality"]["lethal_attack_opportunities"]["1"] == 1
    assert out["combat_quality"]["lethal_attack_misses"]["1"] == 1
    assert out["combat_quality"]["block_actions"]["2"] == 1
    assert out["combat_quality"]["profitable_blocks"]["2"] == 1


def test_card_play_analytics_ignores_tapped_blockers(tmp_path: Path) -> None:
    games = tmp_path / "games.jsonl"
    _games_jsonl(
        games,
        [{
            "winner": 1,
            "log": [
                'AI TRACE {"pid":1,"turn":5,"step":"Step.DECLARE_ATTACKERS","life":{"self":20,"opp":20},"battlefield":[{"id":"a","types":["Creature"],"power":1,"toughness":2,"tapped":false}],"opp_battlefield":[{"id":"b","types":["Creature"],"power":2,"toughness":2,"tapped":true}],"action":{"type":"attack","attackers":["a"]}}',
            ],
        }],
    )

    out = summarize_card_play_logic(games)

    assert out["combat_quality"]["attacks_with_blockers"].get("1", 0) == 0
    assert out["combat_quality"]["obvious_bad_attacks"].get("1", 0) == 0


def test_card_play_analytics_empty_stream_marks_all_decision_metrics_unavailable() -> None:
    out = _summarize_card_play_lines(iter(()))

    expected_metrics = {
        "missed_land_drops",
        "unused_mana_passes",
        "lethal_misses",
        "bad_blocks",
        "stall_streaks",
        "redundant_removal_casts",
    }
    assert out["decision_quality"]["metrics"] == {
        metric: None for metric in expected_metrics
    }
    assert set(out["decision_quality"]["unavailable_metrics"]) == expected_metrics
    assert all(
        not available
        for availability in out["decision_quality"]["availability"].values()
        for available in availability.values()
    )


def test_card_play_analytics_consumes_stream_once() -> None:
    class OnePass:
        def __init__(self):
            self.iterations = 0

        def __iter__(self):
            self.iterations += 1
            if self.iterations > 1:
                raise AssertionError("stream was iterated twice")
            for turn in range(2000):
                yield json.dumps({
                    "winner": 1,
                    "log": [
                        f'AI TRACE {{"pid":1,"turn":{turn},"step":"Step.UPKEEP","legal_non_pass":false,"stall_actionable_options":false,"mana_pool":{{}},"action":{{"type":"pass_priority"}}}}',
                        f'AI TRACE {{"pid":2,"turn":{turn},"step":"Step.UPKEEP","legal_non_pass":false,"stall_actionable_options":false,"mana_pool":{{}},"action":{{"type":"pass_priority"}}}}',
                    ],
                })

    lines = OnePass()
    out = _summarize_card_play_lines(lines)

    assert lines.iterations == 1
    assert out["games"] == 2000


@pytest.mark.parametrize(
    "line",
    [
        "{not-json",
        json.dumps({"winner": 1, "log": [7]}),
        json.dumps({"winner": 1, "log": ["AI TRACE []"]}),
        json.dumps({"winner": 1, "log": ["AI TRACE " + json.dumps({"pid": 1, "action": []})]}),
        json.dumps({"winner": 1, "log": ["AI TRACE " + json.dumps({"pid": 1, "step": []})]}),
    ],
)
def test_card_play_analytics_malformed_input_is_unavailable_not_a_crash(line: str) -> None:
    out = _summarize_card_play_lines(iter([line]))

    assert out["decision_quality"]["unavailable_metrics"]


def test_card_play_analytics_legacy_trace_does_not_report_bad_blocks_or_stalls_as_zero() -> None:
    legacy = json.dumps({
        "winner": 1,
        "log": [
            'AI TRACE {"pid":1,"turn":2,"step":"Step.UPKEEP","action":{"type":"pass_priority"}}',
            'AI TRACE {"pid":2,"turn":2,"step":"Step.UPKEEP","action":{"type":"pass_priority"}}',
        ],
    })

    out = _summarize_card_play_lines(iter([legacy]))

    assert out["decision_quality"]["metrics"]["bad_blocks"] is None
    assert out["decision_quality"]["metrics"]["stall_streaks"] is None
    assert "bad_blocks" in out["decision_quality"]["unavailable_metrics"]
    assert "stall_streaks" in out["decision_quality"]["unavailable_metrics"]


@pytest.mark.parametrize(
    "non_finite",
    [
        pytest.param("NaN", id="string-nan"),
        pytest.param("Infinity", id="string-positive-infinity"),
        pytest.param("-Infinity", id="string-negative-infinity"),
        pytest.param(float("nan"), id="float-nan"),
        pytest.param(float("inf"), id="float-positive-infinity"),
        pytest.param(float("-inf"), id="float-negative-infinity"),
    ],
)
@pytest.mark.parametrize("field", ["attacker_power", "opponent_life"])
def test_card_play_analytics_non_finite_attack_power_only_invalidates_lethal_misses(
    field: str,
    non_finite: object,
) -> None:
    attacker_power = non_finite if field == "attacker_power" else 1
    opponent_life = non_finite if field == "opponent_life" else 20
    row = json.dumps({
        "winner": 1,
        "log": [
            "AI TRACE " + json.dumps({
                "pid": 1,
                "step": "Step.DECLARE_ATTACKERS",
                "legal_non_pass": True,
                "legal_has_land": False,
                "stall_actionable_options": False,
                "bad_blocks": 0,
                "redundant_removal_casts": 0,
                "mana_pool": {},
                "lethal_attack_available": False,
                "battlefield": [{
                    "id": "attacker",
                    "types": ["Creature"],
                    "power": attacker_power,
                    "toughness": 1,
                    "tapped": False,
                }],
                "opp_battlefield": [],
                "life": {"opp": opponent_life},
                "legal_action_types": ["attack"],
                "action": {"type": "attack", "attackers": ["attacker"]},
            }),
            "AI TRACE " + json.dumps({
                "pid": 2,
                "step": "Step.UPKEEP",
                "legal_non_pass": False,
                "legal_has_land": False,
                "stall_actionable_options": False,
                "bad_blocks": 0,
                "redundant_removal_casts": 0,
                "mana_pool": {},
                "action": {"type": "pass_priority"},
            }),
        ],
    })

    out = _summarize_card_play_lines(iter([row]))

    assert out["decision_quality"]["availability"]["1"]["lethal_misses"] is False
    assert all(
        available
        for metric, available in out["decision_quality"]["availability"]["1"].items()
        if metric != "lethal_misses"
    )
    assert all(out["decision_quality"]["availability"]["2"].values())


@pytest.mark.parametrize("field", ["attacker_power", "blocker_power"])
@pytest.mark.parametrize(
    "non_finite",
    ["NaN", "Infinity", "-Infinity", float("nan"), float("inf"), float("-inf")],
)
def test_card_play_analytics_non_finite_attack_comparison_only_invalidates_lethal_misses(
    field: str,
    non_finite: object,
) -> None:
    attacker_power = non_finite if field == "attacker_power" else 2
    blocker_power = non_finite if field == "blocker_power" else 3
    row = json.dumps({
        "winner": 1,
        "log": [
            "AI TRACE " + json.dumps({
                "pid": 1,
                "step": "Step.DECLARE_ATTACKERS",
                "legal_non_pass": True,
                "legal_has_land": False,
                "stall_actionable_options": False,
                "bad_blocks": 0,
                "redundant_removal_casts": 0,
                "mana_pool": {},
                "lethal_attack_available": False,
                "battlefield": [{
                    "id": "attacker",
                    "types": ["Creature"],
                    "power": attacker_power,
                    "toughness": 2,
                    "tapped": False,
                }],
                "opp_battlefield": [{
                    "id": "blocker",
                    "types": ["Creature"],
                    "power": blocker_power,
                    "toughness": 3,
                    "tapped": False,
                }],
                "action": {"type": "attack", "attackers": ["attacker"]},
            }),
            "AI TRACE " + json.dumps({
                "pid": 2,
                "step": "Step.UPKEEP",
                "legal_non_pass": False,
                "legal_has_land": False,
                "stall_actionable_options": False,
                "bad_blocks": 0,
                "redundant_removal_casts": 0,
                "mana_pool": {},
                "action": {"type": "pass_priority"},
            }),
        ],
    })

    out = _summarize_card_play_lines(iter([row]))

    assert out["decision_quality"]["availability"]["1"]["lethal_misses"] is False
    assert all(
        available
        for metric, available in out["decision_quality"]["availability"]["1"].items()
        if metric != "lethal_misses"
    )


@pytest.mark.parametrize("field", ["attacker_power", "opponent_life"])
@pytest.mark.parametrize(
    "non_finite",
    ["NaN", "Infinity", "-Infinity", float("nan"), float("inf"), float("-inf")],
)
def test_card_play_analytics_non_finite_legacy_lethal_evidence_does_not_crash(
    field: str,
    non_finite: object,
) -> None:
    attacker_power = non_finite if field == "attacker_power" else 2
    opponent_life = non_finite if field == "opponent_life" else 3
    row = json.dumps({
        "winner": 1,
        "log": [
            "AI TRACE " + json.dumps({
                "pid": 1,
                "step": "Step.DECLARE_ATTACKERS",
                "legal_non_pass": True,
                "legal_has_land": False,
                "stall_actionable_options": False,
                "bad_blocks": 0,
                "redundant_removal_casts": 0,
                "mana_pool": {},
                "battlefield": [{
                    "id": "attacker",
                    "types": ["Creature"],
                    "power": attacker_power,
                    "toughness": 2,
                    "tapped": False,
                }],
                "opp_battlefield": [],
                "life": {"opp": opponent_life},
                "legal_action_types": ["attack"],
                "action": {"type": "pass_priority"},
            }),
            "AI TRACE " + json.dumps({
                "pid": 2,
                "step": "Step.UPKEEP",
                "legal_non_pass": False,
                "legal_has_land": False,
                "stall_actionable_options": False,
                "bad_blocks": 0,
                "redundant_removal_casts": 0,
                "mana_pool": {},
                "action": {"type": "pass_priority"},
            }),
        ],
    })

    out = _summarize_card_play_lines(iter([row]))

    assert out["decision_quality"]["availability"]["1"]["lethal_misses"] is False
    assert all(
        available
        for metric, available in out["decision_quality"]["availability"]["1"].items()
        if metric != "lethal_misses"
    )


@pytest.mark.parametrize(
    "non_finite",
    ["NaN", "Infinity", "-Infinity", float("nan"), float("inf"), float("-inf")],
)
@pytest.mark.parametrize(
    "card_side,field",
    [
        ("attacker", "power"),
        ("attacker", "toughness"),
        ("blocker", "power"),
        ("blocker", "toughness"),
    ],
)
def test_card_play_analytics_non_finite_block_stat_only_invalidates_bad_blocks(
    card_side: str,
    field: str,
    non_finite: object,
) -> None:
    attacker = {"id": "attacker", "types": ["Creature"], "power": 3, "toughness": 3}
    blocker = {"id": "blocker", "types": ["Creature"], "power": 2, "toughness": 2}
    (attacker if card_side == "attacker" else blocker)[field] = non_finite
    row = json.dumps({
        "winner": 1,
        "log": [
            "AI TRACE " + json.dumps({
                "pid": 1,
                "step": "Step.DECLARE_BLOCKERS",
                "legal_non_pass": True,
                "legal_has_land": False,
                "stall_actionable_options": False,
                "bad_blocks": 0,
                "redundant_removal_casts": 0,
                "mana_pool": {},
                "battlefield": [blocker],
                "opp_battlefield": [attacker],
                "action": {"type": "block", "blocks": {"attacker": ["blocker"]}},
            }),
            "AI TRACE " + json.dumps({
                "pid": 2,
                "step": "Step.UPKEEP",
                "legal_non_pass": False,
                "legal_has_land": False,
                "stall_actionable_options": False,
                "bad_blocks": 0,
                "redundant_removal_casts": 0,
                "mana_pool": {},
                "action": {"type": "pass_priority"},
            }),
        ],
    })

    out = _summarize_card_play_lines(iter([row]))

    assert out["decision_quality"]["availability"]["1"]["bad_blocks"] is False
    assert all(
        available
        for metric, available in out["decision_quality"]["availability"]["1"].items()
        if metric != "bad_blocks"
    )
    assert all(out["decision_quality"]["availability"]["2"].values())
