from __future__ import annotations

from game_state.state import MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine


def test_attack_can_target_planeswalker_and_reduce_loyalty() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    engine = RulesEngine()

    # Put attacker on P1 battlefield.
    atk = state.players[1].hand.pop()
    state.players[1].battlefield.append(atk)
    state.cards[atk].zone = Zone.BATTLEFIELD
    state.cards[atk].types = ["Creature"]
    state.cards[atk].power = 3
    state.cards[atk].toughness = 3
    state.cards[atk].summoning_sick = False

    # Put planeswalker on P2 battlefield.
    pw = state.players[2].hand.pop()
    state.players[2].battlefield.append(pw)
    state.cards[pw].zone = Zone.BATTLEFIELD
    state.cards[pw].name = "Teferi, Time Raveler"
    state.cards[pw].types = ["Planeswalker"]
    state.cards[pw].loyalty = 2

    state.active_player = 1
    state.priority_player = 1
    state.step = Step.DECLARE_ATTACKERS
    engine.take_action(
        state,
        1,
        {"type": "attack", "attackers": [atk], "attack_targets": {atk: f"planeswalker:{pw}"}},
    )
    state.step = Step.COMBAT_DAMAGE
    engine.take_action(state, 1, {"type": "combat_damage"})

    assert state.cards[pw].zone == Zone.GRAVEYARD


def test_planeswalker_loyalty_ability_appears_in_legal_moves() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.priority_player = 1
    state.step = Step.PRECOMBAT_MAIN
    engine = RulesEngine()

    pw = state.players[1].hand.pop()
    state.players[1].battlefield.append(pw)
    state.cards[pw].zone = Zone.BATTLEFIELD
    state.cards[pw].name = "Test Walker"
    state.cards[pw].types = ["Planeswalker"]
    state.cards[pw].loyalty = 3
    state.cards[pw].oracle_text = "+1: Draw a card.\n-2: Target player loses 2 life."

    moves = engine.legal_moves(state, 1)
    loyalty_moves = [m for m in moves if m.get("type") == "activate_loyalty" and m.get("card_id") == pw]
    assert len(loyalty_moves) == 2
