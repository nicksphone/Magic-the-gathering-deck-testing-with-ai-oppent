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


def test_ai_avoids_mana_tap_loop_when_no_cast_available() -> None:
    ai = AIAgent(difficulty="master", archetype="Control")
    moves = [
        {"type": "tap_land_for_mana", "card_id": "land-1"},
        {"type": "pass_priority"},
    ]

    class FakeState:
        players = {1: type("P", (), {"life": 20, "hand": [], "battlefield": [], "mana_pool": {}})(), 2: type("P", (), {"life": 20, "hand": [], "battlefield": [], "mana_pool": {}})()}
        cards = {}
        stack = []

    decision = ai.choose_action(FakeState(), moves, 1)
    assert decision.action["type"] == "pass_priority"


def test_aggro_ai_prefers_creature_development_over_burn_early() -> None:
    ai = AIAgent(difficulty="strong", archetype="Aggro")
    moves = [
        {"type": "cast_spell", "card_name": "Monastery Swiftspear", "card_id": "creature-1"},
        {"type": "cast_spell", "card_name": "Lightning Bolt", "card_id": "spell-1"},
        {"type": "pass_priority"},
    ]

    class FakeState:
        turn = 2
        step = type("Step", (), {"PRECOMBAT_MAIN": "precombat_main", "POSTCOMBAT_MAIN": "postcombat_main"})().PRECOMBAT_MAIN
        players = {
            1: type("P", (), {"life": 20, "hand": [], "battlefield": [], "mana_pool": {}})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": [], "mana_pool": {}})(),
        }
        cards = {
            "creature-1": type("C", (), {"types": ["Creature"]})(),
            "spell-1": type("C", (), {"types": ["Instant"]})(),
        }
        stack = []

    decision = ai.choose_action(FakeState(), moves, 1)
    assert decision.action["card_id"] == "creature-1"


def test_control_ai_prefers_card_draw_over_creature_on_empty_stack() -> None:
    ai = AIAgent(difficulty="strong", archetype="Control")
    moves = [
        {"type": "cast_spell", "card_name": "Merfolk Looter", "card_id": "creature-1"},
        {"type": "cast_spell", "card_name": "Consider", "card_id": "draw-1"},
        {"type": "pass_priority"},
    ]

    class FakeState:
        turn = 3
        step = "precombat_main"
        players = {
            1: type("P", (), {"life": 20, "hand": [], "battlefield": [], "mana_pool": {}})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": [], "mana_pool": {}})(),
        }
        cards = {
            "creature-1": type("C", (), {"types": ["Creature"], "name": "Merfolk Looter", "oracle_text": ""})(),
            "draw-1": type("C", (), {"types": ["Instant"], "name": "Consider", "oracle_text": "Draw a card."})(),
        }
        stack = []

    decision = ai.choose_action(FakeState(), moves, 1)
    assert decision.action["card_id"] == "draw-1"


def test_control_ai_sets_counterspell_stack_target() -> None:
    ai = AIAgent(difficulty="strong", archetype="Control")
    moves = [
        {
            "type": "cast_spell",
            "card_name": "Counterspell",
            "card_id": "counter-1",
            "target_hints": {"stack_targets": [{"id": "stack-a", "label": "Lightning Bolt"}]},
        },
        {"type": "pass_priority"},
    ]

    class FakeState:
        turn = 3
        step = "precombat_main"
        players = {
            1: type("P", (), {"life": 20, "hand": [], "battlefield": [], "mana_pool": {}})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": [], "mana_pool": {}})(),
        }
        cards = {
            "counter-1": type("C", (), {"types": ["Instant"], "name": "Counterspell", "oracle_text": "Counter target spell."})(),
        }
        stack = [type("S", (), {"id": "stack-a", "label": "Lightning Bolt"})()]

    decision = ai.choose_action(FakeState(), moves, 1)
    assert decision.action["type"] == "cast_spell"
    assert decision.action["targets"]["target_stack_id"] == "stack-a"
