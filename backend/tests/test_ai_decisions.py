from __future__ import annotations

from ai.agent import AIAgent
from ai.matchup_profiles import profile_for
from game_state.state import CardInstance, MatchFactory, Step, Zone


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


def test_ai_ignores_attack_restricted_placeholder_actions() -> None:
    ai = AIAgent(difficulty="master", archetype="Tokens")
    moves = [
        {"type": "attack_restricted", "card_id": "token-1", "card_name": "White Human", "reason": "Tapped"},
        {"type": "pass_priority"},
    ]

    class FakeState:
        turn = 5
        step = type("Step", (), {"DECLARE_ATTACKERS": "declare_attackers"})().DECLARE_ATTACKERS
        active_player = 1
        players = {
            1: type("P", (), {"life": 20, "hand": [], "battlefield": [], "mana_pool": {}})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": [], "mana_pool": {}})(),
        }
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


def test_control_ai_prefers_value_draw_over_idle_hold_up_when_stable() -> None:
    ai = AIAgent(difficulty="master", archetype="Control")
    moves = [
        {"type": "pass_priority"},
        {"type": "cast_spell", "card_name": "Counterspell", "card_id": "counter-1"},
        {"type": "cast_spell", "card_name": "Memory Deluge", "card_id": "draw-1"},
    ]

    class FakeState:
        turn = 6
        step = Step.PRECOMBAT_MAIN
        active_player = 1
        priority_player = 1
        pregame_pending = False
        winner = None
        stack = []
        players = {
            1: type("P", (), {"life": 20, "hand": ["counter-1", "draw-1"], "battlefield": ["i1", "i2", "i3", "i4"], "mana_pool": {}, "lands_played_this_turn": 1})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": [], "mana_pool": {}, "lands_played_this_turn": 1})(),
        }
        cards = {
            "counter-1": type("C", (), {"types": ["Instant"], "name": "Counterspell", "oracle_text": "Counter target spell.", "mana_cost": "{U}{U}", "keywords": []})(),
            "draw-1": type("C", (), {"types": ["Instant"], "name": "Memory Deluge", "oracle_text": "Draw cards.", "mana_cost": "{2}{U}{U}", "keywords": []})(),
            "i1": type("C", (), {"types": ["Land"], "name": "Island", "type_line": "Basic Land — Island", "oracle_text": "{T}: Add {U}.", "tapped": False})(),
            "i2": type("C", (), {"types": ["Land"], "name": "Island", "type_line": "Basic Land — Island", "oracle_text": "{T}: Add {U}.", "tapped": False})(),
            "i3": type("C", (), {"types": ["Land"], "name": "Island", "type_line": "Basic Land — Island", "oracle_text": "{T}: Add {U}.", "tapped": False})(),
            "i4": type("C", (), {"types": ["Land"], "name": "Island", "type_line": "Basic Land — Island", "oracle_text": "{T}: Add {U}.", "tapped": False})(),
        }

    decision = ai.choose_action(FakeState(), moves, 1)
    assert decision.action["type"] == "cast_spell"
    assert decision.action["card_id"] == "draw-1"


def test_matchup_profile_pushes_control_to_hold_up_against_aggro() -> None:
    profile = profile_for("Control", "Aggro")
    assert profile["holdup_bias"] > 1.0
    assert profile["risk_tolerance"] < 0.0


def test_matchup_profile_pushes_tempo_to_be_more_proactive_against_control() -> None:
    profile = profile_for("Tempo", "Control")
    assert profile["proactive_bias"] > 0.4
    assert profile["risk_tolerance"] > 0.0


def test_matchup_profile_boosts_counterspell_score_against_aggro() -> None:
    control_vs_aggro = AIAgent(difficulty="master", archetype="Control", opponent_archetype="Aggro")
    control_vs_control = AIAgent(difficulty="master", archetype="Control", opponent_archetype="Control")

    class FakeState:
        active_player = 1
        step = "precombat_main"
        stack = [type("S", (), {"id": "stack-a", "label": "Threat"})()]
        players = {
            1: type("P", (), {"life": 16, "hand": ["counter-1"], "battlefield": ["i1", "i2", "i3"], "mana_pool": {}})(),
            2: type("P", (), {"life": 16, "hand": [], "battlefield": ["b1"], "mana_pool": {}})(),
        }
        cards = {
            "counter-1": type("C", (), {"types": ["Instant"], "name": "Counterspell", "oracle_text": "Counter target spell.", "mana_cost": "{U}{U}", "keywords": []})(),
            "i1": type("C", (), {"types": ["Land"], "name": "Island", "type_line": "Basic Land — Island", "oracle_text": "{T}: Add {U}.", "tapped": False})(),
            "i2": type("C", (), {"types": ["Land"], "name": "Island", "type_line": "Basic Land — Island", "oracle_text": "{T}: Add {U}.", "tapped": False})(),
            "i3": type("C", (), {"types": ["Land"], "name": "Island", "type_line": "Basic Land — Island", "oracle_text": "{T}: Add {U}.", "tapped": False})(),
            "b1": type("C", (), {"types": ["Creature"], "name": "2/2", "power": 2, "toughness": 2, "tapped": False})(),
        }

    move = {"type": "cast_spell", "card_id": "counter-1", "card_name": "Counterspell"}
    score_vs_aggro = control_vs_aggro._matchup_move_adjustment(FakeState(), move, 1)
    score_vs_control = control_vs_control._matchup_move_adjustment(FakeState(), move, 1)
    assert score_vs_aggro > score_vs_control


def test_matchup_profile_changes_attack_bias_for_tempo_pressure() -> None:
    tempo_vs_control = AIAgent(difficulty="master", archetype="Tempo", opponent_archetype="Control")
    tempo_vs_ramp = AIAgent(difficulty="master", archetype="Tempo", opponent_archetype="Ramp")

    class FakeState:
        players = {
            1: type("P", (), {"life": 16, "battlefield": ["a1"]})(),
            2: type("P", (), {"life": 16, "battlefield": ["b1", "b2"]})(),
        }
        cards = {
            "a1": type("C", (), {"types": ["Creature"], "power": 2, "toughness": 2, "tapped": False})(),
            "b1": type("C", (), {"types": ["Creature"], "power": 3, "toughness": 3, "tapped": False})(),
            "b2": type("C", (), {"types": ["Creature"], "power": 3, "toughness": 3, "tapped": False})(),
        }

    score_vs_control = tempo_vs_control._attack_bias(FakeState(), {"attackers": ["a1"]}, 1)
    score_vs_ramp = tempo_vs_ramp._attack_bias(FakeState(), {"attackers": ["a1"]}, 1)
    assert score_vs_control > score_vs_ramp


def test_ramp_ai_prefers_ramp_spell_over_card_draw_on_early_turn() -> None:
    ai = AIAgent(difficulty="master", archetype="Ramp")
    moves = [
        {"type": "cast_spell", "card_name": "Cultivate", "card_id": "ramp-1"},
        {"type": "cast_spell", "card_name": "Consider", "card_id": "draw-1"},
        {"type": "pass_priority"},
    ]

    deck = [
        {"quantity": 52, "card_name": "Forest"},
        {"quantity": 4, "card_name": "Cultivate"},
        {"quantity": 4, "card_name": "Consider"},
    ]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.turn = 3
    state.step = "precombat_main"
    state.active_player = 1
    state.priority_player = 1
    state.winner = None
    state.stack = []
    state.players[1].mana_pool = {}
    state.players[2].mana_pool = {}
    ramp_id = next(cid for cid in state.players[1].library if state.cards[cid].name == "Cultivate")
    draw_id = next(cid for cid in state.players[1].library if state.cards[cid].name == "Consider")
    state.players[1].library.remove(ramp_id)
    state.players[1].library.remove(draw_id)
    state.players[1].hand = [ramp_id, draw_id]
    state.cards[ramp_id].zone = Zone.HAND
    state.cards[draw_id].zone = Zone.HAND
    land_ids = [cid for cid in list(state.players[1].library) if "Land" in state.cards[cid].types][:3]
    for cid in land_ids:
        state.players[1].library.remove(cid)
        state.players[1].battlefield.append(cid)
        state.cards[cid].zone = Zone.BATTLEFIELD
        state.cards[cid].tapped = False

    decision = ai.choose_action(state, moves, 1)
    assert decision.action["type"] == "cast_spell"
    assert decision.action["card_id"] == "ramp-1"


