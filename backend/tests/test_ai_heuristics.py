from __future__ import annotations

from ai.agent import AIAgent
from ai.heuristics import evaluate_board
from game_state.state import MatchFactory, Zone


def test_evaluate_board_rewards_evasive_keyword_creatures() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    baseline = MatchFactory.from_decks(deck, deck)
    upgraded = MatchFactory.from_decks(deck, deck)

    base_id = baseline.players[1].library.pop()
    baseline.players[1].battlefield.append(base_id)
    baseline.cards[base_id].zone = Zone.BATTLEFIELD
    baseline.cards[base_id].types = ["Creature"]
    baseline.cards[base_id].power = 2
    baseline.cards[base_id].toughness = 2
    baseline.cards[base_id].keywords = []

    upgrade_id = upgraded.players[1].library.pop()
    upgraded.players[1].battlefield.append(upgrade_id)
    upgraded.cards[upgrade_id].zone = Zone.BATTLEFIELD
    upgraded.cards[upgrade_id].types = ["Creature"]
    upgraded.cards[upgrade_id].power = 2
    upgraded.cards[upgrade_id].toughness = 2
    upgraded.cards[upgrade_id].keywords = ["Flying", "Lifelink"]

    assert evaluate_board(upgraded, 1) > evaluate_board(baseline, 1)


def test_evaluate_board_penalizes_opponent_planeswalker_pressure() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    baseline = MatchFactory.from_decks(deck, deck)
    pressured = MatchFactory.from_decks(deck, deck)

    walker_id = pressured.players[2].library.pop()
    pressured.players[2].battlefield.append(walker_id)
    pressured.cards[walker_id].zone = Zone.BATTLEFIELD
    pressured.cards[walker_id].types = ["Planeswalker"]
    pressured.cards[walker_id].name = "Teferi, Hero of Dominaria"
    pressured.cards[walker_id].loyalty = 5

    assert evaluate_board(pressured, 1) < evaluate_board(baseline, 1)


def test_evaluate_board_reads_active_face_for_modal_permanents() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    face_a = MatchFactory.from_decks(deck, deck)
    face_b = MatchFactory.from_decks(deck, deck)

    card_a = face_a.players[1].library.pop()
    face_a.players[1].battlefield.append(card_a)
    face_a.cards[card_a].zone = Zone.BATTLEFIELD
    face_a.cards[card_a].name = "MDFC Shell"
    face_a.cards[card_a].types = ["Enchantment"]
    face_a.cards[card_a].selected_face_index = 0
    face_a.cards[card_a].card_faces = [
        {"name": "Front", "type_line": "Sorcery", "oracle_text": "Draw a card."},
        {"name": "Back", "type_line": "Enchantment", "oracle_text": "Creatures you control get +1/+1."},
    ]

    card_b = face_b.players[1].library.pop()
    face_b.players[1].battlefield.append(card_b)
    face_b.cards[card_b].zone = Zone.BATTLEFIELD
    face_b.cards[card_b].name = "MDFC Shell"
    face_b.cards[card_b].types = ["Enchantment"]
    face_b.cards[card_b].selected_face_index = 1
    face_b.cards[card_b].card_faces = [
        {"name": "Front", "type_line": "Sorcery", "oracle_text": "Draw a card."},
        {"name": "Back", "type_line": "Enchantment", "oracle_text": "Creatures you control get +1/+1."},
    ]

    assert evaluate_board(face_b, 1) > evaluate_board(face_a, 1)


def test_control_ai_prefers_removal_against_evasive_threat() -> None:
    ai = AIAgent(difficulty="master", archetype="Control")
    moves = [
        {
            "type": "cast_spell",
            "card_name": "Go for the Throat",
            "card_id": "removal-1",
            "target_hints": {"creature_targets": [{"id": "threat-1", "name": "Troll"}]},
        },
        {"type": "cast_spell", "card_name": "Consider", "card_id": "draw-1"},
        {"type": "pass_priority"},
    ]

    class FakeState:
        turn = 7
        step = "precombat_main"
        active_player = 1
        priority_player = 1
        pregame_pending = False
        stack = []
        winner = None
        players = {
            1: type("P", (), {"life": 8, "hand": ["removal-1", "draw-1"], "battlefield": ["land-1"], "mana_pool": {}})(),
            2: type("P", (), {"life": 12, "hand": [], "battlefield": ["threat-1"], "mana_pool": {}})(),
        }
        cards = {
            "removal-1": type("C", (), {"types": ["Instant"], "name": "Go for the Throat", "oracle_text": "Destroy target creature.", "mana_cost": "{1}{B}", "keywords": []})(),
            "draw-1": type("C", (), {"types": ["Instant"], "name": "Consider", "oracle_text": "Draw a card.", "mana_cost": "{U}", "keywords": []})(),
            "land-1": type("C", (), {"types": ["Land"], "name": "Island", "type_line": "Basic Land — Island", "oracle_text": "{T}: Add {U}.", "tapped": False})(),
            "threat-1": type(
                "C",
                (),
                {
                    "types": ["Creature"],
                    "name": "Serra Angel",
                    "oracle_text": "",
                    "power": 4,
                    "toughness": 4,
                    "keywords": ["Flying", "Lifelink"],
                    "tapped": False,
                },
            )(),
        }

    decision = ai.choose_action(FakeState(), moves, 1)
    assert decision.action["type"] == "cast_spell"
    assert decision.action["card_id"] == "removal-1"
