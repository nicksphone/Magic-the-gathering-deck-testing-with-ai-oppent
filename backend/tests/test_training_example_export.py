from __future__ import annotations

import json
from pathlib import Path

from scripts.extract_training_examples import extract_examples_from_games_jsonl


def test_training_example_export_preserves_trace_labels(tmp_path: Path) -> None:
    games = tmp_path / "games.jsonl"
    games.write_text(
        "\n".join(
            [
                json.dumps(
                        {
                            "game": 1,
                            "winner": 1,
                            "log": [
                                'AI TRACE {"trace":true,"pid":1,"turn":4,"step":"precombat_main","hand":["Modal Adept"],"battlefield":[{"id":"c1","name":"Island","types":["Land"],"tapped":false}],"opp_battlefield":[{"id":"c2","name":"Goblin Guide","types":["Creature"],"tapped":true}],"life":{"self":14,"opp":8},"mana_pool":{"U":1},"legal_non_pass":true,"legal_has_land":false,"action":{"type":"cast_spell","card_id":"modal-1","card_name":"Modal Adept","selected_face_index":1},"reasoning":"Whole-card modal evaluation selected the draw/removal face"}',
                                'AI TRACE {"trace":true,"pid":1,"turn":4,"step":"precombat_main","active_player":1,"priority_player":1,"hand":["Modal Adept"],"battlefield":[{"id":"c1","name":"Island","types":["Land"],"tapped":false}],"opp_battlefield":[{"id":"c2","name":"Goblin Guide","types":["Creature"],"tapped":true}],"life":{"self":14,"opp":8},"mana_pool":{"U":1},"legal_non_pass":true,"legal_has_land":false,"action":{"type":"cast_spell","card_id":"modal-1","card_name":"Modal Adept","selected_face_index":1},"reasoning":"Whole-card modal evaluation selected the draw/removal face"}'
                            ],
                        }
                )
            ]
        ),
        encoding="utf-8",
    )

    examples = extract_examples_from_games_jsonl(games)
    assert len(examples) == 2
    first, second = examples
    assert first["game"] == 1
    assert first["pid"] == 1
    assert first["action_type"] == "cast_spell"
    assert first["selected_face_index"] == 1
    assert first["active_player"] is None
    assert first["priority_player"] is None
    assert first["legal_non_pass"] is True
    assert first["board_snapshot"]["battlefield_count"] == 1
    assert first["board_snapshot"]["opp_battlefield_types"]["Creature"] == 1
    assert first["reasoning"].startswith("Whole-card modal evaluation")
    assert second["active_player"] == 1
    assert second["priority_player"] == 1
