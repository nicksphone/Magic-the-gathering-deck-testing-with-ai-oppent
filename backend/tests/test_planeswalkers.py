from __future__ import annotations

from ai.agent import AIAgent
from game_state.state import MatchFactory, Step, Zone
from rules_engine import combat
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import extract_loyalty_abilities


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


def test_planeswalker_x_loyalty_ability_requires_x_value_and_materializes() -> None:
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
    state.cards[pw].name = "X Walker"
    state.cards[pw].types = ["Planeswalker"]
    state.cards[pw].loyalty = 4
    state.cards[pw].oracle_text = "-X: Deal X damage to any target.\n+1: Draw a card."

    abilities = extract_loyalty_abilities(state.cards[pw])
    assert abilities[0]["x_cost"] is True

    moves = engine.legal_moves(state, 1)
    x_moves = [m for m in moves if m.get("type") == "activate_loyalty" and m.get("card_id") == pw and m.get("ability_x_cost")]
    assert len(x_moves) == 1
    assert x_moves[0]["target_hints"]["requires_x_value"] is True

    ai = AIAgent(difficulty="master", archetype="Control")
    materialized = ai._materialize_action(state, x_moves[0], 1)
    assert materialized.get("_invalid_ai_choice") is not True
    assert int(materialized["targets"]["x_value"]) > 0

    engine.take_action(state, 1, materialized)
    assert state.cards[pw].loyalty == 4 - int(materialized["targets"]["x_value"])


def test_unblocked_damage_to_removed_planeswalker_disappears():
    """When an unblocked attacker targets a PW that leaves the battlefield,
    the damage disappears — it does NOT redirect to the player."""
    from rules_engine.combat import _deal_unblocked_damage

    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}

    # Setup: attacker with 4 power, targeting a PW
    atk = state.players[1].hand.pop()
    state.players[1].battlefield.append(atk)
    state.cards[atk].zone = Zone.BATTLEFIELD
    state.cards[atk].types = ["Creature"]
    state.cards[atk].power = 4
    state.cards[atk].toughness = 3
    state.cards[atk].summoning_sick = False

    # PW starts on battlefield, then gets removed (simulating leaving)
    pw = state.players[2].hand.pop()
    state.cards[pw].zone = Zone.GRAVEYARD  # Already gone
    state.cards[pw].types = ["Planeswalker"]
    state.cards[pw].loyalty = 5

    p2_life_before = state.players[2].life

    result = _deal_unblocked_damage(state, f"planeswalker:{pw}", 4)

    # Damage should disappear — PW not on battlefield
    assert result == 0, f"Expected 0 damage, got {result}"
    assert state.players[2].life == p2_life_before, \
        f"Player life changed from {p2_life_before} to {state.players[2].life} — damage leaked to player!"


def test_trample_excess_damage_to_protected_planeswalker_is_prevented() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.step = Step.COMBAT_DAMAGE

    atk = state.players[1].hand.pop()
    state.players[1].battlefield.append(atk)
    state.cards[atk].zone = Zone.BATTLEFIELD
    state.cards[atk].types = ["Creature"]
    state.cards[atk].name = "Red Trampler"
    state.cards[atk].mana_cost = "{3}{R}"
    state.cards[atk].power = 4
    state.cards[atk].toughness = 4
    state.cards[atk].keywords = ["trample"]
    state.cards[atk].summoning_sick = False

    blk = state.players[2].hand.pop()
    state.players[2].battlefield.append(blk)
    state.cards[blk].zone = Zone.BATTLEFIELD
    state.cards[blk].types = ["Creature"]
    state.cards[blk].power = 1
    state.cards[blk].toughness = 1
    state.cards[blk].summoning_sick = False

    pw = state.players[2].hand.pop()
    state.players[2].battlefield.append(pw)
    state.cards[pw].zone = Zone.BATTLEFIELD
    state.cards[pw].name = "Protected Walker"
    state.cards[pw].types = ["Planeswalker"]
    state.cards[pw].loyalty = 5
    state.cards[pw].keywords = ["protection from red"]

    state.attackers = [atk]
    state.attack_targets = {atk: f"planeswalker:{pw}"}
    state.blocks = {atk: [blk]}

    combat.combat_damage(state)

    assert state.cards[pw].loyalty == 5
    assert state.players[2].life == 20