def test_control_ai_prefers_sweeper_over_draw_when_stabilizing() -> None:
    ai = AIAgent(difficulty="master", archetype="Control", opponent_archetype="Aggro")
    moves = [
        {"type": "cast_spell", "card_name": "Supreme Verdict", "card_id": "sweeper-1"},
        {"type": "cast_spell", "card_name": "Memory Deluge", "card_id": "draw-1"},
        {"type": "pass_priority"},
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
            1: type("P", (), {"life": 7, "hand": ["sweeper-1", "draw-1"], "battlefield": ["land-1", "land-2", "land-3", "land-4"], "mana_pool": {}})(),
            2: type("P", (), {"life": 18, "hand": [], "battlefield": ["atk-1", "atk-2", "atk-3"], "mana_pool": {}})(),
        }
        cards = {
            "sweeper-1": type("C", (), {"types": ["Sorcery"], "name": "Supreme Verdict", "oracle_text": "Destroy all creatures.", "mana_cost": "{1}{W}{W}{U}", "keywords": []})(),
            "draw-1": type("C", (), {"types": ["Instant"], "name": "Memory Deluge", "oracle_text": "Draw two cards.", "mana_cost": "{2}{U}{U}", "keywords": []})(),
            "land-1": type("C", (), {"types": ["Land"], "name": "Island", "type_line": "Basic Land — Island", "oracle_text": "{T}: Add {U}.", "tapped": False})(),
            "land-2": type("C", (), {"types": ["Land"], "name": "Island", "type_line": "Basic Land — Island", "oracle_text": "{T}: Add {U}.", "tapped": False})(),
            "land-3": type("C", (), {"types": ["Land"], "name": "Plains", "type_line": "Basic Land — Plains", "oracle_text": "{T}: Add {W}.", "tapped": False})(),
            "land-4": type("C", (), {"types": ["Land"], "name": "Plains", "type_line": "Basic Land — Plains", "oracle_text": "{T}: Add {W}.", "tapped": False})(),
            "atk-1": type("C", (), {"types": ["Creature"], "name": "2/2", "power": 2, "toughness": 2, "tapped": False})(),
            "atk-2": type("C", (), {"types": ["Creature"], "name": "2/2", "power": 2, "toughness": 2, "tapped": False})(),
            "atk-3": type("C", (), {"types": ["Creature"], "name": "3/3", "power": 3, "toughness": 3, "tapped": False})(),
        }

    decision = ai.choose_action(FakeState(), moves, 1)
    assert decision.action["type"] == "cast_spell"
    assert decision.action["card_id"] == "sweeper-1"


def test_matchup_profile_pushes_combo_lite_to_proactive_conversion_against_control() -> None:
    profile = profile_for("Combo-lite", "Control")
    assert profile["proactive_bias"] > 0.8
    assert profile["risk_tolerance"] > 0.2
    assert profile["holdup_bias"] >= 0.0


def test_board_role_distinguishes_stabilize_and_convert() -> None:
    ai = AIAgent(difficulty="master", archetype="Control")

    class StabilizeState:
        players = {
            1: type("P", (), {"life": 6, "hand": [], "battlefield": ["a1"], "mana_pool": {}})(),
            2: type("P", (), {"life": 18, "hand": [], "battlefield": ["b1", "b2"], "mana_pool": {}})(),
        }
        cards = {
            "a1": type("C", (), {"types": ["Creature"], "power": 2, "toughness": 2, "tapped": False})(),
            "b1": type("C", (), {"types": ["Creature"], "power": 3, "toughness": 3, "tapped": False})(),
            "b2": type("C", (), {"types": ["Creature"], "power": 2, "toughness": 2, "tapped": False})(),
        }

    class ConvertState:
        players = {
            1: type("P", (), {"life": 14, "hand": [], "battlefield": ["a1", "a2"], "mana_pool": {}})(),
            2: type("P", (), {"life": 9, "hand": [], "battlefield": ["b1"], "mana_pool": {}})(),
        }
        cards = {
            "a1": type("C", (), {"types": ["Creature"], "power": 4, "toughness": 4, "tapped": False})(),
            "a2": type("C", (), {"types": ["Creature"], "power": 3, "toughness": 3, "tapped": False})(),
            "b1": type("C", (), {"types": ["Creature"], "power": 2, "toughness": 2, "tapped": False})(),
        }

    assert ai._board_role(StabilizeState(), 1) == "stabilize"
    assert ai._board_role(ConvertState(), 1) == "convert"


def test_board_role_adjusts_pass_bias_for_control_and_aggro_lines() -> None:
    control_ai = AIAgent(difficulty="master", archetype="Control")
    aggro_ai = AIAgent(difficulty="master", archetype="Aggro")

    class ControlStabilizeState:
        step = "precombat_main"
        active_player = 1
        stack = []
        turn = 6
        players = {
            1: type("P", (), {"life": 6, "hand": ["c1"], "battlefield": ["a1"], "mana_pool": {}})(),
            2: type("P", (), {"life": 16, "hand": [], "battlefield": ["b1", "b2"], "mana_pool": {}})(),
        }
        cards = {
            "c1": type("C", (), {"types": ["Instant"], "name": "Counterspell", "oracle_text": "Counter target spell."})(),
            "a1": type("C", (), {"types": ["Creature"], "power": 2, "toughness": 2, "tapped": False})(),
            "b1": type("C", (), {"types": ["Creature"], "power": 3, "toughness": 3, "tapped": False})(),
            "b2": type("C", (), {"types": ["Creature"], "power": 2, "toughness": 2, "tapped": False})(),
        }

    class AggroConvertState:
        step = "precombat_main"
        active_player = 1
        stack = []
        turn = 6
        players = {
            1: type("P", (), {"life": 14, "hand": ["t1"], "battlefield": ["a1", "a2"], "mana_pool": {}})(),
            2: type("P", (), {"life": 9, "hand": [], "battlefield": ["b1"], "mana_pool": {}})(),
        }
        cards = {
            "t1": type("C", (), {"types": ["Creature"], "name": "Goblin Guide", "oracle_text": "", "power": 2, "toughness": 2})(),
            "a1": type("C", (), {"types": ["Creature"], "power": 4, "toughness": 4, "tapped": False})(),
            "a2": type("C", (), {"types": ["Creature"], "power": 3, "toughness": 3, "tapped": False})(),
            "b1": type("C", (), {"types": ["Creature"], "power": 2, "toughness": 2, "tapped": False})(),
        }

    assert control_ai._pass_bias(ControlStabilizeState(), 1) > aggro_ai._pass_bias(AggroConvertState(), 1)


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


