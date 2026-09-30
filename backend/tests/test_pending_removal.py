"""Real-card regression for stacking redundant removal before passing."""
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from ai.pending_effects import pending_removal_destinations
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine


CARDS = {row["name"]: row for row in json.loads(
    (Path(__file__).parent / "fixtures" / "pending_removal.json").read_text())}


def add_card(state, name, zone, player=1):
    raw = CARDS[name]
    card = CardInstance(f"{name}-{len(state.cards)}", name, player, player, zone,
                        [kind for kind in ["Creature", "Artifact", "Enchantment", "Instant", "Sorcery"]
                         if kind in raw["type_line"].split()], mana_cost=raw["mana_cost"],
                        oracle_text=raw["oracle_text"], type_line=raw["type_line"],
                        power=int(raw["power"]) if raw["power"] else None,
                        toughness=int(raw["toughness"]) if raw["toughness"] else None,
                        keywords=raw["keywords"], colors=raw["colors"])
    state.cards[card.id] = card
    getattr(state.players[player], zone.value).append(card.id)
    return card


def fixture(target="Sprite Dragon", removal="Go for the Throat"):
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=711)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.priority_player = state.active_player = 1
    state.players[1].lands_played_this_turn = 1
    for player in state.players.values():
        player.mana_pool.update({"C": 6, "U": 6, "B": 6, "G": 6, "R": 6})
    victim = add_card(state, target, Zone.BATTLEFIELD, 2)
    first = add_card(state, removal, Zone.HAND)
    second = add_card(state, removal, Zone.HAND)
    state = checked_action(state, RulesEngine(), 1, {
        "type": "cast_spell", "card_id": first.id, "targets": {"target_card_id": victim.id},
    })
    return state, victim.id, second.id


@pytest.mark.parametrize("target,removal", [
    ("Sprite Dragon", "Go for the Throat"),
    ("Sprite Dragon", "Fatal Push"),
    ("Mind Stone", "Naturalize"),
    ("Phyrexian Arena", "Naturalize"),
])
def test_ai_holds_duplicate_removal_for_already_covered_permanent(target, removal):
    state, victim, held = fixture(target, removal)
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    before = serialize_match_snapshot(state)
    assert pending_removal_destinations(state, 1)[victim] == Zone.GRAVEYARD
    decision = AIAgent(archetype="Control", difficulty="master").choose_action(state, RulesEngine().legal_moves(state, 1), 1)
    assert decision.action["type"] == "pass_priority", decision
    assert held in state.players[1].hand and state.cards[victim].zone == Zone.BATTLEFIELD
    assert serialize_match_snapshot(state) == before


def test_ai_redirects_removal_to_an_uncovered_threat():
    state, victim, held = fixture()
    other = add_card(state, "Sprite Dragon", Zone.BATTLEFIELD, 2)
    decision = AIAgent(archetype="Control").choose_action(state, RulesEngine().legal_moves(state, 1), 1)
    assert decision.action["card_id"] == held
    assert decision.action["targets"]["target_card_id"] == other.id
    assert decision.action["targets"]["target_card_id"] != victim


def test_known_counter_response_keeps_backup_removal_available():
    state, victim, held = fixture()
    original = state.stack[-1].id
    RulesEngine().take_action(state, 1, {"type": "pass_priority"})
    counter = add_card(state, "Counterspell", Zone.HAND, 2)
    state = checked_action(state, RulesEngine(), 2, {
        "type": "cast_spell", "card_id": counter.id, "targets": {"target_stack_id": original},
    })
    RulesEngine().take_action(state, 2, {"type": "pass_priority"})
    assert victim not in pending_removal_destinations(state, 1)
    decision = AIAgent(archetype="Control").choose_action(state, RulesEngine().legal_moves(state, 1), 1)
    assert decision.action["card_id"] == held and decision.action["targets"]["target_card_id"] == victim


def test_pending_lethal_damage_covers_target_for_additional_destroy_spell():
    state, victim, _ = fixture(removal="Lightning Bolt")
    held = add_card(state, "Go for the Throat", Zone.HAND)
    assert pending_removal_destinations(state, 1)[victim] == Zone.GRAVEYARD
    move = next(move for move in RulesEngine().legal_moves(state, 1) if move.get("card_id") == held.id)
    assert AIAgent()._materialize_action(state, move, 1).get("_invalid_ai_choice")


def test_known_growth_response_to_damage_keeps_destroy_spell_available():
    state, victim, _ = fixture(removal="Lightning Bolt")
    held = add_card(state, "Go for the Throat", Zone.HAND)
    RulesEngine().take_action(state, 1, {"type": "pass_priority"})
    growth = add_card(state, "Giant Growth", Zone.HAND, 2)
    state = checked_action(state, RulesEngine(), 2, {
        "type": "cast_spell", "card_id": growth.id, "targets": {"target_card_id": victim},
    })
    RulesEngine().take_action(state, 2, {"type": "pass_priority"})
    assert victim not in pending_removal_destinations(state, 1)
    move = next(move for move in RulesEngine().legal_moves(state, 1) if move.get("card_id") == held.id)
    assert not AIAgent()._materialize_action(state, move, 1).get("_invalid_ai_choice")


def test_indestructible_target_is_not_falsely_predicted_to_die():
    state, victim, _ = fixture("Darksteel Myr", "Naturalize")
    assert victim not in pending_removal_destinations(state, 1)


def test_unresolved_choice_does_not_invent_a_stack_outcome():
    state, victim, _ = fixture()
    state.pending_mechanic_choice = {"kind": "draw", "player_id": 1}
    assert pending_removal_destinations(state, 1) is None
