from __future__ import annotations

from ai.log_priors import build_priors_from_examples, build_priors_from_logs


def test_build_priors_extracts_card_timing() -> None:
    logs = [
        [
            'AI TRACE {"trace":true,"pid":1,"turn":2,"step":"Step.PRECOMBAT_MAIN","hand":["Secure the Wastes"],"action":{"type":"pass_priority"}}',
            "Player A casts/activates Secure the Wastes.",
            'AI TRACE {"trace":true,"pid":1,"turn":8,"step":"Step.PRECOMBAT_MAIN","hand":["Secure the Wastes"],"action":{"type":"cast_spell"}}',
            "Player A casts/activates Secure the Wastes.",
            'AI TRACE {"trace":true,"pid":1,"turn":9,"step":"Step.PRECOMBAT_MAIN","hand":["Secure the Wastes"],"action":{"type":"cast_spell"}}',
            "Player A casts/activates Secure the Wastes.",
        ]
    ]
    priors = build_priors_from_logs(logs)
    row = priors["cards"].get("secure the wastes")
    assert row is not None
    assert row["casts"] == 3
    assert row["preferred_min_turn"] >= 2


def test_build_priors_tracks_board_role_timing() -> None:
    logs = [
        [
            'AI TRACE {"trace":true,"pid":1,"turn":4,"step":"precombat_main","hand":["Memory Deluge","Island","Island","Island"],"opp_hand":["Card"],"battlefield":[{"types":["Land"]},{"types":["Land"]},{"types":["Land"]},{"types":["Land"]}],"opp_battlefield":[{"types":["Land"]}],"life":{"self":18,"opp":16},"action":{"type":"cast_spell"}}',
            "Player A casts/activates Memory Deluge.",
            'AI TRACE {"trace":true,"pid":1,"turn":5,"step":"precombat_main","hand":["Memory Deluge","Island","Island","Island"],"opp_hand":["Card"],"battlefield":[{"types":["Land"]},{"types":["Land"]},{"types":["Land"]},{"types":["Land"]},{"types":["Land"]}],"opp_battlefield":[{"types":["Land"]}],"life":{"self":18,"opp":15},"action":{"type":"cast_spell"}}',
            "Player A casts/activates Memory Deluge.",
            'AI TRACE {"trace":true,"pid":1,"turn":8,"step":"precombat_main","hand":["Memory Deluge","Island","Island","Island"],"opp_hand":["Card"],"battlefield":[{"types":["Land"]},{"types":["Land"]},{"types":["Land"]},{"types":["Land"]},{"types":["Land"]}],"opp_battlefield":[{"types":["Land"]}],"life":{"self":18,"opp":12},"action":{"type":"cast_spell"}}',
            "Player A casts/activates Memory Deluge.",
        ]
    ]
    priors = build_priors_from_logs(logs)
    row = priors["cards"].get("memory deluge")
    assert row is not None
    assert "board_roles" in row
    control = row["board_roles"].get("control")
    assert control is not None
    assert control["casts"] == 3
    assert control["preferred_min_turn"] <= row["preferred_min_turn"]


def test_build_priors_from_examples_uses_board_role_hint() -> None:
    examples = [
        {
            "game": 1,
            "turn": 4,
            "board_role_hint": "control",
            "action_type": "cast_spell",
            "action_card_name": "Memory Deluge",
            "hand_size": 4,
        },
        {
            "game": 1,
            "turn": 5,
            "board_role_hint": "control",
            "action_type": "cast_spell",
            "action_card_name": "Memory Deluge",
            "hand_size": 4,
        },
        {
            "game": 2,
            "turn": 8,
            "board_role_hint": "race",
            "action_type": "cast_spell",
            "action_card_name": "Memory Deluge",
            "hand_size": 2,
        },
        {
            "game": 3,
            "turn": 9,
            "board_role_hint": "race",
            "action_type": "cast_spell",
            "action_card_name": "Memory Deluge",
            "hand_size": 2,
        },
    ]
    priors = build_priors_from_examples(examples)
    row = priors["cards"].get("memory deluge")
    assert row is not None
    assert row["casts"] == 4
    assert row["board_roles"]["control"]["casts"] == 2
    assert row["board_roles"]["race"]["casts"] == 2
