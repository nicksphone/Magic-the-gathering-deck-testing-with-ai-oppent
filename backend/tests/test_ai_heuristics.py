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


def test_ai_combat_uses_granted_keywords_from_static_effects() -> None:
    deck = [{"quantity": 60, "card_name": "Forest"}]
    state = MatchFactory.from_decks(deck, deck, seed=11)
    state.pregame_pending = False
    state.kept_hands = {1, 2}

    attacker_id = state.players[1].hand.pop()
    attacker = state.cards[attacker_id]
    attacker.name = "Small Deathtouch Creature"
    attacker.types = ["Creature"]
    attacker.zone = Zone.BATTLEFIELD
    attacker.type_line = "Creature — Insect"
    attacker.power = 1
    attacker.toughness = 1
    attacker.summoning_sick = False
    state.players[1].battlefield.append(attacker_id)

    grant_id = state.players[1].hand.pop()
    grant = state.cards[grant_id]
    grant.name = "Deathtouch Anthem"
    grant.types = ["Enchantment"]
    grant.zone = Zone.BATTLEFIELD
    grant.oracle_text = "Creatures you control have deathtouch."
    state.players[1].battlefield.append(grant_id)

    blocker_id = state.players[2].hand.pop()
    blocker = state.cards[blocker_id]
    blocker.name = "Large Blocker"
    blocker.types = ["Creature"]
    blocker.zone = Zone.BATTLEFIELD
    blocker.power = 3
    blocker.toughness = 3
    blocker.summoning_sick = False
    state.players[2].battlefield.append(blocker_id)

    chosen = AIAgent(difficulty="master", archetype="Midrange")._choose_attackers(
        state, [attacker_id], 1
    )

    assert attacker_id in chosen


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


def test_evaluate_board_rewards_trigger_engine_permanents() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    baseline = MatchFactory.from_decks(deck, deck)
    engine = MatchFactory.from_decks(deck, deck)

    base_id = baseline.players[1].library.pop()
    baseline.players[1].battlefield.append(base_id)
    baseline.cards[base_id].zone = Zone.BATTLEFIELD
    baseline.cards[base_id].types = ["Enchantment"]
    baseline.cards[base_id].name = "Vanilla Enchantment"
    baseline.cards[base_id].oracle_text = ""

    engine_id = engine.players[1].library.pop()
    engine.players[1].battlefield.append(engine_id)
    engine.cards[engine_id].zone = Zone.BATTLEFIELD
    engine.cards[engine_id].types = ["Enchantment"]
    engine.cards[engine_id].name = "Anointed Procession"
    engine.cards[engine_id].oracle_text = "Whenever a permanent enters the battlefield under your control, draw a card."

    assert evaluate_board(engine, 1) > evaluate_board(baseline, 1)


def test_evaluate_board_rewards_artifact_or_enchantment_engine_permanents() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    baseline = MatchFactory.from_decks(deck, deck)
    engine = MatchFactory.from_decks(deck, deck)

    base_id = baseline.players[1].library.pop()
    baseline.players[1].battlefield.append(base_id)
    baseline.cards[base_id].zone = Zone.BATTLEFIELD
    baseline.cards[base_id].types = ["Artifact"]
    baseline.cards[base_id].name = "Vanilla Artifact"
    baseline.cards[base_id].oracle_text = ""

    engine_id = engine.players[1].library.pop()
    engine.players[1].battlefield.append(engine_id)
    engine.cards[engine_id].zone = Zone.BATTLEFIELD
    engine.cards[engine_id].types = ["Artifact"]
    engine.cards[engine_id].name = "Engine Artifact"
    engine.cards[engine_id].oracle_text = "Whenever an artifact or enchantment enters the battlefield under your control, draw a card."

    assert evaluate_board(engine, 1) > evaluate_board(baseline, 1)


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
