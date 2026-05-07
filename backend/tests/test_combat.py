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


def test_summoning_sickness_cleared_only_for_old_creatures() -> None:
    """Creatures present at untap lose summoning sickness; new ones keep it."""
    from effects.registry import resolve_effect

    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False

    # Create a token for P1 in turn 1
    resolve_effect(
        state, 1, "create_token",
        {"name": "Veteran", "power": 2, "toughness": 2, "amount": 1, "keywords": []},
    )
    veteran_id = [c for c in state.players[1].battlefield if state.cards[c].name == "Veteran"][0]
    assert state.cards[veteran_id].entered_turn == 1

    # Advance to P2's turn (turn 2) — only clears P2's creatures
    engine = RulesEngine()
    state.step = Step.CLEANUP
    state.priority_player = 1
    state.passed_priority = set()
    engine.next_step(state)  # P1 cleanup -> P2 untap (turn 2)
    assert state.turn == 2
    assert state.active_player == 2

    # P1's Veteran still has SS — only P2's creatures were checked
    assert state.cards[veteran_id].summoning_sick is True

    # Create a creature for P2 during turn 2
    resolve_effect(
        state, 2, "create_token",
        {"name": "P2Creature", "power": 1, "toughness": 1, "amount": 1, "keywords": []},
    )
    p2_id = [c for c in state.players[2].battlefield if state.cards[c].name == "P2Creature"][0]
    assert state.cards[p2_id].entered_turn == 2

    # Advance to P1's turn 3 — clears P1's old creatures
    state.step = Step.CLEANUP
    state.passed_priority = set()
    engine.next_step(state)  # P2 cleanup -> P1 untap (turn 3)
    assert state.turn == 3
    assert state.active_player == 1

    # Veteran entered turn 1 < turn 3 -> SS cleared
    assert state.cards[veteran_id].summoning_sick is False
    # P2's creature still has SS (only P1's creatures checked)
    assert state.cards[p2_id].summoning_sick is True


def test_summoning_sickness_kept_for_creature_entering_this_turn() -> None:
    """A creature entering during a player's own turn keeps summoning sickness until their next turn."""
    from effects.registry import resolve_effect

    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False

    # Start on P1's turn 2
    state.turn = 2
    state.active_player = 1
    state.step = Step.PRECOMBAT_MAIN

    # Create a token during P1's turn 2
    resolve_effect(
        state, 1, "create_token",
        {"name": "FreshCreature", "power": 2, "toughness": 2, "amount": 1, "keywords": []},
    )
    cid = [c for c in state.players[1].battlefield if state.cards[c].name == "FreshCreature"][0]
    assert state.cards[cid].entered_turn == 2
    assert state.cards[cid].summoning_sick is True  # has SS — entered this turn

    # Advance to P2's turn (turn 3) — doesn't clear P1's SS
    engine = RulesEngine()
    state.step = Step.CLEANUP
    state.passed_priority = set()
    engine.next_step(state)  # -> P2 untap (turn 3)
    assert state.turn == 3
    assert state.active_player == 2
    assert state.cards[cid].summoning_sick is True  # unchanged — active_player is 2

    # Advance to P1's turn 4 — now entered_turn=2 < turn=4 -> SS cleared
    state.step = Step.CLEANUP
    state.passed_priority = set()
    engine.next_step(state)  # -> P1 untap (turn 4)
    assert state.turn == 4
    assert state.active_player == 1
    assert state.cards[cid].summoning_sick is False  # entered 2 < 4
