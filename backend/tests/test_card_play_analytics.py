from __future__ import annotations

import json
from pathlib import Path

from scripts.card_play_analytics import summarize_card_play_logic


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
