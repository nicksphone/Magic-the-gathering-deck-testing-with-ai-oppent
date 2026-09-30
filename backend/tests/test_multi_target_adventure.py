"""Real Gollum / Meager Meal targets must be rechecked independently."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai.agent import AIAgent
from card_data.hydration import hydrate_deck_cards
from effects.handlers import copy_spell
from effects.registry import resolve_effect
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack


RAW = json.loads((Path(__file__).parent / "fixtures/multi_target_adventure.json").read_text())


def meal_state():
    row = SimpleNamespace(**{key: value for key, value in RAW.items() if key != "card_faces"},
                          card_faces_json=json.dumps(RAW["card_faces"]), image_uri=None)
    repo = SimpleNamespace(get_cached_cards_by_names=lambda names: {RAW["name"].lower(): row})
    deck = hydrate_deck_cards(repo, [{"quantity": 60, "card_name": RAW["name"]}])
    state = MatchFactory.from_decks(deck, deck, seed=211)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = 1
    state.players[1].mana_pool["B"] = 1
    card_id = state.players[1].hand[0]
    creature_id = state.players[2].hand.pop()
    state.players[2].battlefield.append(creature_id)
    state.cards[creature_id].zone = Zone.BATTLEFIELD
    return state, card_id, creature_id


def cast_meal(state, card_id, creature_id):
    action = {"type": "cast_spell", "card_id": card_id, "selected_face_index": 1,
              "targets": {"target_card_id": creature_id, "target_player": 2}}
    state = checked_action(state, RulesEngine(), 1, action)
    assert state.stack[-1].effect_key == "effect_sequence"
    assert len(state.stack[-1].payload["effects"]) == 2
    return state


def grant_player_hexproof(state):
    orb = CardInstance("orb", "Witchbane Orb", 2, 2, Zone.BATTLEFIELD, ["Artifact"],
                       oracle_text="When this artifact enters, destroy all Curses attached to you.\nYou have hexproof.")
    state.cards[orb.id] = orb
    state.players[2].battlefield.append(orb.id)


def test_meager_meal_all_targets_illegal_goes_to_graveyard() -> None:
    state, card_id, creature_id = meal_state()
    state = cast_meal(state, card_id, creature_id)
    resolve_effect(state, 2, "destroy_permanent", {"target_card_id": creature_id})
    grant_player_hexproof(state)
    state = deserialize_match_snapshot(serialize_match_snapshot(state))

    assert resolve_top_of_stack(state)
    assert state.cards[card_id].zone == Zone.GRAVEYARD
    assert card_id not in state.adventure_permissions
    assert state.players[2].life == 20


@pytest.mark.parametrize("lost_target", ["creature", "player"])
def test_meager_meal_one_legal_target_resolves_only_that_effect(lost_target: str) -> None:
    state, card_id, creature_id = meal_state()
    state = cast_meal(state, card_id, creature_id)
    if lost_target == "creature":
        resolve_effect(state, 2, "destroy_permanent", {"target_card_id": creature_id})
    else:
        grant_player_hexproof(state)
    state = deserialize_match_snapshot(serialize_match_snapshot(state))

    assert resolve_top_of_stack(state)
    assert state.cards[card_id].zone == Zone.EXILE
    assert state.adventure_permissions[card_id] == 1
    assert state.players[2].life == (22 if lost_target == "creature" else 20)
    assert state.cards[creature_id].counters.get("+1/+1", 0) == (1 if lost_target == "player" else 0)


def test_meager_meal_cannot_target_hexproof_player_at_cast() -> None:
    state, card_id, creature_id = meal_state()
    grant_player_hexproof(state)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, {
            "type": "cast_spell", "card_id": card_id, "selected_face_index": 1,
            "targets": {"target_card_id": creature_id, "target_player": 2},
        })
    assert serialize_match_snapshot(state) == before


def test_meager_meal_optional_creature_target_can_be_skipped() -> None:
    state, card_id, creature_id = meal_state()
    own_id = state.players[1].hand.pop(1)
    state.players[1].battlefield.append(own_id)
    state.cards[own_id].zone = Zone.BATTLEFIELD
    state = checked_action(state, RulesEngine(), 1, {
        "type": "cast_spell", "card_id": card_id, "selected_face_index": 1,
        "targets": {"target_player": 2},
    })
    assert resolve_top_of_stack(state)
    assert state.players[2].life == 22
    assert state.cards[creature_id].counters.get("+1/+1", 0) == 0
    assert state.cards[own_id].counters.get("+1/+1", 0) == 0
    assert state.cards[card_id].zone == Zone.EXILE


def test_meager_meal_copy_can_retarget_each_clause_after_snapshot() -> None:
    state, card_id, creature_id = meal_state()
    own_id = state.players[1].hand.pop(1)
    state.players[1].battlefield.append(own_id)
    state.cards[own_id].zone = Zone.BATTLEFIELD
    state = cast_meal(state, card_id, creature_id)
    original_id = state.stack[-1].id
    copy_spell(state, 1, {"target_stack_id": original_id, "may_choose_new_targets": True})
    assert state.pending_mechanic_choice is not None
    assert "target_card_id:" + own_id in state.pending_mechanic_choice["options"]
    state = checked_action(state, RulesEngine(), 1, {
        "type": "choose_mechanic", "card_ids": ["target_card_id:" + own_id],
    })
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert "target_player:1" in state.pending_mechanic_choice["options"]
    state = checked_action(state, RulesEngine(), 1, {
        "type": "choose_mechanic", "card_ids": ["target_player:1"],
    })
    assert state.pending_mechanic_choice is None
    assert resolve_top_of_stack(state)
    assert state.players[1].life == 22
    assert state.cards[own_id].counters.get("+1/+1") == 1
    assert state.cards[card_id].zone == Zone.STACK
    assert card_id not in state.adventure_permissions
    assert resolve_top_of_stack(state)
    assert state.players[2].life == 22
    assert state.cards[creature_id].counters.get("+1/+1") == 1
    assert state.cards[card_id].zone == Zone.EXILE
    assert state.adventure_permissions[card_id] == 1


def test_meager_meal_copy_partially_resolves_without_exile_permission() -> None:
    state, card_id, creature_id = meal_state()
    state = cast_meal(state, card_id, creature_id)
    copy_spell(state, 1, {"target_stack_id": state.stack[-1].id})
    resolve_effect(state, 2, "destroy_permanent", {"target_card_id": creature_id})
    state = deserialize_match_snapshot(serialize_match_snapshot(state))

    assert resolve_top_of_stack(state)
    assert state.players[2].life == 22
    assert state.cards[card_id].zone == Zone.STACK
    assert card_id not in state.adventure_permissions
    assert resolve_top_of_stack(state)
    assert state.players[2].life == 24
    assert state.cards[card_id].zone == Zone.EXILE
    assert state.adventure_permissions[card_id] == 1


def test_ai_retargets_beneficial_copy_clauses_to_itself() -> None:
    state, card_id, creature_id = meal_state()
    own_id = state.players[1].hand.pop(1)
    state.players[1].battlefield.append(own_id)
    state.cards[own_id].zone = Zone.BATTLEFIELD
    state = cast_meal(state, card_id, creature_id)
    copy_spell(state, 1, {"target_stack_id": state.stack[-1].id, "may_choose_new_targets": True})
    rules = RulesEngine()
    ai = AIAgent(difficulty="master", archetype="Midrange")

    first = ai.choose_action(state, rules.legal_moves(state, 1), 1).action
    assert first["card_ids"] == ["target_card_id:" + own_id]
    state = checked_action(state, rules, 1, first)
    second = ai.choose_action(state, rules.legal_moves(state, 1), 1).action
    assert second["card_ids"] == ["target_player:1"]
    state = checked_action(state, rules, 1, second)
    assert resolve_top_of_stack(state)
    assert state.players[1].life == 22
    assert state.cards[own_id].counters.get("+1/+1") == 1


def test_opponent_controls_copy_choices_but_not_original_adventure_permission() -> None:
    state, card_id, creature_id = meal_state()
    own_id = state.players[1].hand.pop(1)
    state.players[1].battlefield.append(own_id)
    state.cards[own_id].zone = Zone.BATTLEFIELD
    state = checked_action(state, RulesEngine(), 1, {
        "type": "cast_spell", "card_id": card_id, "selected_face_index": 1,
        "targets": {"target_card_id": own_id, "target_player": 1},
    })
    copy_spell(state, 2, {"target_stack_id": state.stack[-1].id, "may_choose_new_targets": True})
    assert state.pending_mechanic_choice["player_id"] == 2
    state = checked_action(state, RulesEngine(), 2, {
        "type": "choose_mechanic", "card_ids": ["target_card_id:" + creature_id],
    })
    state = checked_action(state, RulesEngine(), 2, {
        "type": "choose_mechanic", "card_ids": ["target_player:2"],
    })
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert resolve_top_of_stack(state)
    assert state.players[2].life == 22
    assert state.cards[creature_id].counters.get("+1/+1") == 1
    assert card_id not in state.adventure_permissions
    assert resolve_top_of_stack(state)
    assert state.players[1].life == 22
    assert state.cards[own_id].counters.get("+1/+1") == 1
    assert state.adventure_permissions[card_id] == 1
