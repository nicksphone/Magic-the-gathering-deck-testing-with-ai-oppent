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
    assert first["board_role_hint"] == "normal"
    assert first["board_snapshot"]["battlefield_count"] == 1
    assert first["board_snapshot"]["opp_battlefield_types"]["Creature"] == 1
    assert first["reasoning"].startswith("Whole-card modal evaluation")
    assert second["active_player"] == 1
    assert second["priority_player"] == 1
    assert second["board_role_hint"] == "normal"


def test_training_example_export_marks_convert_role_for_board_lead() -> None:
    games = Path("/tmp/test-gates-games.jsonl")
    games.write_text(
        json.dumps(
            {
                "game": 2,
                "winner": 1,
                "log": [
                    'AI TRACE {"trace":true,"pid":1,"turn":7,"step":"precombat_main","hand":["Finisher"],"battlefield":[{"id":"c1","name":"4/4","types":["Creature"],"tapped":false},{"id":"c2","name":"3/3","types":["Creature"],"tapped":false}],"opp_battlefield":[{"id":"c3","name":"2/2","types":["Creature"],"tapped":false}],"life":{"self":14,"opp":9},"mana_pool":{"G":2},"legal_non_pass":true,"legal_has_land":false,"action":{"type":"cast_spell","card_id":"finisher-1","card_name":"Finisher"},"reasoning":"Convert pressure"}'
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    examples = extract_examples_from_games_jsonl(games)
    assert examples[0]["board_role_hint"] == "convert"


def test_training_example_export_preserves_opponent_hidden_information() -> None:
    games = Path("/tmp/test-hidden-info-games.jsonl")
    games.write_text(
        json.dumps(
            {
                "game": 3,
                "winner": 2,
                "log": [
                    'AI TRACE {"trace":true,"pid":1,"turn":6,"step":"precombat_main","hand":["Counterspell"],"opp_hand":["Threat","Threat"],"battlefield":[{"id":"c1","name":"Island","types":["Land"],"tapped":false}],"opp_battlefield":[{"id":"c2","name":"Goblin Guide","types":["Creature"],"tapped":false}],"graveyard_count":1,"opp_graveyard_count":2,"library_count":28,"opp_library_count":27,"life":{"self":15,"opp":12},"mana_pool":{"U":2},"legal_non_pass":true,"legal_has_land":false,"action":{"type":"pass_priority","card_name":"Counterspell"},"reasoning":"Hold up interaction"}'
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    examples = extract_examples_from_games_jsonl(games)
    assert examples[0]["opp_hand_size"] == 2
    assert examples[0]["board_snapshot"]["opp_hand_count"] == 2
    assert examples[0]["graveyard_count"] == 1
    assert examples[0]["opp_graveyard_count"] == 2
    assert examples[0]["library_count"] == 28
    assert examples[0]["opp_library_count"] == 27


def test_training_example_export_captures_opponent_hand_when_available() -> None:
    games = Path("/tmp/test-hidden-info-games-2.jsonl")
    games.write_text(
        json.dumps(
            {
                "game": 4,
                "winner": 1,
                "log": [
                    'AI TRACE {"trace":true,"pid":2,"turn":3,"step":"declare_attackers","hand":["Burn Spell"],"opp_hand":["Counterspell","Counterspell"],"battlefield":[{"id":"c1","name":"Mountain","types":["Land"],"tapped":false}],"opp_battlefield":[{"id":"c2","name":"Island","types":["Land"],"tapped":false}],"life":{"self":12,"opp":16},"mana_pool":{"R":1},"legal_non_pass":true,"legal_has_land":false,"action":{"type":"cast_spell","card_name":"Burn Spell"},"reasoning":"Force damage through"}'
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    examples = extract_examples_from_games_jsonl(games)
    assert examples[0]["opp_hand_size"] == 2
    assert examples[0]["opp_hand"] == ["Counterspell", "Counterspell"]
