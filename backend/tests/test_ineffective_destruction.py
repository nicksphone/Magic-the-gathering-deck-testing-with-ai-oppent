"""Canonical destruction targets remain legal, but not necessarily useful."""
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from ai.pending_effects import unproductive_destroy_targets
from game_state.serializers import serialize_match_snapshot
from game_state.state import CardInstance, Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_pending_removal import CARDS, add_card, fixture


@pytest.fixture(autouse=True)
def canonical_cards(monkeypatch):
    rows = json.loads((Path(__file__).parent / "fixtures" / "ineffective_destruction.json").read_text())
    for row in rows:
        monkeypatch.setitem(CARDS, row["name"], row)


def settled_state():
    state, victim, held = fixture("Darksteel Myr", "Naturalize")
    engine = RulesEngine()
    while state.stack:
        engine.take_action(state, state.priority_player, {"type": "pass_priority"})
    state.priority_player = 1
    land = next(move for move in engine.legal_moves(state, 1) if move["type"] == "play_land")
    state = checked_action(state, engine, 1, land)
    return state, victim, held


@pytest.mark.parametrize("difficulty", ["casual", "strong", "master"])
@pytest.mark.parametrize("archetype", ["Control", "Tempo", "Midrange", "Aggro"])
def test_ai_holds_useless_destruction_without_pending_removal(difficulty, archetype):
    state, _, held = settled_state()
    before = serialize_match_snapshot(state)
    ai = AIAgent(difficulty=difficulty, archetype=archetype)
    for _ in range(3):
        action = ai.choose_action(state, RulesEngine().legal_moves(state, 1), 1).action
        assert action["type"] == "pass_priority", action
    assert held in state.players[1].hand
    assert serialize_match_snapshot(state) == before


def test_destroy_redirects_from_indestructible_creature_to_productive_artifact():
    state, _, held = settled_state()
    productive = add_card(state, "Mind Stone", Zone.BATTLEFIELD, 2)
    decision = AIAgent(archetype="Control").choose_action(state, RulesEngine().legal_moves(state, 1), 1)
    assert decision.action["card_id"] == held
    assert decision.action["targets"]["target_card_id"] == productive.id


def test_doom_blade_avoids_high_threat_indestructible_creature():
    state, _, _ = settled_state()
    add_card(state, "Darksteel Colossus", Zone.BATTLEFIELD, 2)
    productive = add_card(state, "Sprite Dragon", Zone.BATTLEFIELD, 2)
    blade = add_card(state, "Doom Blade", Zone.HAND)
    move = next(move for move in RulesEngine().legal_moves(state, 1) if move.get("card_id") == blade.id)
    assert AIAgent()._materialize_action(state, move, 1)["targets"]["target_card_id"] == productive.id


def test_preselected_indestructible_target_is_not_an_ai_escape_hatch():
    state, victim, held = settled_state()
    move = next(move for move in RulesEngine().legal_moves(state, 1) if move.get("card_id") == held)
    move = {**move, "targets": {"target_card_id": victim}}
    assert AIAgent()._materialize_action(state, move, 1).get("_invalid_ai_choice")


def test_selected_modal_destroy_checks_remaining_targets_not_stale_modes():
    state, _, _ = settled_state()
    card = add_card(state, "Abrade", Zone.HAND)
    move = next(move for move in RulesEngine().legal_moves(state, 1) if move.get("card_id") == card.id)
    move = {**move, "targets": {"mode_text": "Destroy target artifact."}}
    assert AIAgent()._materialize_action(state, move, 1).get("_invalid_ai_choice")


def test_loyalty_destroy_does_not_waste_loyalty_on_indestructible():
    state, _, _ = settled_state()
    raw = CARDS["Vraska the Unseen"]
    card = CardInstance("vraska", raw["name"], 1, 1, Zone.BATTLEFIELD, ["Planeswalker"],
                        mana_cost=raw["mana_cost"], oracle_text=raw["oracle_text"],
                        type_line=raw["type_line"], colors=raw["colors"], loyalty=int(raw["loyalty"]))
    state.cards[card.id] = card
    state.players[1].battlefield.append(card.id)
    move = next(move for move in RulesEngine().legal_moves(state, 1)
                if move.get("card_id") == card.id and move.get("ability_delta") == -3)
    assert AIAgent()._materialize_action(state, move, 1).get("_invalid_ai_choice")


def test_human_can_legally_cast_at_indestructible_and_it_survives():
    state, victim, held = settled_state()
    state = checked_action(state, RulesEngine(), 1, {
        "type": "cast_spell", "card_id": held, "targets": {"target_card_id": victim},
    })
    assert state.stack[-1].source_card_id == held
    while state.stack:
        RulesEngine().take_action(state, state.priority_player, {"type": "pass_priority"})
    assert state.cards[victim].zone == Zone.BATTLEFIELD
    assert state.cards[held].zone == Zone.GRAVEYARD


def test_pure_activated_destroy_does_not_waste_its_sacrifice():
    state, _, _ = settled_state()
    source = add_card(state, "Thrashing Brontodon", Zone.BATTLEFIELD)
    before = serialize_match_snapshot(state)
    move = next(move for move in RulesEngine().legal_moves(state, 1)
                if move.get("card_id") == source.id and move["type"] == "activate_ability")
    assert AIAgent()._materialize_action(state, move, 1).get("_invalid_ai_choice")
    assert serialize_match_snapshot(state) == before


def test_secondary_draw_is_not_discarded_by_pure_destroy_guard():
    state, victim, _ = settled_state()
    card = add_card(state, "Slice in Twain", Zone.HAND)
    assert unproductive_destroy_targets(state, card, 1, {"target_card_id": victim}) == set()


def test_secondary_draw_still_resolves_when_indestructible_prevents_destruction():
    state, victim, _ = settled_state()
    card = add_card(state, "Slice in Twain", Zone.HAND)
    library = len(state.players[1].library)
    state = checked_action(state, RulesEngine(), 1, {
        "type": "cast_spell", "card_id": card.id, "targets": {"target_card_id": victim},
    })
    while state.stack:
        RulesEngine().take_action(state, state.priority_player, {"type": "pass_priority"})
    assert state.cards[victim].zone == Zone.BATTLEFIELD
    assert len(state.players[1].library) == library - 1
