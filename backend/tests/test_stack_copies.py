from __future__ import annotations

from effects.handlers import copy_ability, copy_spell, counter_ability, counter_spell
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, StackItem, Step, Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.targeting import stack_object_kind


def _state():
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=935)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.priority_player = 1
    return state


def _bolt(state):
    card = CardInstance(
        id="bolt", name="Lightning Bolt", owner=1, controller=1,
        zone=Zone.STACK, types=["Instant"], mana_cost="{R}",
        type_line="Instant", oracle_text="Lightning Bolt deals 3 damage to any target.",
    )
    state.cards[card.id] = card
    state.stack.append(StackItem(
        id="original", source_card_id=card.id, controller=1, label=card.name,
        effect_key="deal_damage", payload={"target_player": 2, "amount": 3,
            "__announced_targets": {"target_player": 2}},
    ))
    return card


def test_copied_spell_uses_stack_and_countering_copy_preserves_original() -> None:
    state = _state()
    original = _bolt(state)
    copy_spell(state, 1, {"target_stack_id": "original"})
    assert len(state.stack) == 2
    assert state.players[2].life == 20
    assert stack_object_kind(state, state.stack[-1]) == "spell"
    copy_id = state.stack[-1].id
    assert copy_id != "original"
    assert state.priority_player == 1 and not state.passed_priority
    counter_spell(state, 2, {"target_stack_id": copy_id})
    assert [item.id for item in state.stack] == ["original"]
    assert original.zone == Zone.STACK
    assert original.id not in state.players[1].graveyard
    assert resolve_top_of_stack(state)
    assert state.players[2].life == 17


def test_copy_survives_original_counter_and_snapshot() -> None:
    state = _state()
    original = _bolt(state)
    copy_spell(state, 2, {"target_stack_id": "original"})
    counter_spell(state, 2, {"target_stack_id": "original"})
    assert original.zone == Zone.GRAVEYARD
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert len(restored.stack) == 1
    assert stack_object_kind(restored, restored.stack[0]) == "spell"
    copy_spell(restored, 2, {"target_stack_id": restored.stack[0].id})
    assert len(restored.stack) == 2
    assert resolve_top_of_stack(restored)
    assert restored.players[2].life == 17
    assert resolve_top_of_stack(restored)
    assert restored.players[2].life == 14
    assert restored.players[1].graveyard.count(original.id) == 1


def test_copy_preserves_announced_modes_x_and_targets_across_snapshot() -> None:
    state = _state()
    _bolt(state)
    state.stack[0].payload.update({
        "x_value": 3,
        "__announced_targets": {"target_player": 2, "mode_texts": ["Deal 3 damage"]},
    })
    copy_spell(state, 1, {"target_stack_id": "original"})
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    copied = restored.stack[-1]
    assert copied.payload["x_value"] == 3
    assert copied.payload["__announced_targets"] == {
        "target_player": 2, "mode_texts": ["Deal 3 damage"],
    }


def test_memory_deluge_copy_has_zero_mana_spent_to_cast() -> None:
    state = _state()
    card = CardInstance(
        id="deluge", name="Memory Deluge", owner=1, controller=1,
        zone=Zone.STACK, types=["Instant"], mana_cost="{2}{U}{U}",
        oracle_text="Look at the top X cards of your library, where X is the amount of mana spent to cast this spell. "
                    "Put two of them into your hand and the rest on the bottom of your library in a random order.",
    )
    state.cards[card.id] = card
    state.stack.append(StackItem(
        id="deluge-original", source_card_id=card.id, controller=1,
        label=card.name, effect_key="look_top_select_hand",
        payload={"mana_spent_to_cast": 4, "hand_count": 2},
    ))
    copy_spell(state, 1, {"target_stack_id": "deluge-original"})
    assert state.stack[-1].payload["mana_spent_to_cast"] == 0
    hand_count = len(state.players[1].hand)
    assert resolve_top_of_stack(state)
    assert len(state.players[1].hand) == hand_count
    assert state.pending_mechanic_choice is None
    assert card.zone == Zone.STACK


