from __future__ import annotations

from ai.agent import AIAgent


def test_ai_prefers_non_pass_action_when_available() -> None:
    ai = AIAgent(difficulty="master", archetype="Burn")
    moves = [
        {"type": "pass_priority"},
        {"type": "cast_spell", "card_name": "Lightning Bolt", "card_id": "x"},
    ]

    class FakeState:
        players = {1: type("P", (), {"life": 20, "hand": [], "battlefield": []})(), 2: type("P", (), {"life": 20, "hand": [], "battlefield": []})()}
        cards = {}

    decision = ai.choose_action(FakeState(), moves, 1)
    assert decision.action["type"] == "cast_spell"
