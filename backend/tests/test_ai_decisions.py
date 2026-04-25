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


def test_control_ai_mulligans_land_light_hand() -> None:
    ai = AIAgent(difficulty="strong", archetype="Control")

    class Card:
        def __init__(self, types, mana_cost=""):
            self.types = types
            self.mana_cost = mana_cost

    class FakeState:
        pregame_pending = True
        mulligan_count = {1: 0}
        players = {1: type("P", (), {"hand": ["l1", "s1", "s2", "s3", "s4", "s5", "s6"]})()}
        cards = {
            "l1": Card(["Land"]),
            "s1": Card(["Instant"], "{1}{U}"),
            "s2": Card(["Instant"], "{2}{U}"),
            "s3": Card(["Instant"], "{1}{U}"),
            "s4": Card(["Instant"], "{3}{U}"),
            "s5": Card(["Sorcery"], "{2}{U}"),
            "s6": Card(["Instant"], "{4}{U}"),
        }

    decision = ai.choose_mulligan_action(FakeState(), 1)
    assert decision.action["type"] == "mulligan"


def test_master_ai_casts_big_creature_when_castable() -> None:
    ai = AIAgent(difficulty="master", archetype="Midrange")
    moves = [
        {"type": "pass_priority"},
        {"type": "cast_spell", "card_name": "Sheoldred, the Apocalypse", "card_id": "big-1"},
    ]

    class FakeState:
        turn = 6
        step = "precombat_main"
        active_player = 1
        priority_player = 1
        players = {
            1: type("P", (), {"life": 20, "hand": ["big-1"], "battlefield": [], "mana_pool": {}})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": [], "mana_pool": {}})(),
        }
        cards = {
            "big-1": type(
                "C",
                (),
                {
                    "types": ["Creature"],
                    "name": "Sheoldred, the Apocalypse",
                    "oracle_text": "",
                    "zone": "hand",
                    "mana_cost": "{2}{B}{B}",
                    "keywords": [],
                    "power": 4,
                    "toughness": 5,
                },
            )(),
        }
        stack = []
        winner = None
        pregame_pending = False
        attackers = []
        attack_targets = {}
        blocks = {}
        passed_priority = set()
        loyalty_activated_this_turn = set()

    decision = ai.choose_action(FakeState(), moves, 1)
    assert decision.action["type"] == "cast_spell"


def test_control_ai_casts_big_finisher_on_clear_main_phase() -> None:
    ai = AIAgent(difficulty="master", archetype="Control")
    moves = [
        {"type": "pass_priority"},
        {"type": "cast_spell", "card_name": "Dream Trawler", "card_id": "big-1"},
    ]

    class FakeState:
        turn = 8
        step = "precombat_main"
        active_player = 1
        priority_player = 1
        players = {
            1: type("P", (), {"life": 20, "hand": ["big-1"], "battlefield": [], "mana_pool": {}})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": [], "mana_pool": {}})(),
        }
        cards = {
            "big-1": type(
                "C",
                (),
                {
                    "types": ["Creature"],
                    "name": "Dream Trawler",
                    "oracle_text": "Flying, lifelink.",
                    "zone": "hand",
                    "mana_cost": "{2}{W}{W}{U}{U}",
                    "keywords": ["Flying", "Lifelink"],
                    "power": 3,
                    "toughness": 5,
                },
            )(),
        }
        stack = []
        winner = None
        pregame_pending = False
        attackers = []
        attack_targets = {}
        blocks = {}
        passed_priority = set()
        loyalty_activated_this_turn = set()

    decision = ai.choose_action(FakeState(), moves, 1)
    assert decision.action["type"] == "cast_spell"


def test_ai_materializes_x_value_for_x_spells() -> None:
    ai = AIAgent(difficulty="master", archetype="Control")
    move = {
        "type": "cast_spell",
        "card_id": "march-1",
        "card_name": "March of Otherworldly Light",
        "mana_cost": "{X}{W}",
        "target_hints": {"creature_targets": [{"id": "enemy-1", "name": "Topiary Stomper"}]},
    }

    class FakeState:
        step = "precombat_main"
        active_player = 1
        priority_player = 1
        players = {
            1: type("P", (), {"life": 20, "hand": ["march-1"], "battlefield": ["l1", "l2", "l3"], "mana_pool": {}})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": ["enemy-1"], "mana_pool": {}})(),
        }
        cards = {
            "march-1": type("C", (), {"types": ["Instant"], "name": "March of Otherworldly Light", "oracle_text": "Exile target creature.", "mana_cost": "{X}{W}", "keywords": []})(),
            "l1": type("C", (), {"types": ["Land"], "name": "Plains", "tapped": False, "type_line": "Basic Land — Plains", "oracle_text": ""})(),
            "l2": type("C", (), {"types": ["Land"], "name": "Island", "tapped": False, "type_line": "Basic Land — Island", "oracle_text": ""})(),
            "l3": type("C", (), {"types": ["Land"], "name": "Island", "tapped": False, "type_line": "Basic Land — Island", "oracle_text": ""})(),
            "enemy-1": type("C", (), {"types": ["Creature"], "name": "Topiary Stomper", "power": 4, "toughness": 4})(),
        }
        stack = []

    out = ai._materialize_action(FakeState(), move, 1)
    assert out["targets"]["target_card_id"] == "enemy-1"
    assert out["targets"]["x_value"] >= 1