def test_control_ai_holds_small_attacker_back_into_larger_blocker_when_not_pressing() -> None:
    ai = AIAgent(difficulty="master", archetype="Control")
    moves = [
        {"type": "attack", "options": ["atk-1"]},
        {"type": "pass_priority"},
    ]

    class FakeState:
        turn = 7
        step = "declare_attackers"
        active_player = 1
        priority_player = 1
        pregame_pending = False
        winner = None
        stack = []
        players = {
            1: type("P", (), {"life": 19, "hand": ["draw-1", "counter-1"], "battlefield": ["atk-1"], "mana_pool": {}})(),
            2: type("P", (), {"life": 19, "hand": [], "battlefield": ["blk-1"], "mana_pool": {}})(),
        }
        cards = {
            "atk-1": type("C", (), {"types": ["Creature"], "name": "1/1", "power": 1, "toughness": 1, "keywords": [], "tapped": False})(),
            "blk-1": type("C", (), {"types": ["Creature"], "name": "3/3", "power": 3, "toughness": 3, "keywords": [], "tapped": False})(),
            "draw-1": type("C", (), {"types": ["Instant"], "name": "Consider", "oracle_text": "Draw a card.", "mana_cost": "{U}"})(),
            "counter-1": type("C", (), {"types": ["Instant"], "name": "Counterspell", "oracle_text": "Counter target spell.", "mana_cost": "{U}{U}"})(),
        }
        attackers = []
        attack_targets = {}
        blocks = {}
        passed_priority = set()
        loyalty_activated_this_turn = set()

    decision = ai.choose_action(FakeState(), moves, 1)
    assert decision.action["type"] == "pass_priority"


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


def test_control_ai_keeps_borderline_two_land_hand_with_real_action() -> None:
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
        players = {1: type("P", (), {"hand": ["l1", "l2", "s1", "s2", "s3"]})()}
        cards = {
            "l1": Card(["Land"], name="Island", type_line="Basic Land — Island", oracle_text="{T}: Add {U}."),
            "l2": Card(["Land"], name="Island", type_line="Basic Land — Island", oracle_text="{T}: Add {U}."),
            "s1": Card(["Instant"], "{U}", name="Consider", oracle_text="Scry 1, draw a card."),
            "s2": Card(["Instant"], "{U}{U}", name="Counterspell", oracle_text="Counter target spell."),
            "s3": Card(["Instant"], "{1}{B}", name="Go for the Throat", oracle_text="Destroy target creature."),
        }

    decision = ai.choose_mulligan_action(FakeState(), 1)
    assert decision.action["type"] == "keep_hand"


def test_ramp_ai_keeps_two_land_hand_with_acceleration() -> None:
    ai = AIAgent(difficulty="strong", archetype="Ramp")

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
        players = {1: type("P", (), {"hand": ["l1", "l2", "s1", "s2", "s3"]})()}
        cards = {
            "l1": Card(["Land"], name="Forest", type_line="Basic Land — Forest", oracle_text="{T}: Add {G}."),
            "l2": Card(["Land"], name="Forest", type_line="Basic Land — Forest", oracle_text="{T}: Add {G}."),
            "s1": Card(["Sorcery"], "{1}{G}", name="Cultivate", oracle_text="Search your library for up to two basic land cards."),
            "s2": Card(["Sorcery"], "{2}{G}{G}", name="Topiary Stomper", oracle_text="When Topiary Stomper enters the battlefield, search your library for a basic land card."),
            "s3": Card(["Sorcery"], "{1}{G}", name="Explore", oracle_text="Draw a card. You may play an additional land this turn."),
        }

    decision = ai.choose_mulligan_action(FakeState(), 1)
    assert decision.action["type"] == "keep_hand"


