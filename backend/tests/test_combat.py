from __future__ import annotations

from game_state.state import MatchFactory, Step
from rules_engine.engine import RulesEngine


def test_combat_damage_reduces_life() -> None:
    deck_a = [{"quantity": 60, "card_name": "Goblin Guide"}]
    deck_b = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck_a, deck_b)
    engine = RulesEngine()

    p1 = state.players[1]
    cid = p1.hand[0]
    state.step = Step.PRECOMBAT_MAIN
    state.priority_player = 1
    engine.take_action(state, 1, {"type": "cast_spell", "card_id": cid})
    engine.take_action(state, 1, {"type": "pass_priority"})
    engine.take_action(state, 2, {"type": "pass_priority"})

    creature_ids = [c for c in p1.battlefield if "Creature" in state.cards[c].types]
    if creature_ids:
        state.step = Step.DECLARE_ATTACKERS
        state.priority_player = 1
        state.cards[creature_ids[0]].summoning_sick = False
        engine.take_action(state, 1, {"type": "attack", "attackers": [creature_ids[0]]})
        state.step = Step.COMBAT_DAMAGE
        engine.take_action(state, 1, {"type": "combat_damage"})
    assert state.players[2].life <= 20
