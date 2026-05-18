from __future__ import annotations

from ai.agent import AIAgent
from game_state.state import MatchFactory, Step


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


def test_aggro_ai_avoids_suicide_attack_into_larger_blocker() -> None:
    ai = AIAgent(difficulty="master", archetype="Aggro")
    moves = [
        {"type": "attack", "options": ["atk-1"]},
        {"type": "pass_priority"},
    ]

    class FakeState:
        turn = 4
        step = "declare_attackers"
        active_player = 1
        priority_player = 1
        pregame_pending = False
        winner = None
        stack = []
        players = {
            1: type("P", (), {"life": 20, "hand": [], "battlefield": ["atk-1"], "mana_pool": {}, "lands_played_this_turn": 1})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": ["blk-1"], "mana_pool": {}, "lands_played_this_turn": 1})(),
        }
        cards = {
            "atk-1": type("C", (), {"types": ["Creature"], "name": "1/1", "power": 1, "toughness": 1, "keywords": [], "tapped": False})(),
            "blk-1": type("C", (), {"types": ["Creature"], "name": "3/3", "power": 3, "toughness": 3, "keywords": [], "tapped": False})(),
        }
        attackers = []
        attack_targets = {}
        blocks = {}
        passed_priority = set()
        loyalty_activated_this_turn = set()

    decision = ai.choose_action(FakeState(), moves, 1)
    assert decision.action["type"] == "pass_priority"


def test_late_game_forced_progress_attack_avoids_empty_attack_stall() -> None:
    ai = AIAgent(difficulty="master", archetype="Control")
    moves = [
        {"type": "attack", "options": ["atk-1"]},
        {"type": "pass_priority"},
    ]

    class FakeState:
        turn = 26
        step = "declare_attackers"
        active_player = 1
        priority_player = 1
        pregame_pending = False
        winner = None
        stack = []
        players = {
            1: type("P", (), {"life": 20, "hand": [], "battlefield": ["atk-1"], "mana_pool": {}, "lands_played_this_turn": 1})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": ["blk-1"], "mana_pool": {}, "lands_played_this_turn": 1})(),
        }
        cards = {
            "atk-1": type("C", (), {"types": ["Creature"], "name": "3/3", "power": 3, "toughness": 3, "keywords": [], "tapped": False})(),
            "blk-1": type("C", (), {"types": ["Creature"], "name": "4/4", "power": 4, "toughness": 4, "keywords": [], "tapped": False})(),
        }
        attackers = []
        attack_targets = {}
        blocks = {}
        passed_priority = set()
        loyalty_activated_this_turn = set()

    decision = ai.choose_action(FakeState(), moves, 1)
    assert decision.action["type"] == "attack"
    assert decision.action.get("attackers") == ["atk-1"]


def test_control_ai_targets_most_threatening_stack_spell_with_counter() -> None:
    ai = AIAgent(difficulty="master", archetype="Control")
    moves = [
        {
            "type": "cast_spell",
            "card_name": "Counterspell",
            "card_id": "counter-1",
            "target_hints": {
                "stack_targets": [
                    {"id": "stack-small", "label": "Opt"},
                    {"id": "stack-big", "label": "Teferi, Hero of Dominaria"},
                ]
            },
        },
        {"type": "pass_priority"},
    ]

    class FakeState:
        turn = 6
        step = "precombat_main"
        active_player = 1
        priority_player = 1
        players = {
            1: type("P", (), {"life": 20, "hand": ["counter-1"], "battlefield": [], "mana_pool": {}})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": [], "mana_pool": {}})(),
        }
        cards = {
            "counter-1": type("C", (), {"types": ["Instant"], "name": "Counterspell", "oracle_text": "Counter target spell.", "mana_cost": "{U}{U}"})(),
            "c-small": type("C", (), {"types": ["Instant"], "name": "Opt", "oracle_text": "Scry 1, draw a card.", "mana_cost": "{U}"})(),
            "c-big": type("C", (), {"types": ["Planeswalker"], "name": "Teferi, Hero of Dominaria", "oracle_text": "+1: Draw a card.", "mana_cost": "{3}{W}{U}"})(),
        }
        stack = [
            type("S", (), {"id": "stack-small", "label": "Opt", "source_card_id": "c-small", "controller": 2})(),
            type("S", (), {"id": "stack-big", "label": "Teferi, Hero of Dominaria", "source_card_id": "c-big", "controller": 2})(),
        ]
        winner = None
        pregame_pending = False

    decision = ai.choose_action(FakeState(), moves, 1)
    assert decision.action["type"] == "cast_spell"
    assert decision.action["targets"]["target_stack_id"] == "stack-big"


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


