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
                    'AI TRACE {"pid":1,"turn":3,"step":"Step.PRECOMBAT_MAIN","hand":["Island","Memory Deluge"],"battlefield":[{"id":"c1"}],"opp_battlefield":[{"id":"c2"}],"mana_pool":{"U":1},"legal_non_pass":true,"legal_has_land":true,"action":{"type":"pass_priority"}}',
                    'AI TRACE {"pid":2,"turn":3,"step":"Step.DECLARE_BLOCKERS","hand":[],"battlefield":[{"id":"c3"}],"opp_battlefield":[{"id":"c4"}],"mana_pool":{},"legal_non_pass":true,"legal_has_land":false,"action":{"type":"pass_priority"}}',
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
    assert out["pass_with_options"].get("2", 0) == 1
    assert out["pass_with_meaningful_options"].get("2", 0) == 0
    assert out["main_phase_passes"].get("2", 0) == 0
