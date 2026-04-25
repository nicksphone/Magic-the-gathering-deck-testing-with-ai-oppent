from __future__ import annotations

from game_state.state import MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine


def test_attack_is_declared_once_per_combat_step() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.priority_player = 1
    state.step = Step.DECLARE_ATTACKERS
    state.attackers_declared = False
    engine = RulesEngine()

    atk = state.players[1].hand.pop()
    state.players[1].battlefield.append(atk)
    card = state.cards[atk]
    card.zone = Zone.BATTLEFIELD
    card.types = ["Creature"]
    card.power = 3
    card.toughness = 3
    card.summoning_sick = False
    card.tapped = False

    # First declaration is allowed.
    engine.take_action(state, 1, {"type": "attack", "attackers": [atk], "attack_targets": {atk: "player:2"}})
    assert state.attackers_declared is True

    # Subsequent legal move generation in same step should not include another attack declaration.
    moves = engine.legal_moves(state, 1)
    assert all(m.get("type") != "attack" for m in moves)
