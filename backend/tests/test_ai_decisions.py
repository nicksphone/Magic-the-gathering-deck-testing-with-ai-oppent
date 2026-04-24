from __future__ import annotations

from ai.agent import AIAgent
from game_state.state import MatchFactory


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


def test_master_ai_prefers_lethal_line() -> None:
    deck = [{"quantity": 60, "card_name": "Lightning Bolt"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.players[2].life = 3
    ai = AIAgent(difficulty="master", archetype="Burn")
    bolt_id = state.players[1].hand[0]
    moves = [
        {"type": "pass_priority"},
        {"type": "cast_spell", "card_name": "Lightning Bolt", "card_id": bolt_id},
    ]
    decision = ai.choose_action(state, moves, 1)
    assert decision.action["type"] == "cast_spell"


def test_master_plus_ai_prefers_lethal_line() -> None:
    deck = [{"quantity": 60, "card_name": "Lightning Bolt"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.players[2].life = 3
    ai = AIAgent(difficulty="master_plus", archetype="Burn")
    bolt_id = state.players[1].hand[0]
    moves = [
        {"type": "pass_priority"},
        {"type": "cast_spell", "card_name": "Lightning Bolt", "card_id": bolt_id},
    ]
    decision = ai.choose_action(state, moves, 1)
    assert decision.action["type"] == "cast_spell"