def test_copied_ability_resolves_after_a_response_window() -> None:
    state = _state()
    source = CardInstance(
        id="ability-source", name="Soul Warden", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Creature"],
    )
    state.cards[source.id] = source
    state.players[1].battlefield.append(source.id)
    state.stack.append(StackItem(
        id="ability", source_card_id=source.id, controller=1, label="Soul Warden trigger",
        effect_key="gain_life", payload={"target_player": 1, "amount": 1, "__trigger_event": "enters_battlefield"},
    ))
    copy_ability(state, 1, {"target_stack_id": "ability"})
    assert len(state.stack) == 2 and state.players[1].life == 20
    assert stack_object_kind(state, state.stack[-1]) == "triggered"
    assert resolve_top_of_stack(state)
    assert state.players[1].life == 21
    assert resolve_top_of_stack(state)
    assert state.players[1].life == 22


def test_countering_copied_ability_preserves_source_and_original() -> None:
    state = _state()
    source = CardInstance(
        id="ability-source", name="Soul Warden", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Creature"],
    )
    state.cards[source.id] = source
    state.players[1].battlefield.append(source.id)
    state.stack.append(StackItem(
        id="ability", source_card_id=source.id, controller=1, label="Soul Warden trigger",
        effect_key="gain_life", payload={"target_player": 1, "amount": 1,
                                         "__trigger_event": "enters_battlefield"},
    ))
    copy_ability(state, 1, {"target_stack_id": "ability"})
    counter_ability(state, 2, {"target_stack_id": state.stack[-1].id, "target_kind": "triggered"})
    assert [item.id for item in state.stack] == ["ability"]
    assert source.zone == Zone.BATTLEFIELD
    assert resolve_top_of_stack(state)
    assert state.players[1].life == 21


def test_copy_effect_rejects_wrong_stack_object_kind() -> None:
    state = _state()
    source = CardInstance(
        id="ability-source", name="Soul Warden", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Creature"],
    )
    state.cards[source.id] = source
    state.stack.append(StackItem(
        id="ability", source_card_id=source.id, controller=1,
        label="Soul Warden trigger", effect_key="gain_life",
        payload={"amount": 1, "__trigger_event": "enters_battlefield"},
    ))
    copy_spell(state, 1, {"target_stack_id": "ability"})
    assert [item.id for item in state.stack] == ["ability"]
    assert not any("copies spell" in line for line in state.log)

    state = _state()
    _bolt(state)
    copy_ability(state, 1, {"target_stack_id": "original"})
    assert [item.id for item in state.stack] == ["original"]


def test_copied_spell_fizzles_when_its_only_target_becomes_illegal() -> None:
    state = _state()
    bolt = _bolt(state)
    target = CardInstance(
        id="target", name="Grizzly Bears", owner=2, controller=2,
        zone=Zone.BATTLEFIELD, types=["Creature"], type_line="Creature - Bear",
        power=2, toughness=2,
    )
    state.cards[target.id] = target
    state.players[2].battlefield.append(target.id)
    state.stack[0].payload = {"target_card_id": target.id, "amount": 3,
                              "__announced_targets": {"target_card_id": target.id}}
    copy_spell(state, 1, {"target_stack_id": "original"})
    state.players[2].battlefield.remove(target.id)
    state.players[2].graveyard.append(target.id)
    target.zone = Zone.GRAVEYARD
    assert resolve_top_of_stack(state)
    assert target.counters.get("__damage_marked", 0) == 0
    assert bolt.zone == Zone.STACK
    assert len(state.stack) == 1