def test_ai_materialize_sets_default_cost_choice_when_options_present() -> None:
    ai = AIAgent(difficulty="master", archetype="Control")
    move = {
        "type": "cast_spell",
        "card_id": "spell-1",
        "card_name": "Memory Deluge",
        "mana_cost": "{2}{U}{U}",
        "cost_options": [
            {"id": "base", "label": "Base Cost", "mana_cost": "{2}{U}{U}"},
            {"id": "alternate", "label": "Alt", "mana_cost": "{1}{U}"},
        ],
        "target_hints": {},
    }

    class FakeState:
        players = {
            1: type("P", (), {"life": 20, "hand": ["spell-1"], "battlefield": [], "mana_pool": {}})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": [], "mana_pool": {}})(),
        }
        cards = {
            "spell-1": type("C", (), {"types": ["Instant"], "name": "Memory Deluge", "oracle_text": "Draw cards.", "mana_cost": "{2}{U}{U}", "keywords": []})(),
        }
        stack = []

    out = ai._materialize_action(FakeState(), move, 1)
    assert out["cost_choice"]["id"] == "base"


def test_ai_forces_land_drop_on_own_main_phase() -> None:
    ai = AIAgent(difficulty="master", archetype="Control")
    moves = [
        {"type": "pass_priority"},
        {"type": "cast_spell", "card_name": "Counterspell", "card_id": "counter-1"},
        {"type": "play_land", "card_id": "island-1"},
    ]

    class FakeState:
        turn = 2
        step = "precombat_main"
        active_player = 1
        priority_player = 1
        pregame_pending = False
        stack = []
        players = {
            1: type("P", (), {"life": 20, "hand": ["counter-1", "island-1"], "battlefield": [], "mana_pool": {}, "lands_played_this_turn": 0})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": [], "mana_pool": {}, "lands_played_this_turn": 0})(),
        }
        cards = {
            "counter-1": type("C", (), {"types": ["Instant"], "name": "Counterspell", "oracle_text": "Counter target spell.", "mana_cost": "{U}{U}"})(),
            "island-1": type("C", (), {"types": ["Land"], "name": "Island", "type_line": "Basic Land — Island", "oracle_text": "{T}: Add {U}."})(),
        }

    decision = ai.choose_action(FakeState(), moves, 1)
    assert decision.action["type"] == "play_land"


def test_ai_prefers_blue_source_for_counterspell_setup() -> None:
    ai = AIAgent(difficulty="master", archetype="Control")
    moves = [
        {"type": "play_land", "card_id": "swamp-1"},
        {"type": "play_land", "card_id": "island-1"},
        {"type": "pass_priority"},
    ]

    class FakeState:
        turn = 1
        step = "precombat_main"
        active_player = 1
        priority_player = 1
        pregame_pending = False
        stack = []
        players = {
            1: type("P", (), {"life": 20, "hand": ["counter-1", "swamp-1", "island-1"], "battlefield": [], "mana_pool": {}, "lands_played_this_turn": 0})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": [], "mana_pool": {}, "lands_played_this_turn": 0})(),
        }
        cards = {
            "counter-1": type("C", (), {"types": ["Instant"], "name": "Counterspell", "oracle_text": "Counter target spell.", "mana_cost": "{U}{U}"})(),
            "swamp-1": type("C", (), {"types": ["Land"], "name": "Swamp", "type_line": "Basic Land — Swamp", "oracle_text": "{T}: Add {B}."})(),
            "island-1": type("C", (), {"types": ["Land"], "name": "Island", "type_line": "Basic Land — Island", "oracle_text": "{T}: Add {U}."})(),
        }

    decision = ai.choose_action(FakeState(), moves, 1)
    assert decision.action["type"] == "play_land"
    assert decision.action["card_id"] == "island-1"