def test_control_ai_mulligans_missing_primary_color_access() -> None:
    ai = AIAgent(difficulty="strong", archetype="Control")

    class Card:
        def __init__(self, types, mana_cost="", name="", type_line="", oracle_text=""):
            self.types = types
            self.mana_cost = mana_cost
            self.name = name
            self.type_line = type_line
            self.oracle_text = oracle_text

    class FakeState:
        pregame_pending = True
        mulligan_count = {1: 0}
        players = {1: type("P", (), {"hand": ["l1", "l2", "s1", "s2", "s3", "s4", "s5"]})()}
        cards = {
            "l1": Card(["Land"], name="Mountain", type_line="Basic Land — Mountain", oracle_text="{T}: Add {R}."),
            "l2": Card(["Land"], name="Mountain", type_line="Basic Land — Mountain", oracle_text="{T}: Add {R}."),
            "s1": Card(["Instant"], "{U}{U}", name="Counterspell"),
            "s2": Card(["Instant"], "{U}", name="Consider"),
            "s3": Card(["Instant"], "{1}{U}", name="Memory Deluge"),
            "s4": Card(["Instant"], "{U}", name="Opt"),
            "s5": Card(["Instant"], "{2}{U}", name="Negate"),
        }

    decision = ai.choose_mulligan_action(FakeState(), 1)
    assert decision.action["type"] == "mulligan"


def test_attack_bias_defensive_role_discourages_attacks() -> None:
    ai = AIAgent(difficulty="master", archetype="Midrange")

    class FakeState:
        players = {
            1: type("P", (), {"life": 6, "battlefield": ["a1"]})(),
            2: type("P", (), {"life": 20, "battlefield": ["b1", "b2"]})(),
        }
        cards = {
            "a1": type("C", (), {"types": ["Creature"], "power": 2, "toughness": 2, "tapped": False})(),
            "b1": type("C", (), {"types": ["Creature"], "power": 4, "toughness": 4, "tapped": False})(),
            "b2": type("C", (), {"types": ["Creature"], "power": 3, "toughness": 3, "tapped": False})(),
        }

    score = ai._attack_bias(FakeState(), {"attackers": ["a1"]}, 1)
    assert score < 5


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


def test_ai_targets_highest_threat_creature_not_just_highest_toughness() -> None:
    ai = AIAgent(difficulty="master", archetype="Control")
    moves = [
        {
            "type": "cast_spell",
            "card_name": "Go for the Throat",
            "card_id": "rmv-1",
            "target_hints": {
                "creature_targets": [{"id": "bear"}, {"id": "dragon"}],
            },
        },
    ]

    class FakeState:
        turn = 5
        step = "precombat_main"
        active_player = 1
        priority_player = 1
        pregame_pending = False
        winner = None
        stack = []
        players = {
            1: type("P", (), {"life": 20, "hand": ["rmv-1"], "battlefield": [], "mana_pool": {}})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": ["bear", "dragon"], "mana_pool": {}})(),
        }
        cards = {
            "rmv-1": type("C", (), {"types": ["Instant"], "name": "Go for the Throat", "oracle_text": "Destroy target creature.", "tapped": False})(),
            "bear": type("C", (), {"types": ["Creature"], "name": "Runeclaw Bear", "power": 2, "toughness": 2, "keywords": [], "oracle_text": "", "tapped": False})(),
            "dragon": type("C", (), {"types": ["Creature"], "name": "Dragon", "power": 5, "toughness": 5, "keywords": ["Flying"], "oracle_text": "", "tapped": False})(),
        }

    decision = ai.choose_action(FakeState(), moves, 1)
    assert decision.action["type"] == "cast_spell"
    assert decision.action["targets"]["target_card_id"] == "dragon"


def test_control_ai_more_proactive_when_opponent_tapped_down() -> None:
    ai = AIAgent(difficulty="master", archetype="Control")
    moves = [
        {"type": "cast_spell", "card_name": "Consider", "card_id": "draw-1"},
        {"type": "pass_priority"},
    ]

    class FakeState:
        turn = 4
        step = "precombat_main"
        active_player = 1
        priority_player = 1
        pregame_pending = False
        winner = None
        stack = []
        players = {
            1: type("P", (), {"life": 20, "hand": ["draw-1"], "battlefield": [], "mana_pool": {}})(),
            2: type(
                "P",
                (),
                {"life": 20, "hand": [], "battlefield": ["l1", "l2"], "mana_pool": {}},
            )(),
        }
        cards = {
            "draw-1": type("C", (), {"types": ["Instant"], "name": "Consider", "oracle_text": "Draw a card.", "mana_cost": "{U}"})(),
            "l1": type("C", (), {"types": ["Land"], "name": "Island", "tapped": True})(),
            "l2": type("C", (), {"types": ["Land"], "name": "Island", "tapped": True})(),
        }

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
        turn = 3
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


