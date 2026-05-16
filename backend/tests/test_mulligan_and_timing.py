from __future__ import annotations

from game_state.state import MatchFactory, Step
from rules_engine.engine import RulesEngine
from rules_engine.move_generator import legal_moves


def test_london_mulligan_flow_completes_pregame() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    engine = RulesEngine()

    assert state.pregame_pending is True
    engine.take_action(state, 1, {"type": "mulligan"})
    assert state.mulligan_count[1] == 1
    engine.take_action(state, 1, {"type": "keep_hand", "bottom_card_ids": []})
    engine.take_action(state, 2, {"type": "keep_hand", "bottom_card_ids": []})
    assert state.pregame_pending is False


def test_sorcery_speed_not_castable_off_main_timing() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}

    # Make player 2 priority on player 1 turn, non-instant spell in hand.
    state.active_player = 1
    state.priority_player = 2
    state.step = Step.BEGIN_COMBAT
    cid = state.players[2].hand[0]
    state.cards[cid].name = "Sorcery Test"
    state.cards[cid].types = ["Sorcery"]
    state.cards[cid].mana_cost = "{1}{U}"

    moves = legal_moves(state, 2)
    assert not any(m.get("type") == "cast_spell" and m.get("card_id") == cid for m in moves)


def test_first_player_skips_first_draw_with_explicit_log() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    engine = RulesEngine()

    engine.take_action(state, 1, {"type": "keep_hand", "bottom_card_ids": []})
    engine.take_action(state, 2, {"type": "keep_hand", "bottom_card_ids": []})
    # Advance from UNTAP -> UPKEEP -> DRAW on turn 1
    engine.take_action(state, 1, {"type": "pass_priority"})
    engine.take_action(state, 2, {"type": "pass_priority"})
    engine.take_action(state, 1, {"type": "pass_priority"})
    engine.take_action(state, 2, {"type": "pass_priority"})

    assert state.step == Step.DRAW
    hand_before = len(state.players[1].hand)
    lib_before = len(state.players[1].library)
    engine.take_action(state, 1, {"type": "pass_priority"})
    engine.take_action(state, 2, {"type": "pass_priority"})
    assert len(state.players[1].hand) == hand_before
    assert len(state.players[1].library) == lib_before
    assert any("skips draw on turn 1" in line.lower() for line in state.log)


def test_players_draw_on_later_turns_with_hand_count_change_log() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    engine = RulesEngine()

    engine.take_action(state, 1, {"type": "keep_hand", "bottom_card_ids": []})
    engine.take_action(state, 2, {"type": "keep_hand", "bottom_card_ids": []})

    def pass_until_turn(target_turn: int, active_player: int, step: Step) -> None:
        for _ in range(300):
            if state.turn == target_turn and state.active_player == active_player and state.step == step:
                return
            pid = state.priority_player
            engine.take_action(state, pid, {"type": "pass_priority"})
        assert False, "did not reach expected turn/step"

    # Player 2 should draw on turn 2 (between upkeep -> draw transition).
    pass_until_turn(2, 2, Step.UPKEEP)
    h2_before = len(state.players[2].hand)
    engine.take_action(state, state.priority_player, {"type": "pass_priority"})
    engine.take_action(state, state.priority_player, {"type": "pass_priority"})
    assert len(state.players[2].hand) == h2_before + 1

    # Player 1 should draw on turn 3 (between upkeep -> draw transition).
    pass_until_turn(3, 1, Step.UPKEEP)
    h1_before = len(state.players[1].hand)
    engine.take_action(state, state.priority_player, {"type": "pass_priority"})
    engine.take_action(state, state.priority_player, {"type": "pass_priority"})
    assert len(state.players[1].hand) == h1_before + 1
    assert any("draws a card. hand" in line.lower() for line in state.log)
