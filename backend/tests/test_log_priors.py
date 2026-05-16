from __future__ import annotations

from ai.log_priors import build_priors_from_logs


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