def test_ai_avoids_casting_x_spells_when_only_x_zero_is_possible() -> None:
    ai = AIAgent(difficulty="master", archetype="Control")
    moves = [
        {
            "type": "cast_spell",
            "card_id": "xspell-1",
            "card_name": "Secure the Wastes",
            "mana_cost": "{X}{W}",
            "target_hints": {"requires_x_value": True},
        },
        {"type": "pass_priority"},
    ]

    class FakeState:
        turn = 3
        step = "precombat_main"
        active_player = 1
        priority_player = 1
        players = {
            1: type("P", (), {"life": 20, "hand": ["xspell-1"], "battlefield": ["l1"], "mana_pool": {}})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": [], "mana_pool": {}})(),
        }
        cards = {
            "xspell-1": type("C", (), {"types": ["Instant"], "name": "Secure the Wastes", "oracle_text": "Create X 1/1 white Warrior creature tokens.", "mana_cost": "{X}{W}", "keywords": []})(),
            "l1": type("C", (), {"types": ["Land"], "name": "Plains", "tapped": False, "type_line": "Basic Land — Plains", "oracle_text": "{T}: Add {W}."})(),
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
    assert decision.action["type"] == "pass_priority"


def test_ai_avoids_low_value_secure_the_wastes_early() -> None:
    ai = AIAgent(difficulty="master", archetype="Control")
    moves = [
        {
            "type": "cast_spell",
            "card_id": "xspell-1",
            "card_name": "Secure the Wastes",
            "mana_cost": "{X}{W}",
            "target_hints": {"requires_x_value": True},
        },
        {"type": "pass_priority"},
    ]

    class FakeState:
        turn = 4
        step = "precombat_main"
        active_player = 1
        priority_player = 1
        players = {
            1: type("P", (), {"life": 20, "hand": ["xspell-1"], "battlefield": ["l1", "l2", "l3"], "mana_pool": {}})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": [], "mana_pool": {}})(),
        }
        cards = {
            "xspell-1": type("C", (), {"types": ["Instant"], "name": "Secure the Wastes", "oracle_text": "Create X 1/1 white Warrior creature tokens.", "mana_cost": "{X}{W}", "keywords": []})(),
            "l1": type("C", (), {"types": ["Land"], "name": "Plains", "tapped": False, "type_line": "Basic Land — Plains", "oracle_text": "{T}: Add {W}."})(),
            "l2": type("C", (), {"types": ["Land"], "name": "Plains", "tapped": False, "type_line": "Basic Land — Plains", "oracle_text": "{T}: Add {W}."})(),
            "l3": type("C", (), {"types": ["Land"], "name": "Plains", "tapped": False, "type_line": "Basic Land — Plains", "oracle_text": "{T}: Add {W}."})(),
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
    assert decision.action["type"] == "pass_priority"


def test_ai_uses_log_priors_to_delay_historically_late_noncreature_spells() -> None:
    ai = AIAgent(difficulty="master", archetype="Control")
    old = AIAgent._log_priors_cache
    AIAgent._log_priors_cache = {
        "generated_at": None,
        "samples": {"games": 10, "logs": 1000},
        "cards": {
            "secure the wastes": {
                "casts": 30,
                "seen_in_logs": 100,
                "avg_turn": 8.2,
                "early_turn_cast_rate": 0.05,
                "mid_turn_cast_rate": 0.25,
                "late_turn_cast_rate": 0.70,
                "preferred_min_turn": 7,
            }
        },
    }
    moves = [
        {
            "type": "cast_spell",
            "card_id": "xspell-1",
            "card_name": "Secure the Wastes",
            "mana_cost": "{X}{W}",
            "target_hints": {"requires_x_value": True},
        },
        {"type": "pass_priority"},
    ]

    class FakeState:
        turn = 4
        step = "precombat_main"
        active_player = 1
        priority_player = 1
        players = {
            1: type("P", (), {"life": 20, "hand": ["xspell-1"], "battlefield": ["l1", "l2", "l3", "l4"], "mana_pool": {}})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": [], "mana_pool": {}})(),
        }
        cards = {
            "xspell-1": type("C", (), {"types": ["Instant"], "name": "Secure the Wastes", "oracle_text": "Create X 1/1 white Warrior creature tokens.", "mana_cost": "{X}{W}", "keywords": []})(),
            "l1": type("C", (), {"types": ["Land"], "name": "Plains", "tapped": False, "type_line": "Basic Land — Plains", "oracle_text": "{T}: Add {W}."})(),
            "l2": type("C", (), {"types": ["Land"], "name": "Plains", "tapped": False, "type_line": "Basic Land — Plains", "oracle_text": "{T}: Add {W}."})(),
            "l3": type("C", (), {"types": ["Land"], "name": "Plains", "tapped": False, "type_line": "Basic Land — Plains", "oracle_text": "{T}: Add {W}."})(),
            "l4": type("C", (), {"types": ["Land"], "name": "Plains", "tapped": False, "type_line": "Basic Land — Plains", "oracle_text": "{T}: Add {W}."})(),
        }
        stack = []
        winner = None
        pregame_pending = False
        attackers = []
        attack_targets = {}
        blocks = {}
        passed_priority = set()
        loyalty_activated_this_turn = set()

    try:
        decision = ai.choose_action(FakeState(), moves, 1)
        assert decision.action["type"] == "pass_priority"
    finally:
        AIAgent._log_priors_cache = old


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
        step = Step.PRECOMBAT_MAIN
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
        step = Step.PRECOMBAT_MAIN
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


def test_ai_forces_land_drop_even_when_legal_moves_omit_play_land() -> None:
    ai = AIAgent(difficulty="master", archetype="Tribal")
    moves = [
        {"type": "pass_priority"},
        {"type": "cast_spell", "card_name": "Elvish Warmaster", "card_id": "warmaster-1"},
    ]

    class FakeState:
        turn = 3
        step = Step.PRECOMBAT_MAIN
        active_player = 1
        priority_player = 1
        pregame_pending = False
        stack = []
        players = {
            1: type("P", (), {"life": 20, "hand": ["warmaster-1", "forest-1"], "battlefield": [], "mana_pool": {}, "lands_played_this_turn": 0})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": [], "mana_pool": {}, "lands_played_this_turn": 0})(),
        }
        cards = {
            "warmaster-1": type("C", (), {"types": ["Creature"], "name": "Elvish Warmaster", "oracle_text": "", "mana_cost": "{1}{G}"})(),
            "forest-1": type("C", (), {"types": [], "name": "Forest", "type_line": "", "oracle_text": "{T}: Add {G}.", "mana_cost": ""})(),
        }

    decision = ai.choose_action(FakeState(), moves, 1)
    assert decision.action["type"] == "play_land"
    assert decision.action["card_id"] == "forest-1"


def test_ai_forces_legal_land_drop_even_if_land_counter_is_desynced() -> None:
    ai = AIAgent(difficulty="master", archetype="Control")
    moves = [
        {"type": "pass_priority"},
        {"type": "cast_spell", "card_name": "Memory Deluge", "card_id": "deluge-1"},
        {"type": "play_land", "card_id": "island-1"},
    ]

    class FakeState:
        turn = 6
        step = Step.PRECOMBAT_MAIN
        active_player = 1
        priority_player = 1
        pregame_pending = False
        stack = []
        players = {
            1: type(
                "P",
                (),
                {
                    "life": 20,
                    "hand": ["deluge-1", "island-1"],
                    "battlefield": [],
                    "mana_pool": {},
                    # Simulates stale counter drift; legal move still allows land.
                    "lands_played_this_turn": 1,
                    "land_plays_recorded_on_turn": 0,
                    "last_land_play_turn": 0,
                },
            )(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": [], "mana_pool": {}, "lands_played_this_turn": 0})(),
        }
        cards = {
            "deluge-1": type("C", (), {"types": ["Instant"], "name": "Memory Deluge", "oracle_text": "Draw cards.", "mana_cost": "{2}{U}{U}"})(),
            "island-1": type("C", (), {"types": ["Land"], "name": "Island", "type_line": "Basic Land — Island", "oracle_text": "{T}: Add {U}."})(),
        }

    decision = ai.choose_action(FakeState(), moves, 1)
    assert decision.action["type"] == "play_land"
    assert decision.action["card_id"] == "island-1"


def test_control_ai_mulligan_counts_land_with_missing_types_from_oracle() -> None:
    ai = AIAgent(difficulty="master", archetype="Control")

    class FakeState:
        mulligan_count = {1: 0}
        players = {
            1: type("P", (), {"hand": ["l1", "s1", "s2", "s3", "s4", "s5", "s6"]})(),
        }
        cards = {
            "l1": type("C", (), {"types": [], "name": "Island", "type_line": "", "oracle_text": "{T}: Add {U}.", "mana_cost": ""})(),
            "s1": type("C", (), {"types": ["Instant"], "name": "Counterspell", "type_line": "Instant", "oracle_text": "Counter target spell.", "mana_cost": "{U}{U}"})(),
            "s2": type("C", (), {"types": ["Instant"], "name": "Memory Deluge", "type_line": "Instant", "oracle_text": "Draw cards.", "mana_cost": "{2}{U}{U}"})(),
            "s3": type("C", (), {"types": ["Instant"], "name": "March", "type_line": "Instant", "oracle_text": "Exile target.", "mana_cost": "{X}{W}"})(),
            "s4": type("C", (), {"types": ["Sorcery"], "name": "Supreme Verdict", "type_line": "Sorcery", "oracle_text": "Destroy all creatures.", "mana_cost": "{1}{W}{W}{U}"})(),
            "s5": type("C", (), {"types": ["Enchantment"], "name": "Shark Typhoon", "type_line": "Enchantment", "oracle_text": "", "mana_cost": "{5}{U}"})(),
            "s6": type("C", (), {"types": ["Instant"], "name": "Consider", "type_line": "Instant", "oracle_text": "Draw a card.", "mana_cost": "{U}"})(),
        }

    decision = ai.choose_mulligan_action(FakeState(), 1)
    assert decision.action["type"] == "mulligan"


def test_ai_does_not_treat_mana_creature_as_land_in_forced_land_logic() -> None:
    ai = AIAgent(difficulty="master", archetype="Tribal")
    moves = [
        {"type": "pass_priority"},
        {"type": "cast_spell", "card_name": "Llanowar Elves", "card_id": "elves-1"},
    ]

    class FakeState:
        turn = 2
        step = Step.PRECOMBAT_MAIN
        active_player = 1
        priority_player = 1
        pregame_pending = False
        stack = []
        players = {
            1: type("P", (), {"life": 20, "hand": ["elves-1"], "battlefield": [], "mana_pool": {}, "lands_played_this_turn": 0})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": [], "mana_pool": {}, "lands_played_this_turn": 0})(),
        }
        cards = {
            "elves-1": type("C", (), {"types": [], "name": "Llanowar Elves", "type_line": "", "oracle_text": "{T}: Add {G}.", "mana_cost": "{G}"})(),
        }

    decision = ai.choose_action(FakeState(), moves, 1)
    assert decision.action["type"] != "play_land"


def test_tokens_ai_prioritizes_token_enchantment_engine() -> None:
    ai = AIAgent(difficulty="strong", archetype="Tokens")
    moves = [
        {"type": "pass_priority"},
        {"type": "cast_spell", "card_name": "Adeline, Resplendent Cathar", "card_id": "adeline-1"},
        {"type": "cast_spell", "card_name": "Wedding Announcement", "card_id": "wedding-1"},
    ]

    class FakeState:
        turn = 4
        step = "precombat_main"
        active_player = 1
        priority_player = 1
        pregame_pending = False
        stack = []
        players = {
            1: type("P", (), {"life": 20, "hand": ["adeline-1", "wedding-1"], "battlefield": ["tok-a", "tok-b"], "mana_pool": {}, "lands_played_this_turn": 1})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": [], "mana_pool": {}, "lands_played_this_turn": 1})(),
        }
        cards = {
            "adeline-1": type("C", (), {"types": ["Creature"], "name": "Adeline, Resplendent Cathar", "oracle_text": "", "mana_cost": "{1}{W}{W}"})(),
            "wedding-1": type(
                "C",
                (),
                {
                    "types": ["Enchantment"],
                    "name": "Wedding Announcement",
                    "oracle_text": "At the beginning of your end step, create a 1/1 white Human creature token.",
                    "mana_cost": "{2}{W}",
                },
            )(),
            "tok-a": type("C", (), {"types": ["Creature"], "name": "Human Token", "power": 1, "toughness": 1, "tapped": False})(),
            "tok-b": type("C", (), {"types": ["Creature"], "name": "Human Token", "power": 1, "toughness": 1, "tapped": False})(),
        }

    decision = ai.choose_action(FakeState(), moves, 1)
    assert decision.action["type"] == "cast_spell"
    assert decision.action["card_id"] == "wedding-1"


def test_control_ai_breaks_late_game_main_phase_pass_loop_with_proactive_spell() -> None:
    ai = AIAgent(difficulty="master", archetype="Control")
    moves = [
        {"type": "pass_priority"},
        {"type": "cast_spell", "card_name": "Counterspell", "card_id": "counter-1"},
        {"type": "cast_spell", "card_name": "Teferi, Hero of Dominaria", "card_id": "teferi-1"},
    ]

    class FakeState:
        turn = 9
        step = Step.PRECOMBAT_MAIN
        active_player = 1
        priority_player = 1
        pregame_pending = False
        winner = None
        stack = []
        players = {
            1: type("P", (), {"life": 20, "hand": ["counter-1", "teferi-1"], "battlefield": [], "mana_pool": {}, "lands_played_this_turn": 1})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": [], "mana_pool": {}, "lands_played_this_turn": 1})(),
        }
        cards = {
            "counter-1": type("C", (), {"types": ["Instant"], "name": "Counterspell", "oracle_text": "Counter target spell.", "mana_cost": "{U}{U}", "keywords": []})(),
            "teferi-1": type("C", (), {"types": ["Planeswalker"], "name": "Teferi, Hero of Dominaria", "oracle_text": "+1: Draw a card.", "mana_cost": "{3}{W}{U}", "keywords": []})(),
        }
        blocks = {}
        attackers = []
        attack_targets = {}
        passed_priority = set()
        loyalty_activated_this_turn = set()

    decision = ai.choose_action(FakeState(), moves, 1)
    assert decision.action["type"] == "cast_spell"
    assert decision.action["card_id"] == "teferi-1"


def test_control_ai_deploys_major_threat_instead_of_holding_counter_late() -> None:
    ai = AIAgent(difficulty="master", archetype="Control")
    moves = [
        {"type": "pass_priority"},
        {"type": "cast_spell", "card_name": "Counterspell", "card_id": "counter-1"},
        {"type": "cast_spell", "card_name": "Dream Trawler", "card_id": "threat-1"},
    ]

    class FakeState:
        turn = 7
        step = Step.PRECOMBAT_MAIN
        active_player = 1
        priority_player = 1
        pregame_pending = False
        winner = None
        stack = []
        players = {
            1: type("P", (), {"life": 20, "hand": ["counter-1", "threat-1"], "battlefield": ["i1", "i2", "i3", "i4", "i5", "i6"], "mana_pool": {}, "lands_played_this_turn": 1})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": ["o1", "o2", "o3"], "mana_pool": {}, "lands_played_this_turn": 1})(),
        }
        cards = {
            "counter-1": type("C", (), {"types": ["Instant"], "name": "Counterspell", "oracle_text": "Counter target spell.", "mana_cost": "{U}{U}", "keywords": []})(),
            "threat-1": type("C", (), {"types": ["Creature"], "name": "Dream Trawler", "oracle_text": "Flying, lifelink.", "mana_cost": "{2}{W}{W}{U}{U}", "keywords": ["flying", "lifelink"], "power": 3, "toughness": 5})(),
            "i1": type("C", (), {"types": ["Land"], "name": "Island", "type_line": "Basic Land — Island", "oracle_text": "{T}: Add {U}.", "tapped": False})(),
            "i2": type("C", (), {"types": ["Land"], "name": "Island", "type_line": "Basic Land — Island", "oracle_text": "{T}: Add {U}.", "tapped": False})(),
            "i3": type("C", (), {"types": ["Land"], "name": "Plains", "type_line": "Basic Land — Plains", "oracle_text": "{T}: Add {W}.", "tapped": False})(),
            "i4": type("C", (), {"types": ["Land"], "name": "Plains", "type_line": "Basic Land — Plains", "oracle_text": "{T}: Add {W}.", "tapped": False})(),
            "i5": type("C", (), {"types": ["Land"], "name": "Island", "type_line": "Basic Land — Island", "oracle_text": "{T}: Add {U}.", "tapped": False})(),
            "i6": type("C", (), {"types": ["Land"], "name": "Island", "type_line": "Basic Land — Island", "oracle_text": "{T}: Add {U}.", "tapped": False})(),
            "o1": type("C", (), {"types": ["Land"], "name": "Island", "tapped": False})(),
            "o2": type("C", (), {"types": ["Land"], "name": "Island", "tapped": False})(),
            "o3": type("C", (), {"types": ["Land"], "name": "Island", "tapped": False})(),
        }
        blocks = {}
        attackers = []
        attack_targets = {}
        passed_priority = set()
        loyalty_activated_this_turn = set()

    decision = ai.choose_action(FakeState(), moves, 1)
    assert decision.action["type"] == "cast_spell"
    assert decision.action["card_id"] == "threat-1"


def test_ai_materializes_block_assignments() -> None:
    ai = AIAgent(difficulty="strong", archetype="Midrange")
    move = {
        "type": "block",
        "attackers": [
            {"id": "atk-1", "name": "Attacker"},
            {"id": "atk-2", "name": "Small Attacker"},
        ],
        "blockers": [
            {"id": "blk-1", "name": "Big Blocker"},
            {"id": "blk-2", "name": "Small Blocker"},
        ],
    }

    class FakeState:
        players = {
            1: type("P", (), {"life": 12, "hand": [], "battlefield": ["blk-1", "blk-2"], "mana_pool": {}})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": ["atk-1", "atk-2"], "mana_pool": {}})(),
        }
        cards = {
            "atk-1": type("C", (), {"types": ["Creature"], "name": "Attacker", "power": 4, "toughness": 4, "tapped": False})(),
            "atk-2": type("C", (), {"types": ["Creature"], "name": "Small Attacker", "power": 2, "toughness": 2, "tapped": False})(),
            "blk-1": type("C", (), {"types": ["Creature"], "name": "Big Blocker", "power": 4, "toughness": 4, "tapped": False})(),
            "blk-2": type("C", (), {"types": ["Creature"], "name": "Small Blocker", "power": 2, "toughness": 2, "tapped": False})(),
        }
        stack = []

    out = ai._materialize_action(FakeState(), move, 1)
    assert out["type"] == "block"
    assert out.get("blocks")
    assert "atk-1" in out["blocks"]


def test_ai_passes_in_declare_blockers_when_no_assignment_exists() -> None:
    ai = AIAgent(difficulty="strong", archetype="Midrange")
    moves = [
        {"type": "pass_priority"},
        {"type": "block", "attackers": [{"id": "atk-1", "name": "Atk"}], "blockers": []},
    ]

    class FakeState:
        pregame_pending = False
        step = Step.DECLARE_BLOCKERS
        active_player = 2
        priority_player = 1
        players = {
            1: type("P", (), {"life": 12, "hand": [], "battlefield": [], "mana_pool": {}})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": ["atk-1"], "mana_pool": {}})(),
        }
        cards = {
            "atk-1": type("C", (), {"types": ["Creature"], "name": "Attacker", "power": 4, "toughness": 4, "tapped": True})(),
        }
        stack = []
        blocks = {}
        turn = 3
        winner = None

    decision = ai.choose_action(FakeState(), moves, 1)
    assert decision.action["type"] == "pass_priority"


def test_ai_attack_selection_avoids_suicidal_one_one_into_bigger_board() -> None:
    ai = AIAgent(difficulty="strong", archetype="Midrange")
    move = {"type": "attack", "options": ["a_small", "a_big"]}

    class FakeState:
        players = {
            1: type("P", (), {"life": 18, "hand": [], "battlefield": ["a_small", "a_big"], "mana_pool": {}})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": ["b1", "b2"], "mana_pool": {}})(),
        }
        cards = {
            "a_small": type("C", (), {"types": ["Creature"], "name": "1/1", "power": 1, "toughness": 1, "tapped": False})(),
            "a_big": type("C", (), {"types": ["Creature"], "name": "4/4", "power": 4, "toughness": 4, "tapped": False})(),
            "b1": type("C", (), {"types": ["Creature"], "name": "3/3", "power": 3, "toughness": 3, "tapped": False})(),
            "b2": type("C", (), {"types": ["Creature"], "name": "3/3", "power": 3, "toughness": 3, "tapped": False})(),
        }
        stack = []

    out = ai._materialize_action(FakeState(), move, 1)
    assert out["type"] == "attack"
    assert "a_small" not in out.get("attackers", [])


def test_ai_blocks_with_stronger_creature_to_prevent_damage() -> None:
    ai = AIAgent(difficulty="strong", archetype="Midrange")
    move = {
        "type": "block",
        "attackers": [{"id": "atk-2-2", "name": "2/2"}],
        "blockers": [{"id": "blk-3-3", "name": "3/3"}],
    }

    class FakeState:
        priority_player = 1
        players = {
            1: type("P", (), {"life": 12, "hand": [], "battlefield": ["blk-3-3"], "mana_pool": {}})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": ["atk-2-2"], "mana_pool": {}})(),
        }
        cards = {
            "atk-2-2": type("C", (), {"types": ["Creature"], "name": "2/2", "power": 2, "toughness": 2, "tapped": True})(),
            "blk-3-3": type("C", (), {"types": ["Creature"], "name": "3/3", "power": 3, "toughness": 3, "tapped": False})(),
        }
        stack = []

    out = ai._materialize_action(FakeState(), move, 1)
    assert out["type"] == "block"
    assert out.get("blocks") == {"atk-2-2": "blk-3-3"}


def test_ai_prefers_block_over_pass_when_good_block_exists() -> None:
    ai = AIAgent(difficulty="strong", archetype="Midrange")
    moves = [
        {"type": "pass_priority"},
        {
            "type": "block",
            "attackers": [{"id": "atk-2-2", "name": "2/2"}],
            "blockers": [{"id": "blk-3-3", "name": "3/3"}],
        },
    ]

    class FakeState:
        pregame_pending = False
        step = Step.DECLARE_BLOCKERS
        active_player = 2
        priority_player = 1
        turn = 5
        winner = None
        blocks = {}
        players = {
            1: type("P", (), {"life": 12, "hand": [], "battlefield": ["blk-3-3"], "mana_pool": {}})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": ["atk-2-2"], "mana_pool": {}})(),
        }
        cards = {
            "atk-2-2": type("C", (), {"types": ["Creature"], "name": "2/2", "power": 2, "toughness": 2, "tapped": True, "controller": 2})(),
            "blk-3-3": type("C", (), {"types": ["Creature"], "name": "3/3", "power": 3, "toughness": 3, "tapped": False, "controller": 1})(),
        }
        stack = []

    decision = ai.choose_action(FakeState(), moves, 1)
    assert decision.action["type"] == "block"
    assert decision.action.get("blocks") == {"atk-2-2": "blk-3-3"}


def test_ai_assigns_two_blockers_against_menace_attacker() -> None:
    ai = AIAgent(difficulty="strong", archetype="Midrange")
    move = {
        "type": "block",
        "attackers": [{"id": "atk-menace", "name": "Menace"}],
        "blockers": [
            {"id": "blk-a", "name": "2/2"},
            {"id": "blk-b", "name": "3/3"},
        ],
    }

    class FakeState:
        priority_player = 1
        players = {
            1: type("P", (), {"life": 12, "hand": [], "battlefield": ["blk-a", "blk-b"], "mana_pool": {}})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": ["atk-menace"], "mana_pool": {}})(),
        }
        cards = {
            "atk-menace": type(
                "C",
                (),
                {"types": ["Creature"], "name": "Menace", "power": 4, "toughness": 4, "tapped": True, "keywords": ["menace"], "oracle_text": ""},
            )(),
            "blk-a": type("C", (), {"types": ["Creature"], "name": "2/2", "power": 2, "toughness": 2, "tapped": False})(),
            "blk-b": type("C", (), {"types": ["Creature"], "name": "3/3", "power": 3, "toughness": 3, "tapped": False})(),
        }
        stack = []

    out = ai._materialize_action(FakeState(), move, 1)
    assert out["type"] == "block"
    assert isinstance(out.get("blocks", {}).get("atk-menace"), list)
    assert len(out["blocks"]["atk-menace"]) == 2


def test_tribal_ai_prefers_collected_company_style_spell_over_pass() -> None:
    ai = AIAgent(difficulty="strong", archetype="Tribal")
    moves = [
        {"type": "pass_priority"},
        {
            "type": "cast_spell",
            "card_name": "Collected Company",
            "card_id": "cc-1",
            "mana_cost": "{3}{G}",
            "target_hints": {},
        },
    ]

    class FakeState:
        turn = 5
        step = Step.PRECOMBAT_MAIN
        active_player = 1
        priority_player = 1
        pregame_pending = False
        winner = None
        players = {
            1: type("P", (), {"life": 14, "hand": ["cc-1"], "battlefield": [], "mana_pool": {}})(),
            2: type("P", (), {"life": 18, "hand": [], "battlefield": [], "mana_pool": {}})(),
        }
        cards = {
            "cc-1": type(
                "C",
                (),
                {
                    "types": ["Instant"],
                    "name": "Collected Company",
                    "oracle_text": (
                        "Look at the top six cards of your library. "
                        "Put up to two creature cards with mana value 3 or less from among them onto the battlefield. "
                        "Put the rest on the bottom of your library in any order."
                    ),
                    "mana_cost": "{3}{G}",
                    "keywords": [],
                },
            )(),
        }
        stack = []
        blocks = {}
        attackers = []
        attack_targets = {}
        passed_priority = set()
        loyalty_activated_this_turn = set()

    decision = ai.choose_action(FakeState(), moves, 1)
    assert decision.action["type"] == "cast_spell"
    assert decision.action["card_id"] == "cc-1"


def test_control_inevitability_planner_prefers_draw_over_pass() -> None:
    ai = AIAgent(difficulty="master", archetype="Control", opponent_archetype="Control")
    moves = [
        {"type": "pass_priority"},
        {"type": "cast_spell", "card_name": "Memory Deluge", "card_id": "draw-1"},
    ]

    class FakeState:
        turn = 11
        step = Step.PRECOMBAT_MAIN
        active_player = 1
        priority_player = 1
        pregame_pending = False
        winner = None
        players = {
            1: type(
                "P",
                (),
                {
                    "life": 16,
                    "hand": ["draw-1"],
                    "battlefield": [],
                    "mana_pool": {},
                    "library": ["a"] * 30,
                    "graveyard": ["g"] * 5,
                },
            )(),
            2: type(
                "P",
                (),
                {
                    "life": 15,
                    "hand": [],
                    "battlefield": [],
                    "mana_pool": {},
                    "library": ["b"] * 24,
                    "graveyard": ["h"] * 6,
                },
            )(),
        }
        cards = {
            "draw-1": type("C", (), {"types": ["Instant"], "name": "Memory Deluge", "oracle_text": "Draw cards.", "mana_cost": "{2}{U}{U}"})(),
        }
        stack = []
        blocks = {}
        attackers = []
        attack_targets = {}
        passed_priority = set()
        loyalty_activated_this_turn = set()

    decision = ai.choose_action(FakeState(), moves, 1)
    assert decision.action["type"] == "cast_spell"
    assert decision.action["card_id"] == "draw-1"


def test_control_inevitability_planner_avoids_counter_on_empty_stack() -> None:
    ai = AIAgent(difficulty="master", archetype="Control", opponent_archetype="Control")
    moves = [
        {"type": "pass_priority"},
        {"type": "cast_spell", "card_name": "Counterspell", "card_id": "ctr-1"},
        {"type": "cast_spell", "card_name": "Memory Deluge", "card_id": "draw-1"},
    ]

    class FakeState:
        turn = 12
        step = Step.PRECOMBAT_MAIN
        active_player = 1
        priority_player = 1
        pregame_pending = False
        winner = None
        players = {
            1: type(
                "P",
                (),
                {
                    "life": 18,
                    "hand": ["ctr-1", "draw-1"],
                    "battlefield": [],
                    "mana_pool": {},
                    "library": ["a"] * 25,
                    "graveyard": ["g"] * 7,
                },
            )(),
            2: type(
                "P",
                (),
                {
                    "life": 17,
                    "hand": [],
                    "battlefield": [],
                    "mana_pool": {},
                    "library": ["b"] * 21,
                    "graveyard": ["h"] * 8,
                },
            )(),
        }
        cards = {
            "ctr-1": type("C", (), {"types": ["Instant"], "name": "Counterspell", "oracle_text": "Counter target spell.", "mana_cost": "{U}{U}"})(),
            "draw-1": type("C", (), {"types": ["Instant"], "name": "Memory Deluge", "oracle_text": "Draw cards.", "mana_cost": "{2}{U}{U}"})(),
        }
        stack = []
        blocks = {}
        attackers = []
        attack_targets = {}
        passed_priority = set()
        loyalty_activated_this_turn = set()

    decision = ai.choose_action(FakeState(), moves, 1)
    assert decision.action["type"] == "cast_spell"
    assert decision.action["card_id"] == "draw-1"
