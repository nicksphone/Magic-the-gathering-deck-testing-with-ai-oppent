from __future__ import annotations

import pytest

from ai.agent import AIAgent
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, StackItem, Step, Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.zone_actions import put_into_graveyard


CRYPTIC_ORACLE = (
    "Choose two —\n"
    "• Counter target spell.\n"
    "• Return target permanent to its owner's hand.\n"
    "• Tap all creatures your opponents control.\n"
    "• Draw a card."
)


def _setup_counter_and_return():
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=17)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = 1
    state.step = Step.PRECOMBAT_MAIN
    state.players[1].mana_pool = {"U": 4}
    cryptic_id = state.players[1].hand[0]
    cryptic = state.cards[cryptic_id]
    cryptic.name = "Cryptic Command"
    cryptic.types = ["Instant"]
    cryptic.type_line = "Instant"
    cryptic.mana_cost = "{1}{U}{U}{U}"
    cryptic.oracle_text = CRYPTIC_ORACLE

    bolt_id = state.players[2].hand.pop()
    bolt = state.cards[bolt_id]
    bolt.name = "Lightning Bolt"
    bolt.types = ["Instant"]
    bolt.type_line = "Instant"
    bolt.zone = Zone.STACK
    state.stack.append(StackItem("bolt", bolt_id, 2, "Lightning Bolt", "deal_damage", {"target_player": 1, "amount": 3}))

    forest_id = state.players[2].hand.pop()
    forest = state.cards[forest_id]
    forest.name = "Forest"
    forest.types = ["Land"]
    forest.type_line = "Basic Land — Forest"
    forest.zone = Zone.BATTLEFIELD
    state.players[2].battlefield.append(forest_id)

    return state, cryptic_id, bolt_id, forest_id


def _cast_counter_and_return():
    state, cryptic_id, bolt_id, forest_id = _setup_counter_and_return()
    after = checked_action(state, RulesEngine(), 1, {
        "type": "cast_spell", "card_id": cryptic_id,
        "targets": {
            "mode_texts": ["Counter target spell", "Return target permanent to its owner's hand"],
            "target_stack_id": "bolt", "target_card_id": forest_id,
        },
    })
    return after, bolt_id, forest_id


def test_ai_materializes_both_target_classes_for_selected_modes() -> None:
    state, cryptic_id, _, forest_id = _setup_counter_and_return()
    own_land_id = state.players[1].hand.pop()
    state.cards[own_land_id].zone = Zone.BATTLEFIELD
    state.players[1].battlefield.append(own_land_id)
    move = next(move for move in RulesEngine().legal_moves(state, 1)
                if move.get("type") == "cast_spell" and move.get("card_id") == cryptic_id)
    move["targets"] = {"mode_texts": ["Counter target spell", "Return target permanent to its owner's hand"]}
    action = AIAgent(difficulty="master", archetype="Control")._materialize_action(state, move, 1)

    assert action["targets"]["mode_targets"] == {
        "Counter target spell": {"target_stack_id": "bolt"},
        "Return target permanent to its owner's hand": {"target_card_id": forest_id},
    }
    assert checked_action(state, RulesEngine(), 1, action).stack[-1].source_card_id == cryptic_id


def test_modal_copy_can_retarget_stack_mode_without_changing_permanent_mode() -> None:
    from effects.handlers import copy_spell

    state, cryptic_id, bolt_id, forest_id = _setup_counter_and_return()
    counter_mode = "Counter target spell"
    return_mode = "Return target permanent to its owner's hand"
    state = checked_action(state, RulesEngine(), 1, {
        "type": "cast_spell", "card_id": cryptic_id,
        "targets": {
            "mode_texts": [counter_mode, return_mode],
            "mode_targets": {
                counter_mode: {"target_stack_id": "bolt"},
                return_mode: {"target_card_id": forest_id},
            },
        },
    })
    original_id = state.stack[-1].id
    copy_spell(state, 1, {"target_stack_id": original_id, "may_choose_new_targets": True})
    pending = state.pending_mechanic_choice
    assert f"target_stack_id:{original_id}" in pending["options"]
    assert f"target_stack_id:{state.stack[-1].id}" not in pending["options"]
    state = checked_action(state, RulesEngine(), 1, {
        "type": "choose_mechanic", "card_ids": [f"target_stack_id:{original_id}"],
    })
    if state.pending_mechanic_choice:
        state = checked_action(state, RulesEngine(), 1, {
            "type": "choose_mechanic", "card_ids": ["keep"],
        })
    assert resolve_top_of_stack(state)
    assert not any(item.id == original_id for item in state.stack)
    assert any(item.id == "bolt" for item in state.stack)
    assert forest_id in state.players[2].hand
    assert state.cards[bolt_id].zone == Zone.STACK


def test_modal_copy_retargets_shared_announcements_as_independent_modes() -> None:
    from effects.handlers import copy_spell

    state, bolt_id, forest_id = _cast_counter_and_return()
    own_land_id = state.players[1].hand.pop()
    state.cards[own_land_id].zone = Zone.BATTLEFIELD
    state.players[1].battlefield.append(own_land_id)
    original = state.stack[-1]
    original_targets = dict(original.payload["__announced_targets"])
    copy_spell(state, 2, {"target_stack_id": original.id, "may_choose_new_targets": True})
    assert state.pending_mechanic_choice["mode_target_text"] == "Counter target spell"
    state = checked_action(state, RulesEngine(), 2, {
        "type": "choose_mechanic", "card_ids": [f"target_stack_id:{original.id}"],
    })
    assert state.pending_mechanic_choice["mode_target_text"] == "Return target permanent to its owner's hand"
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = checked_action(state, RulesEngine(), 2, {
        "type": "choose_mechanic", "card_ids": [f"target_card_id:{own_land_id}"],
    })
    assert state.stack[1].payload["__announced_targets"] == original_targets
    copied = state.stack[-1]
    assert copied.payload["__announced_targets"]["mode_targets"] == {
        "Counter target spell": {"target_stack_id": original.id},
        "Return target permanent to its owner's hand": {"target_card_id": own_land_id},
    }
    assert resolve_top_of_stack(state)
    assert not any(item.id == original.id for item in state.stack)
    assert own_land_id in state.players[1].hand
    assert forest_id in state.players[2].battlefield
    assert state.cards[bolt_id].zone == Zone.STACK