def test_aggro_ai_mulligans_hand_without_early_pressure() -> None:
    ai = AIAgent(difficulty="strong", archetype="Aggro")

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
        players = {1: type("P", (), {"hand": ["l1", "l2", "l3", "s1", "s2", "s3", "s4"]})()}
        cards = {
            "l1": Card(["Land"], name="Mountain", type_line="Basic Land — Mountain", oracle_text="{T}: Add {R}."),
            "l2": Card(["Land"], name="Mountain", type_line="Basic Land — Mountain", oracle_text="{T}: Add {R}."),
            "l3": Card(["Land"], name="Mountain", type_line="Basic Land — Mountain", oracle_text="{T}: Add {R}."),
            "s1": Card(["Sorcery"], "{4}{R}", name="Divination", oracle_text="Draw two cards."),
            "s2": Card(["Sorcery"], "{4}{R}", name="Slow Value", oracle_text="Draw a card."),
            "s3": Card(["Instant"], "{5}{R}", name="Big Setup", oracle_text="Create a token."),
            "s4": Card(["Enchantment"], "{4}{R}", name="Slow Engine", oracle_text="Whenever you cast a spell, draw a card."),
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


def test_control_ai_casts_big_creature_on_clear_turn_four_board() -> None:
    ai = AIAgent(difficulty="master", archetype="Control")
    moves = [
        {"type": "pass_priority"},
        {"type": "cast_spell", "card_name": "Dream Trawler", "card_id": "big-1"},
    ]

    class FakeState:
        turn = 4
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


def test_master_ai_uses_deeper_planner_on_complex_midgame_board() -> None:
    ai = AIAgent(difficulty="master", archetype="Control")
    moves = [
        {"type": "pass_priority"},
        {"type": "cast_spell", "card_name": "Dream Trawler", "card_id": "big-1"},
    ]

    class FakeState:
        turn = 6
        step = "precombat_main"
        active_player = 1
        priority_player = 1
        pregame_pending = False
        winner = None
        stack = []
        players = {
            1: type("P", (), {"life": 18, "hand": ["big-1"], "battlefield": ["a1", "a2", "a3", "a4", "a5", "a6"], "mana_pool": {}})(),
            2: type("P", (), {"life": 18, "hand": [], "battlefield": ["b1", "b2", "b3", "b4", "b5", "b6"], "mana_pool": {}})(),
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
        for cid in ["a1", "a2", "a3", "a4", "a5", "a6", "b1", "b2", "b3", "b4", "b5", "b6"]:
            cards[cid] = type("C", (), {"types": ["Creature"], "name": cid, "power": 1, "toughness": 1, "tapped": False})()
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


def test_ai_x_value_accounts_for_opponent_static_spell_tax() -> None:
    state = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Island"}],
        [{"quantity": 60, "card_name": "Plains"}],
        seed=972,
    )
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.turn = 8
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = 1
    state.priority_player = 1
    p1 = state.players[1]
    p2 = state.players[2]
    p1.hand.clear()
    for index in range(9):
        land_id = f"x-land-{index}"
        land = CardInstance(land_id, "Swamp", 1, 1, Zone.BATTLEFIELD, ["Land"], type_line="Basic Land — Swamp")
        state.cards[land_id] = land
        p1.battlefield.append(land_id)
    tax = CardInstance(
        "tax", "Thalia", 2, 2, Zone.BATTLEFIELD, ["Creature"],
        oracle_text="Noncreature spells cost {1} more to cast.", power=2, toughness=1,
    )
    spell = CardInstance(
        "meathook", "The Meathook Massacre", 1, 1, Zone.HAND, ["Enchantment"],
        mana_cost="{X}{B}{B}", oracle_text="When The Meathook Massacre enters the battlefield, each creature gets -X/-X until end of turn.",
    )
    state.cards.update({tax.id: tax, spell.id: spell})
    p2.battlefield.append(tax.id)
    p1.hand.append(spell.id)

    chosen = AIAgent(difficulty="master", archetype="Control")._choose_x_value(
        state, 1, spell.mana_cost, card=spell,
    )

    assert chosen == 6


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


def test_ai_rejects_low_impact_x_value_for_token_spells() -> None:
    ai = AIAgent(difficulty="master", archetype="Control")

    class FakeState:
        turn = 3
        step = "precombat_main"
        active_player = 1
        priority_player = 1
        players = {
            1: type("P", (), {"life": 20, "hand": ["xspell-1"], "battlefield": ["l1", "l2"], "mana_pool": {}})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": [], "mana_pool": {}})(),
        }
        cards = {
            "xspell-1": type("C", (), {"types": ["Instant"], "name": "Secure the Wastes", "oracle_text": "Create X 1/1 white Warrior creature tokens.", "mana_cost": "{X}{W}", "keywords": []})(),
            "l1": type("C", (), {"types": ["Land"], "name": "Plains", "tapped": False, "type_line": "Basic Land — Plains", "oracle_text": "{T}: Add {W}."})(),
            "l2": type("C", (), {"types": ["Land"], "name": "Plains", "tapped": False, "type_line": "Basic Land — Plains", "oracle_text": "{T}: Add {W}."})(),
        }

    x_value = ai._choose_x_value(FakeState(), 1, "{X}{W}", card=FakeState.cards["xspell-1"])
    assert x_value == 0


def test_ai_prefers_positive_x_for_interactive_x_removal() -> None:
    ai = AIAgent(difficulty="master", archetype="Control")

    class FakeState:
        turn = 2
        step = "precombat_main"
        active_player = 1
        priority_player = 1
        players = {
            1: type("P", (), {"life": 20, "hand": ["xspell-1"], "battlefield": ["l1", "l2", "l3", "l4"], "mana_pool": {}})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": ["enemy-1"], "mana_pool": {}})(),
        }
        cards = {
            "xspell-1": type("C", (), {"types": ["Instant"], "name": "March of Otherworldly Light", "oracle_text": "Exile target nonland permanent with mana value X or less.", "mana_cost": "{X}{W}", "keywords": []})(),
            "l1": type("C", (), {"types": ["Land"], "name": "Plains", "tapped": False, "type_line": "Basic Land — Plains", "oracle_text": "{T}: Add {W}."})(),
            "l2": type("C", (), {"types": ["Land"], "name": "Island", "tapped": False, "type_line": "Basic Land — Island", "oracle_text": "{T}: Add {U}."})(),
            "l3": type("C", (), {"types": ["Land"], "name": "Island", "tapped": False, "type_line": "Basic Land — Island", "oracle_text": "{T}: Add {U}."})(),
            "l4": type("C", (), {"types": ["Land"], "name": "Island", "tapped": False, "type_line": "Basic Land — Island", "oracle_text": "{T}: Add {U}."})(),
            "enemy-1": type("C", (), {"types": ["Artifact"], "name": "Lockstone", "tapped": False})(),
        }

    x_value = ai._choose_x_value(FakeState(), 1, "{X}{W}", card=FakeState.cards["xspell-1"])
    assert x_value >= 1


def test_control_ai_prefers_moderate_x_value_over_max_on_stable_board() -> None:
    ai = AIAgent(difficulty="master", archetype="Control")

    class FakeState:
        turn = 5
        step = "precombat_main"
        active_player = 1
        priority_player = 1
        players = {
            1: type("P", (), {"life": 20, "hand": ["xspell-1"], "battlefield": ["l1", "l2", "l3", "l4", "l5", "l6"], "mana_pool": {}})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": [], "mana_pool": {}})(),
        }
        cards = {
            "xspell-1": type("C", (), {"types": ["Instant"], "name": "Secure the Wastes", "oracle_text": "Create X 1/1 white Warrior creature tokens.", "mana_cost": "{X}{W}", "keywords": []})(),
            "l1": type("C", (), {"types": ["Land"], "name": "Plains", "tapped": False, "type_line": "Basic Land — Plains", "oracle_text": "{T}: Add {W}."})(),
            "l2": type("C", (), {"types": ["Land"], "name": "Plains", "tapped": False, "type_line": "Basic Land — Plains", "oracle_text": "{T}: Add {W}."})(),
            "l3": type("C", (), {"types": ["Land"], "name": "Plains", "tapped": False, "type_line": "Basic Land — Plains", "oracle_text": "{T}: Add {W}."})(),
            "l4": type("C", (), {"types": ["Land"], "name": "Plains", "tapped": False, "type_line": "Basic Land — Plains", "oracle_text": "{T}: Add {W}."})(),
            "l5": type("C", (), {"types": ["Land"], "name": "Plains", "tapped": False, "type_line": "Basic Land — Plains", "oracle_text": "{T}: Add {W}."})(),
            "l6": type("C", (), {"types": ["Land"], "name": "Plains", "tapped": False, "type_line": "Basic Land — Plains", "oracle_text": "{T}: Add {W}."})(),
        }
        stack = []
        winner = None
        pregame_pending = False
        attackers = []
        attack_targets = {}
        blocks = {}
        passed_priority = set()
        loyalty_activated_this_turn = set()

    x_value = ai._choose_x_value(FakeState(), 1, "{X}{W}", card=FakeState.cards["xspell-1"])
    assert x_value == 3


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


def test_ai_uses_role_specific_log_priors_when_board_is_stable() -> None:
    ai = AIAgent(difficulty="master", archetype="Control")
    old = AIAgent._log_priors_cache
    AIAgent._log_priors_cache = {
        "generated_at": None,
        "samples": {"games": 10, "logs": 1000},
        "cards": {
            "memory deluge": {
                "casts": 30,
                "seen_in_logs": 100,
                "avg_turn": 7.9,
                "early_turn_cast_rate": 0.08,
                "mid_turn_cast_rate": 0.22,
                "late_turn_cast_rate": 0.7,
                "preferred_min_turn": 7,
                "board_roles": {
                    "control": {
                        "casts": 12,
                        "avg_turn": 4.4,
                        "early_turn_cast_rate": 0.33,
                        "mid_turn_cast_rate": 0.2,
                        "late_turn_cast_rate": 0.6,
                        "preferred_min_turn": 4,
                    }
                },
            }
        },
    }
    moves = [
        {
            "type": "cast_spell",
            "card_id": "deluge-1",
            "card_name": "Memory Deluge",
            "mana_cost": "{2}{U}{U}",
            "target_hints": {},
        },
        {"type": "pass_priority"},
    ]

    class FakeState:
        turn = 5
        step = "precombat_main"
        active_player = 1
        priority_player = 1
        players = {
            1: type("P", (), {"life": 18, "hand": ["deluge-1", "f1", "f2", "f3"], "battlefield": ["l1", "l2", "l3", "l4"], "mana_pool": {}})(),
            2: type("P", (), {"life": 16, "hand": ["x"], "battlefield": ["o1"], "mana_pool": {}})(),
        }
        cards = {
            "deluge-1": type("C", (), {"types": ["Instant"], "name": "Memory Deluge", "oracle_text": "Look at the top X cards of your library.", "mana_cost": "{2}{U}{U}", "keywords": []})(),
            "l1": type("C", (), {"types": ["Land"], "name": "Island", "tapped": False, "type_line": "Basic Land — Island", "oracle_text": "{T}: Add {U}."})(),
            "l2": type("C", (), {"types": ["Land"], "name": "Island", "tapped": False, "type_line": "Basic Land — Island", "oracle_text": "{T}: Add {U}."})(),
            "l3": type("C", (), {"types": ["Land"], "name": "Island", "tapped": False, "type_line": "Basic Land — Island", "oracle_text": "{T}: Add {U}."})(),
            "l4": type("C", (), {"types": ["Land"], "name": "Island", "tapped": False, "type_line": "Basic Land — Island", "oracle_text": "{T}: Add {U}."})(),
            "o1": type("C", (), {"types": ["Land"], "name": "Island", "tapped": False, "type_line": "Basic Land — Island", "oracle_text": "{T}: Add {U}."})(),
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
        assert ai._historical_cast_timing_bias(FakeState(), FakeState.cards["deluge-1"], 1) > 0
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


def test_ai_prefers_preserving_mana_creature_when_other_good_block_exists() -> None:
    ai = AIAgent(difficulty="strong", archetype="Control")
    move = {
        "type": "block",
        "attackers": [{"id": "atk-3-3", "name": "3/3"}],
        "blockers": [
            {"id": "mana-dork", "name": "Llanowar Elves"},
            {"id": "safe-blocker", "name": "4/4"},
        ],
    }

    class FakeState:
        priority_player = 1
        players = {
            1: type("P", (), {"life": 12, "hand": [], "battlefield": ["mana-dork", "safe-blocker"], "mana_pool": {}})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": ["atk-3-3"], "mana_pool": {}})(),
        }
        cards = {
            "atk-3-3": type("C", (), {"types": ["Creature"], "name": "3/3", "power": 3, "toughness": 3, "tapped": True})(),
            "mana-dork": type(
                "C",
                (),
                {"types": ["Creature"], "name": "Llanowar Elves", "power": 1, "toughness": 1, "tapped": False, "oracle_text": "{T}: Add {G}."},
            )(),
            "safe-blocker": type("C", (), {"types": ["Creature"], "name": "4/4", "power": 4, "toughness": 4, "tapped": False})(),
        }
        stack = []
        step = Step.DECLARE_BLOCKERS
        active_player = 2
        turn = 5

    out = ai._materialize_action(FakeState(), move, 1)
    assert out["type"] == "block"
    assert out.get("blocks") == {"atk-3-3": "safe-blocker"}


def test_ai_blocks_with_mana_creature_when_it_is_the_only_profitable_assignment() -> None:
    ai = AIAgent(difficulty="strong", archetype="Control")
    move = {
        "type": "block",
        "attackers": [{"id": "atk-6-6", "name": "6/6"}],
        "blockers": [{"id": "mana-dork", "name": "Llanowar Elves"}],
    }

    class FakeState:
        priority_player = 1
        players = {
            1: type("P", (), {"life": 6, "hand": [], "battlefield": ["mana-dork"], "mana_pool": {}})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": ["atk-6-6"], "mana_pool": {}})(),
        }
        cards = {
            "atk-6-6": type("C", (), {"types": ["Creature"], "name": "6/6", "power": 6, "toughness": 6, "tapped": True})(),
            "mana-dork": type(
                "C",
                (),
                {"types": ["Creature"], "name": "Llanowar Elves", "power": 1, "toughness": 1, "tapped": False, "oracle_text": "{T}: Add {G}."},
            )(),
        }
        stack = []
        step = Step.DECLARE_BLOCKERS
        active_player = 2
        turn = 5

    out = ai._materialize_action(FakeState(), move, 1)
    assert out["type"] == "block"
    assert out.get("blocks") == {"atk-6-6": "mana-dork"}


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


def test_ai_targets_high_threat_enchantment_when_available() -> None:
    ai = AIAgent(difficulty="master", archetype="Aggro")
    move = {
        "type": "cast_spell",
        "card_name": "Disenchant",
        "card_id": "rem-1",
        "target_hints": {
            "enchantment_targets": [{"id": "ench-low", "label": "Minor Aura"}, {"id": "ench-high", "label": "Lock Piece"}],
        },
    }

    class FakeState:
        players = {
            1: type("P", (), {"life": 20, "hand": ["rem-1"], "battlefield": [], "mana_pool": {}})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": ["ench-low", "ench-high"], "mana_pool": {}})(),
        }
        cards = {
            "rem-1": type("C", (), {"types": ["Instant"], "name": "Disenchant", "oracle_text": "Destroy target artifact or enchantment."})(),
            "ench-low": type("C", (), {"types": ["Enchantment"], "name": "Minor Aura", "oracle_text": "Enchanted creature gets +1/+1.", "controller": 2})(),
            "ench-high": type(
                "C",
                (),
                {"types": ["Enchantment"], "name": "Solemnity Lock", "oracle_text": "Players can't get counters. Your opponents can't gain life.", "controller": 2},
            )(),
        }
        stack = []

    out = ai._materialize_action(FakeState(), move, 1)
    assert out["targets"]["target_card_id"] == "ench-high"


def test_counter_target_prefers_high_impact_artifact_stack_spell() -> None:
    ai = AIAgent(difficulty="master", archetype="Control")
    moves = [
        {
            "type": "cast_spell",
            "card_name": "Counterspell",
            "card_id": "counter-1",
            "target_hints": {
                "stack_targets": [
                    {"id": "stack-small", "label": "Opt"},
                    {"id": "stack-big", "label": "The One Ring"},
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
            "c-big": type("C", (), {"types": ["Artifact"], "name": "The One Ring", "oracle_text": "At the beginning of your upkeep, you lose 1 life for each burden counter on The One Ring.\n{T}: Put a burden counter on The One Ring, then draw a card for each burden counter on The One Ring.", "mana_cost": "{4}"})(),
        }
        stack = [
            type("S", (), {"id": "stack-small", "label": "Opt", "source_card_id": "c-small", "controller": 2})(),
            type("S", (), {"id": "stack-big", "label": "The One Ring", "source_card_id": "c-big", "controller": 2})(),
        ]
        winner = None
        pregame_pending = False

    decision = ai.choose_action(FakeState(), moves, 1)
    assert decision.action["type"] == "cast_spell"
    assert decision.action["targets"]["target_stack_id"] == "stack-big"


def test_early_turn_cheap_proactive_cast_over_pass_when_opponent_tapped_low() -> None:
    ai = AIAgent(difficulty="master", archetype="Tempo")
    moves = [
        {"type": "pass_priority"},
        {"type": "cast_spell", "card_name": "Delver of Secrets", "card_id": "delver-1"},
    ]

    class FakeState:
        turn = 2
        step = Step.PRECOMBAT_MAIN
        active_player = 1
        priority_player = 1
        pregame_pending = False
        winner = None
        players = {
            1: type("P", (), {"life": 20, "hand": ["delver-1"], "battlefield": ["isl-1"], "mana_pool": {}})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": ["isl-2"], "mana_pool": {}})(),
        }
        cards = {
            "delver-1": type("C", (), {"types": ["Creature"], "name": "Delver of Secrets", "oracle_text": "", "mana_cost": "{U}"})(),
            "isl-1": type("C", (), {"types": ["Land"], "name": "Island", "oracle_text": "{T}: Add {U}.", "tapped": False})(),
            "isl-2": type("C", (), {"types": ["Land"], "name": "Island", "oracle_text": "{T}: Add {U}.", "tapped": True})(),
        }
        stack = []
        blocks = {}
        attackers = []
        attack_targets = {}
        passed_priority = set()
        loyalty_activated_this_turn = set()

    decision = ai.choose_action(FakeState(), moves, 1)
    assert decision.action["type"] == "cast_spell"
    assert decision.action["card_id"] == "delver-1"


def test_aggro_cast_bias_values_stronger_modal_face_higher() -> None:
    ai = AIAgent(difficulty="strong", archetype="Aggro")

    class FakeState:
        turn = 3
        step = "precombat_main"
        active_player = 1
        players = {
            1: type("P", (), {"life": 20, "hand": [], "battlefield": [], "mana_pool": {}})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": [], "mana_pool": {}})(),
        }
        stack = []
        cards = {
            "weak": type(
                "C",
                (),
                {
                    "types": ["Creature"],
                    "name": "Modal Adept",
                    "mana_cost": "{2}{G}",
                    "oracle_text": "",
                    "card_faces": [
                        {
                            "name": "Adept Form",
                            "oracle_text": "When this enters, create a 1/1 token.",
                            "mana_cost": "{2}{G}",
                            "type_line": "Creature - Elf",
                        },
                        {
                            "name": "Scholar Form",
                            "oracle_text": "When this enters, create a 1/1 token.",
                            "mana_cost": "{2}{G}",
                            "type_line": "Creature - Elf",
                        },
                    ],
                },
            )(),
            "strong": type(
                "C",
                (),
                {
                    "types": ["Creature"],
                    "name": "Modal Adept",
                    "mana_cost": "{2}{G}",
                    "oracle_text": "",
                    "card_faces": [
                        {
                            "name": "Adept Form",
                            "oracle_text": "When this enters, create a 1/1 token.",
                            "mana_cost": "{2}{G}",
                            "type_line": "Creature - Elf",
                        },
                        {
                            "name": "Scholar Form",
                            "oracle_text": "When this enters, draw a card and create a 1/1 token.",
                            "mana_cost": "{2}{G}",
                            "type_line": "Creature - Elf",
                        },
                    ],
                },
            )(),
        }

    weak_score = ai._cast_bias(FakeState(), {"type": "cast_spell", "card_id": "weak"}, 1)
    strong_score = ai._cast_bias(FakeState(), {"type": "cast_spell", "card_id": "strong"}, 1)
    assert strong_score > weak_score


def test_midrange_cast_bias_values_stronger_modal_face_higher() -> None:
    ai = AIAgent(difficulty="strong", archetype="Midrange")

    class FakeState:
        turn = 5
        step = "precombat_main"
        active_player = 1
        players = {
            1: type("P", (), {"life": 20, "hand": [], "battlefield": [], "mana_pool": {}})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": [], "mana_pool": {}})(),
        }
        stack = []
        cards = {
            "weak": type(
                "C",
                (),
                {
                    "types": ["Creature"],
                    "name": "Modal Adept",
                    "mana_cost": "{2}{G}",
                    "oracle_text": "",
                    "card_faces": [
                        {
                            "name": "Adept Form",
                            "oracle_text": "When this enters, create a 1/1 token.",
                            "mana_cost": "{2}{G}",
                            "type_line": "Creature - Elf",
                        },
                        {
                            "name": "Scholar Form",
                            "oracle_text": "When this enters, create a 1/1 token.",
                            "mana_cost": "{2}{G}",
                            "type_line": "Creature - Elf",
                        },
                    ],
                },
            )(),
            "strong": type(
                "C",
                (),
                {
                    "types": ["Creature"],
                    "name": "Modal Adept",
                    "mana_cost": "{2}{G}",
                    "oracle_text": "",
                    "card_faces": [
                        {
                            "name": "Adept Form",
                            "oracle_text": "When this enters, create a 1/1 token.",
                            "mana_cost": "{2}{G}",
                            "type_line": "Creature - Elf",
                        },
                        {
                            "name": "Scholar Form",
                            "oracle_text": "When this enters, draw a card and create a 1/1 token.",
                            "mana_cost": "{2}{G}",
                            "type_line": "Creature - Elf",
                        },
                    ],
                },
            )(),
        }

    weak_score = ai._cast_bias(FakeState(), {"type": "cast_spell", "card_id": "weak"}, 1)
    strong_score = ai._cast_bias(FakeState(), {"type": "cast_spell", "card_id": "strong"}, 1)
    assert strong_score > weak_score


def test_control_cast_bias_engine_tag_path_does_not_crash() -> None:
    ai = AIAgent(difficulty="master", archetype="Control")

    class FakeState:
        turn = 5
        step = "precombat_main"
        active_player = 1
        stack = []
        players = {
            1: type("P", (), {"life": 14, "hand": [], "battlefield": [], "mana_pool": {}})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": [], "mana_pool": {}})(),
        }
        cards = {
            "engine": type(
                "C",
                (),
                {
                    "types": ["Enchantment"],
                    "name": "Rhystic Study",
                    "mana_cost": "{2}{U}",
                    "oracle_text": "Whenever an opponent casts a spell, draw a card.",
                    "card_faces": [],
                },
            )(),
        }

    score = ai._cast_bias(FakeState(), {"type": "cast_spell", "card_id": "engine"}, 1)
    assert score > 0


def test_control_values_graveyard_recursion_when_a_spell_is_available() -> None:
    ai = AIAgent(difficulty="master", archetype="Control")

    class FakeState:
        turn = 8
        step = "precombat_main"
        active_player = 1
        priority_player = 1
        stack = []
        players = {
            1: type("P", (), {"life": 20, "hand": ["recursion", "value"], "battlefield": [], "graveyard": ["spell"], "mana_pool": {}})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": [], "graveyard": [], "mana_pool": {}})(),
        }
        cards = {
            "recursion": type(
                "C",
                (),
                {
                    "name": "Graveyard Threat",
                    "types": ["Creature"],
                    "oracle_text": "When this enters the battlefield, you may cast target instant card from your graveyard without paying its mana cost.",
                    "mana_cost": "{4}{U}{U}",
                    "power": 5,
                    "toughness": 6,
                    "keywords": [],
                },
            )(),
            "value": type(
                "C",
                (),
                {"name": "Value Enchantment", "types": ["Enchantment"], "oracle_text": "Draw a card.", "mana_cost": "{5}{U}"},
            )(),
            "spell": type("C", (), {"name": "Draw Spell", "types": ["Instant"], "oracle_text": "Draw two cards."})(),
        }

    assert "recursion" in ai._spell_tags(FakeState.cards["recursion"])
    recursion_score = ai._cast_bias(FakeState(), {"type": "cast_spell", "card_id": "recursion"}, 1)
    value_score = ai._cast_bias(FakeState(), {"type": "cast_spell", "card_id": "value"}, 1)
    assert recursion_score > value_score


def test_modal_face_proxy_uses_face_type_line_for_scoring() -> None:
    ai = AIAgent(difficulty="strong", archetype="Control")

    class FakeState:
        turn = 7
        step = "precombat_main"
        active_player = 1
        players = {
            1: type("P", (), {"life": 20, "hand": [], "battlefield": [], "mana_pool": {}})(),
            2: type("P", (), {"life": 14, "hand": [], "battlefield": [], "mana_pool": {}})(),
        }
        cards = {
            "modal": type(
                "C",
                (),
                {
                    "types": ["Creature"],
                    "name": "Dual Threat",
                    "mana_cost": "{2}{G}",
                    "oracle_text": "",
                        "card_faces": [
                            {
                            "name": "Seed Form",
                            "oracle_text": "Create a 1/1 token.",
                            "mana_cost": "{2}{G}",
                            "type_line": "Creature - Elf",
                        },
                        {
                            "name": "Bloom Form",
                            "oracle_text": "Draw a card.",
                            "mana_cost": "{2}{G}",
                            "type_line": "Instant",
                        },
                    ],
                },
            )(),
        }
        stack = []

    idx, score = ai._select_modal_face_index(FakeState(), FakeState.cards["modal"], 1)
    assert idx == 1
    assert score > 0


def test_modal_face_proxy_prefers_creature_face_when_board_is_empty() -> None:
    ai = AIAgent(difficulty="strong", archetype="Aggro")

    class FakeState:
        turn = 2
        step = "precombat_main"
        active_player = 1
        players = {
            1: type("P", (), {"life": 20, "hand": [], "battlefield": [], "mana_pool": {}})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": [], "mana_pool": {}})(),
        }
        cards = {
            "modal": type(
                "C",
                (),
                {
                    "types": ["Creature"],
                    "name": "Dual Threat",
                    "mana_cost": "{2}{G}",
                    "oracle_text": "",
                    "card_faces": [
                        {
                            "name": "Seed Form",
                            "oracle_text": "Create a 1/1 token.",
                            "mana_cost": "{2}{G}",
                            "type_line": "Creature - Elf",
                        },
                        {
                            "name": "Bloom Form",
                            "oracle_text": "Draw a card.",
                            "mana_cost": "{2}{G}",
                            "type_line": "Instant",
                        },
                    ],
                },
            )(),
        }
        stack = []

    idx, score = ai._select_modal_face_index(FakeState(), FakeState.cards["modal"], 1)
    assert idx == 0
    assert score > 0


def test_control_modal_face_prefers_interaction_face_under_pressure() -> None:
    ai = AIAgent(difficulty="master", archetype="Control")

    class FakeState:
        turn = 4
        step = "precombat_main"
        active_player = 1
        players = {
            1: type("P", (), {"life": 20, "hand": [], "battlefield": [], "mana_pool": {}})(),
            2: type("P", (), {"life": 18, "hand": [], "battlefield": ["enemy-1", "enemy-2"], "mana_pool": {}})(),
        }
        cards = {
            "modal": type(
                "C",
                (),
                {
                    "types": ["Creature"],
                    "name": "Dual Threat",
                    "mana_cost": "{2}{G}",
                    "oracle_text": "",
                    "card_faces": [
                        {
                            "name": "Board Form",
                            "oracle_text": "Create a 2/2 token creature.",
                            "mana_cost": "{2}{G}",
                            "type_line": "Creature - Elf",
                            "power": 2,
                            "toughness": 2,
                        },
                        {
                            "name": "Answer Form",
                            "oracle_text": "Destroy target creature with mana value 3 or less.",
                            "mana_cost": "{2}{G}",
                            "type_line": "Instant",
                        },
                    ],
                },
            )(),
            "enemy-1": type("C", (), {"types": ["Creature"], "name": "Threat 1", "power": 3, "toughness": 3})(),
            "enemy-2": type("C", (), {"types": ["Creature"], "name": "Threat 2", "power": 4, "toughness": 4})(),
        }
        stack = []

    idx, score = ai._select_modal_face_index(FakeState(), FakeState.cards["modal"], 1)
    assert idx == 1
    assert score > 0


def test_aggro_modal_face_prefers_creature_face_when_board_is_empty() -> None:
    ai = AIAgent(difficulty="strong", archetype="Aggro")

    class FakeState:
        turn = 3
        step = "precombat_main"
        active_player = 1
        players = {
            1: type("P", (), {"life": 20, "hand": [], "battlefield": [], "mana_pool": {}})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": [], "mana_pool": {}})(),
        }
        cards = {
            "modal": type(
                "C",
                (),
                {
                    "types": ["Creature"],
                    "name": "Dual Threat",
                    "mana_cost": "{2}{G}",
                    "oracle_text": "",
                    "card_faces": [
                        {
                            "name": "Board Form",
                            "oracle_text": "Create a 2/2 token creature.",
                            "mana_cost": "{2}{G}",
                            "type_line": "Creature - Elf",
                            "power": 2,
                            "toughness": 2,
                        },
                        {
                            "name": "Answer Form",
                            "oracle_text": "Destroy target creature with mana value 3 or less.",
                            "mana_cost": "{2}{G}",
                            "type_line": "Instant",
                        },
                    ],
                },
            )(),
        }
        stack = []

    idx, score = ai._select_modal_face_index(FakeState(), FakeState.cards["modal"], 1)
    assert idx == 0
    assert score > 0


def test_control_selects_counter_mode_when_stack_is_live() -> None:
    ai = AIAgent(difficulty="master", archetype="Control")

    class FakeState:
        turn = 5
        step = "precombat_main"
        active_player = 1
        priority_player = 1
        players = {
            1: type("P", (), {"life": 18, "hand": ["spell-1"], "battlefield": ["l1", "l2", "l3"], "mana_pool": {}})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": ["enemy-1"], "mana_pool": {}})(),
        }
        cards = {
            "spell-1": type(
                "C",
                (),
                {
                    "types": ["Instant"],
                    "name": "Modal Interaction",
                    "oracle_text": "Choose one — Counter target spell; Create two 1/1 white Soldier creature tokens.",
                    "mana_cost": "{1}{W}{U}",
                },
            )(),
            "l1": type("C", (), {"types": ["Land"], "name": "Island", "tapped": False, "type_line": "Basic Land — Island", "oracle_text": ""})(),
            "l2": type("C", (), {"types": ["Land"], "name": "Plains", "tapped": False, "type_line": "Basic Land — Plains", "oracle_text": ""})(),
            "l3": type("C", (), {"types": ["Land"], "name": "Plains", "tapped": False, "type_line": "Basic Land — Plains", "oracle_text": ""})(),
            "enemy-1": type("C", (), {"types": ["Creature"], "name": "Threat", "power": 4, "toughness": 4})(),
        }
        stack = [type("S", (), {"id": "stack-1", "label": "Lightning Bolt", "source_card_id": "bolt", "controller": 2})()]
        winner = None
        pregame_pending = False
        attackers = []
        attack_targets = {}
        blocks = {}
        passed_priority = set()
        loyalty_activated_this_turn = set()

    move = {
        "type": "cast_spell",
        "card_id": "spell-1",
        "card_name": "Modal Interaction",
        "mana_cost": "{1}{W}{U}",
        "target_hints": {"modes": ["Counter target spell", "Create two 1/1 white Soldier creature tokens."]},
    }

    out = ai._materialize_action(FakeState(), move, 1)
    assert out["targets"]["mode_text"] == "Counter target spell"


def test_control_prefers_removal_mode_over_draw_when_opponent_has_board_pressure() -> None:
    ai = AIAgent(difficulty="master", archetype="Control")

    class FakeState:
        turn = 5
        step = "precombat_main"
        active_player = 1
        priority_player = 1
        players = {
            1: type("P", (), {"life": 12, "hand": [], "battlefield": ["l1", "l2", "l3"], "mana_pool": {}})(),
            2: type("P", (), {"life": 16, "hand": [], "battlefield": ["enemy-1", "enemy-2"], "mana_pool": {}})(),
        }
        cards = {
            "l1": type("C", (), {"types": ["Land"], "name": "Island", "tapped": False, "type_line": "Basic Land — Island", "oracle_text": ""})(),
            "l2": type("C", (), {"types": ["Land"], "name": "Plains", "tapped": False, "type_line": "Basic Land — Plains", "oracle_text": ""})(),
            "l3": type("C", (), {"types": ["Land"], "name": "Plains", "tapped": False, "type_line": "Basic Land — Plains", "oracle_text": ""})(),
            "enemy-1": type("C", (), {"types": ["Creature"], "name": "Threat 1", "power": 3, "toughness": 3})(),
            "enemy-2": type("C", (), {"types": ["Creature"], "name": "Threat 2", "power": 4, "toughness": 4})(),
        }
        stack = []

    mode = ai._select_mode_text(FakeState(), type("C", (), {"oracle_text": "", "types": ["Instant"]})(), ["Draw two cards.", "Destroy target creature."], 1)
    assert mode == "Destroy target creature."


def test_aggro_prefers_token_mode_over_draw_when_board_is_empty() -> None:
    ai = AIAgent(difficulty="strong", archetype="Aggro")

    class FakeState:
        turn = 3
        step = "precombat_main"
        active_player = 1
        players = {
            1: type("P", (), {"life": 20, "hand": [], "battlefield": [], "mana_pool": {}})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": [], "mana_pool": {}})(),
        }
        cards = {}
        stack = []

    mode = ai._select_mode_text(FakeState(), type("C", (), {"oracle_text": "", "types": ["Sorcery"]})(), ["Draw a card.", "Create two 1/1 creature tokens."], 1)
    assert mode == "Create two 1/1 creature tokens."


def test_strategic_planner_considers_beyond_top_four_moves_on_complex_boards() -> None:
    ai = AIAgent(difficulty="master", archetype="Control")

    class FakeState:
        turn = 10
        step = Step.PRECOMBAT_MAIN
        active_player = 1
        priority_player = 1
        pregame_pending = False
        winner = None
        stack = []
        players = {
            1: type("P", (), {"life": 18, "hand": ["best"], "battlefield": ["a1", "a2", "a3", "a4", "a5", "a6"], "mana_pool": {}})(),
            2: type("P", (), {"life": 18, "hand": [], "battlefield": ["b1", "b2", "b3", "b4", "b5", "b6"], "mana_pool": {}})(),
        }
        cards = {
            "best": type("C", (), {"types": ["Instant"], "name": "Memory Deluge", "oracle_text": "Draw cards.", "mana_cost": "{2}{U}{U}", "keywords": []})(),
            "a1": type("C", (), {"types": ["Land"], "name": "Island", "type_line": "Basic Land — Island", "oracle_text": "{T}: Add {U}.", "tapped": False})(),
            "a2": type("C", (), {"types": ["Land"], "name": "Island", "type_line": "Basic Land — Island", "oracle_text": "{T}: Add {U}.", "tapped": False})(),
            "a3": type("C", (), {"types": ["Land"], "name": "Plains", "type_line": "Basic Land — Plains", "oracle_text": "{T}: Add {W}.", "tapped": False})(),
            "a4": type("C", (), {"types": ["Land"], "name": "Plains", "type_line": "Basic Land — Plains", "oracle_text": "{T}: Add {W}.", "tapped": False})(),
            "a5": type("C", (), {"types": ["Land"], "name": "Island", "type_line": "Basic Land — Island", "oracle_text": "{T}: Add {U}.", "tapped": False})(),
            "a6": type("C", (), {"types": ["Land"], "name": "Island", "type_line": "Basic Land — Island", "oracle_text": "{T}: Add {U}.", "tapped": False})(),
            "b1": type("C", (), {"types": ["Creature"], "name": "Threat 1", "power": 3, "toughness": 3})(),
            "b2": type("C", (), {"types": ["Creature"], "name": "Threat 2", "power": 3, "toughness": 3})(),
            "b3": type("C", (), {"types": ["Creature"], "name": "Threat 3", "power": 3, "toughness": 3})(),
            "b4": type("C", (), {"types": ["Creature"], "name": "Threat 4", "power": 3, "toughness": 3})(),
            "b5": type("C", (), {"types": ["Creature"], "name": "Threat 5", "power": 3, "toughness": 3})(),
            "b6": type("C", (), {"types": ["Creature"], "name": "Threat 6", "power": 3, "toughness": 3})(),
        }

    moves = [{"type": "pass_priority"}] + [
        {"type": "cast_spell", "card_id": f"m{i}", "card_name": f"Move {i}"} for i in range(1, 7)
    ]
    for idx in range(1, 7):
        FakeState.cards[f"m{idx}"] = type("C", (), {"types": ["Instant"], "name": f"Move {idx}", "oracle_text": f"Mode {idx}.", "mana_cost": "{1}{U}"})()

    ranked = [moves[1], moves[2], moves[3], moves[4], moves[5], moves[6], moves[0]]

    def fake_rank_moves(state, legal_moves, player_id):  # noqa: ANN001
        return list(ranked)

    def fake_materialize(state, move, player_id):  # noqa: ANN001
        return dict(move)

    def fake_score(state, move, player_id, depth):  # noqa: ANN001
        return 10.0 if move.get("card_id") == "m6" else float(move.get("card_id", "")[-1] if move.get("card_id") else 0)

    ai._rank_moves = fake_rank_moves  # type: ignore[method-assign]
    ai._materialize_action = fake_materialize  # type: ignore[method-assign]
    ai._strategic_line_score = fake_score  # type: ignore[method-assign]

    result = ai._strategic_plan_action(FakeState(), moves, 1)
    assert result is not None
    assert result["card_id"] == "m6"


def test_master_uses_two_ply_search_only_on_developed_boards() -> None:
    ai = AIAgent(difficulty="master", archetype="Control")

    class State:
        turn = 10
        players = {
            1: type("P", (), {"battlefield": [f"a{i}" for i in range(7)]})(),
            2: type("P", (), {"battlefield": [f"b{i}" for i in range(7)]})(),
        }

    assert ai._strategic_search_depth(State(), 1) == 2

    State.turn = 4
    assert ai._strategic_search_depth(State(), 1) == 1


def test_master_plus_uses_bounded_three_ply_search_on_late_developed_boards() -> None:
    ai = AIAgent(difficulty="master_plus", archetype="Control")

    class State:
        turn = 9
        players = {
            1: type("P", (), {"battlefield": [f"a{i}" for i in range(5)]})(),
            2: type("P", (), {"battlefield": [f"b{i}" for i in range(5)]})(),
        }

    assert ai._strategic_search_depth(State(), 1) == 3
    State.turn = 6
    assert ai._strategic_search_depth(State(), 1) == 2


def test_aggro_selects_token_mode_when_board_is_empty() -> None:
    ai = AIAgent(difficulty="strong", archetype="Aggro")

    class FakeState:
        turn = 3
        step = "precombat_main"
        active_player = 1
        priority_player = 1
        players = {
            1: type("P", (), {"life": 20, "hand": ["spell-1"], "battlefield": ["l1", "l2"], "mana_pool": {}})(),
            2: type("P", (), {"life": 20, "hand": [], "battlefield": [], "mana_pool": {}})(),
        }
        cards = {
            "spell-1": type(
                "C",
                (),
                {
                    "types": ["Sorcery"],
                    "name": "Modal Threat",
                    "oracle_text": "Choose one — Deal 3 damage to any target; Create a 2/2 white Knight creature token.",
                    "mana_cost": "{2}{W}",
                },
            )(),
            "l1": type("C", (), {"types": ["Land"], "name": "Plains", "tapped": False, "type_line": "Basic Land — Plains", "oracle_text": ""})(),
            "l2": type("C", (), {"types": ["Land"], "name": "Plains", "tapped": False, "type_line": "Basic Land — Plains", "oracle_text": ""})(),
        }
        stack = []
        winner = None
        pregame_pending = False
        attackers = []
        attack_targets = {}
        blocks = {}
        passed_priority = set()
        loyalty_activated_this_turn = set()

    move = {
        "type": "cast_spell",
        "card_id": "spell-1",
        "card_name": "Modal Threat",
        "mana_cost": "{2}{W}",
        "target_hints": {"modes": ["Deal 3 damage to any target", "Create a 2/2 white Knight creature token"]},
    }

    out = ai._materialize_action(FakeState(), move, 1)
    assert out["targets"]["mode_text"] == "Create a 2/2 white Knight creature token"