def test_copied_permanent_spell_enters_as_token_without_moving_card() -> None:
    state = _state()
    card = CardInstance(
        id="bear", name="Grizzly Bears", owner=1, controller=1,
        zone=Zone.STACK, types=["Creature"], mana_cost="{1}{G}",
        type_line="Creature - Bear", power=2, toughness=2,
    )
    state.cards[card.id] = card
    state.stack.append(StackItem(
        id="bear-original", source_card_id=card.id, controller=1,
        label=card.name, effect_key="noop", payload={},
    ))
    copy_spell(state, 2, {"target_stack_id": "bear-original"})
    assert resolve_top_of_stack(state)
    tokens = [state.cards[cid] for cid in state.players[2].battlefield if state.cards[cid].is_token]
    assert len(tokens) == 1
    assert (tokens[0].name, tokens[0].power, tokens[0].toughness) == ("Grizzly Bears", 2, 2)
    assert card.zone == Zone.STACK and card.id not in state.players[2].battlefield
    assert resolve_top_of_stack(state)
    assert card.id in state.players[1].battlefield


def test_twincast_cast_resolves_copy_before_original_after_priority_passes() -> None:
    state = _state()
    state.step = Step.PRECOMBAT_MAIN
    state.players[1].mana_pool["U"] = 2
    _bolt(state)
    card = state.cards[state.players[1].hand[0]]
    card.name, card.types, card.type_line = "Twincast", ["Instant"], "Instant"
    card.mana_cost = "{U}{U}"
    card.oracle_text = "Copy target instant or sorcery spell. You may choose new targets for the copy."
    rules = RulesEngine()
    state = checked_action(state, rules, 1, {
        "type": "cast_spell", "card_id": card.id,
        "targets": {"target_stack_id": "original"},
    })
    assert len(state.stack) == 2
    rules.take_action(state, 1, {"type": "pass_priority"})
    rules.take_action(state, 2, {"type": "pass_priority"})
    assert state.stack[-1].payload["__stack_copy_kind"] == "spell"
    assert state.cards[card.id].zone == Zone.GRAVEYARD
    assert state.players[2].life == 20
    rules.take_action(state, 1, {"type": "pass_priority"})
    rules.take_action(state, 2, {"type": "pass_priority"})
    assert state.players[2].life == 17
    rules.take_action(state, 1, {"type": "pass_priority"})
    rules.take_action(state, 2, {"type": "pass_priority"})
    assert state.players[2].life == 14


def test_http_twincast_action_exposes_copy_on_stack_before_resolution() -> None:
    from fastapi.testclient import TestClient
    from main import ACTIVE_MATCHES, MatchController, app

    state = _state()
    state.step = Step.PRECOMBAT_MAIN
    state.players[1].mana_pool["U"] = 2
    _bolt(state)
    card = state.cards[state.players[1].hand[0]]
    card.name, card.types, card.type_line = "Twincast", ["Instant"], "Instant"
    card.mana_cost = "{U}{U}"
    card.oracle_text = "Copy target instant or sorcery spell. You may choose new targets for the copy."
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
            legal = client.get(f"/matches/{state.id}/legal-moves?player_id=1")
            assert legal.status_code == 200
            assert any(move.get("card_id") == card.id and move["type"] == "cast_spell"
                       for move in legal.json()["moves"])
            cast = client.post(f"/matches/{state.id}/action", json={
                "player_id": 1, "action": {"type": "cast_spell", "card_id": card.id,
                                          "targets": {"target_stack_id": "original"}},
            })
            assert cast.status_code == 200
            for player_id in (1, 2):
                response = client.post(f"/matches/{state.id}/action", json={
                    "player_id": player_id, "action": {"type": "pass_priority"},
                })
                assert response.status_code == 200
            body = response.json()
            assert len(body["stack"]) == 2
            assert body["stack"][-1]["label"] == "Lightning Bolt (copy)"
            assert body["players"]["2"]["life"] == 20
        finally:
            ACTIVE_MATCHES.pop(state.id, None)