def test_ai_retargets_shared_modal_copy_away_from_its_own_side() -> None:
    from effects.handlers import copy_spell

    state, _, forest_id = _cast_counter_and_return()
    own_land_id = state.players[1].hand.pop()
    state.cards[own_land_id].zone = Zone.BATTLEFIELD
    state.players[1].battlefield.append(own_land_id)
    original_id = state.stack[-1].id
    copy_spell(state, 2, {"target_stack_id": original_id, "may_choose_new_targets": True})
    ai = AIAgent(difficulty="master", archetype="Control")
    rules = RulesEngine()
    decision = ai.choose_action(state, rules.legal_moves(state, 2), 2)
    assert decision.action == {"type": "choose_mechanic", "card_ids": [f"target_stack_id:{original_id}"]}
    state = checked_action(state, rules, 2, decision.action)
    decision = ai.choose_action(state, rules.legal_moves(state, 2), 2)
    assert decision.action == {"type": "choose_mechanic", "card_ids": [f"target_card_id:{own_land_id}"]}
    state = checked_action(state, rules, 2, decision.action)
    assert resolve_top_of_stack(state)
    assert own_land_id in state.players[1].hand
    assert forest_id in state.players[2].battlefield


def test_http_shared_modal_copy_exposes_both_choices() -> None:
    from fastapi.testclient import TestClient

    from effects.handlers import copy_spell
    from main import ACTIVE_MATCHES, MatchController, app

    state, _, _ = _cast_counter_and_return()
    own_land_id = state.players[1].hand.pop()
    state.cards[own_land_id].zone = Zone.BATTLEFIELD
    state.players[1].battlefield.append(own_land_id)
    original_id = state.stack[-1].id
    copy_spell(state, 2, {"target_stack_id": original_id, "may_choose_new_targets": True})
    deck = [{"quantity": 60, "card_name": "Island"}]
    match = MatchController(
        state=state, rules=RulesEngine(), controllers={1: "human", 2: "human"}, ai={},
        mode="human_vs_human", deck_ids=(None, None), mainboards={1: deck, 2: deck},
        sideboards={1: [], 2: []}, game_number=1, current_game_recorded=False,
        match_complete=False, best_of=3,
    )
    with TestClient(app) as client:
        ACTIVE_MATCHES[state.id] = match
        try:
            legal = client.get(f"/matches/{state.id}/legal-moves?player_id=2")
            assert legal.status_code == 200
            assert any(move.get("mode_target_text") == "Counter target spell" for move in legal.json()["moves"])
            first = client.post(f"/matches/{state.id}/action", json={
                "player_id": 2, "action": {"type": "choose_mechanic", "card_ids": [f"target_stack_id:{original_id}"]},
            })
            assert first.status_code == 200
            assert first.json()["pending_mechanic_choice"]["mode_target_text"] == "Return target permanent to its owner's hand"
            second = client.post(f"/matches/{state.id}/action", json={
                "player_id": 2, "action": {"type": "choose_mechanic", "card_ids": [f"target_card_id:{own_land_id}"]},
            })
            assert second.status_code == 200
            assert second.json()["pending_mechanic_choice"] is None
            assert second.json()["stack"][-1]["targets"] == [original_id, own_land_id]
        finally:
            ACTIVE_MATCHES.pop(state.id, None)


def test_restored_modal_spell_skips_permanent_that_gained_shroud() -> None:
    state, bolt_id, forest_id = _cast_counter_and_return()
    state.cards[forest_id].keywords.append("shroud")
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))

    assert resolve_top_of_stack(restored)
    assert not restored.stack
    assert bolt_id in restored.players[2].graveyard
    assert forest_id in restored.players[2].battlefield
    assert forest_id not in restored.players[2].hand


@pytest.mark.parametrize(
    ("remove_spell", "remove_permanent", "should_resolve"),
    [(False, False, True), (True, False, True), (False, True, True), (True, True, False)],
)
def test_cryptic_command_rechecks_each_independent_target(
    remove_spell: bool, remove_permanent: bool, should_resolve: bool,
) -> None:
    state, bolt_id, forest_id = _cast_counter_and_return()
    assert [effect["effect_key"] for effect in state.stack[-1].payload["effects"]] == [
        "counter_spell", "return_permanent_to_hand",
    ]
    if remove_spell:
        state.stack = [item for item in state.stack if item.id != "bolt"]
        put_into_graveyard(state, bolt_id)
    if remove_permanent:
        state.players[2].battlefield.remove(forest_id)
        put_into_graveyard(state, forest_id)

    assert resolve_top_of_stack(state)
    assert not state.stack
    assert bolt_id in state.players[2].graveyard
    if remove_permanent:
        assert forest_id in state.players[2].graveyard
    else:
        assert forest_id in state.players[2].hand
    assert ("Cryptic Command resolves." in state.log) is should_resolve
    assert not any("Lightning Bolt resolves." in line for line in state.log)
