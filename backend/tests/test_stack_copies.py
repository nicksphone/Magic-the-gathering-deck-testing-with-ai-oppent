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
    assert state.pending_mechanic_choice["kind"] == "copy_target"
    state = checked_action(state, rules, 1, {"type": "choose_mechanic", "card_ids": ["keep"]})
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
            assert body["pending_mechanic_choice"]["kind"] == "copy_target"
            response = client.post(f"/matches/{state.id}/action", json={
                "player_id": 1, "action": {"type": "choose_mechanic", "card_ids": ["target_player:1"]},
            })
            assert response.status_code == 200
            assert response.json()["stack"][-1]["targets"] == ["1"]
            assert response.json()["pending_mechanic_choice"] is None
        finally:
            ACTIVE_MATCHES.pop(state.id, None)


def test_copy_target_choice_retargets_only_copy_across_snapshot() -> None:
    state = _state()
    _bolt(state)
    copy_spell(state, 2, {"target_stack_id": "original", "may_choose_new_targets": True})
    assert state.pending_mechanic_choice["options"] == ["keep", "target_player:1"]
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    rules = RulesEngine()
    restored = checked_action(restored, rules, 2, {
        "type": "choose_mechanic", "card_ids": ["target_player:1"],
    })
    assert restored.pending_mechanic_choice is None
    assert restored.stack[-1].payload["__announced_targets"]["target_player"] == 1
    assert restored.stack[0].payload["target_player"] == 2
    assert resolve_top_of_stack(restored)
    assert (restored.players[1].life, restored.players[2].life) == (17, 20)
    assert resolve_top_of_stack(restored)
    assert (restored.players[1].life, restored.players[2].life) == (17, 17)


def test_ai_chooses_opponent_as_new_damage_target() -> None:
    from ai.agent import AIAgent

    state = _state()
    _bolt(state)
    copy_spell(state, 2, {"target_stack_id": "original", "may_choose_new_targets": True})
    ai = AIAgent(archetype="Burn")
    decision = ai.choose_action(state, RulesEngine().legal_moves(state, 2), 2)
    assert decision.action == {"type": "choose_mechanic", "card_ids": ["target_player:1"]}


def test_copy_target_choice_rejects_unoffered_target_without_mutation() -> None:
    import pytest

    state = _state()
    _bolt(state)
    copy_spell(state, 2, {"target_stack_id": "original", "may_choose_new_targets": True})
    before = serialize_match_snapshot(state)
    with pytest.raises(Exception):
        checked_action(state, RulesEngine(), 2, {
            "type": "choose_mechanic", "card_ids": ["target_player:99"],
        })
    assert serialize_match_snapshot(state) == before


def test_copy_without_target_does_not_pause_for_retargeting() -> None:
    state = _state()
    _bolt(state)
    state.stack[0].payload = {"amount": 3}
    copy_spell(state, 1, {"target_stack_id": "original", "may_choose_new_targets": True})
    assert state.pending_mechanic_choice is None


def test_counterspell_copy_cannot_target_itself() -> None:
    state = _state()
    _bolt(state)
    counter = CardInstance(
        id="counter", name="Counterspell", owner=2, controller=2,
        zone=Zone.STACK, types=["Instant"], mana_cost="{U}{U}",
        oracle_text="Counter target spell.",
    )
    state.cards[counter.id] = counter
    state.stack.append(StackItem(
        id="counter-original", source_card_id=counter.id, controller=2,
        label="Counterspell", effect_key="counter_spell",
        payload={"target_stack_id": "original", "__announced_targets": {"target_stack_id": "original"}},
    ))
    copy_spell(state, 2, {"target_stack_id": "counter-original", "may_choose_new_targets": True})
    assert state.stack[-1].id != "counter-original"
    assert state.pending_mechanic_choice["options"] == ["keep", "target_stack_id:counter-original"]
    assert f"target_stack_id:{state.stack[-1].id}" not in state.pending_mechanic_choice["options"]


def test_creature_spell_copy_offers_only_legal_new_creature_targets() -> None:
    state = _state()
    _bolt(state)
    spell = state.cards["bolt"]
    spell.name = "Murder"
    spell.oracle_text = "Destroy target creature."
    state.stack[0].label = "Murder"
    state.stack[0].effect_key = "destroy_permanent"
    for card_id, types in (("first", ["Creature"]), ("second", ["Creature"]), ("land", ["Land"])):
        card = CardInstance(id=card_id, name=card_id, owner=1, controller=1,
                            zone=Zone.BATTLEFIELD, types=types)
        state.cards[card_id] = card
        state.players[1].battlefield.append(card_id)
    state.stack[0].payload = {
        "target_card_id": "first", "__announced_targets": {"target_card_id": "first"},
    }
    copy_spell(state, 2, {"target_stack_id": "original", "may_choose_new_targets": True})
    assert state.pending_mechanic_choice["options"] == ["keep", "target_card_id:second"]
    state = checked_action(state, RulesEngine(), 2, {
        "type": "choose_mechanic", "card_ids": ["target_card_id:second"],
    })
    assert state.stack[-1].payload["target_card_id"] == "second"
    assert state.stack[0].payload["target_card_id"] == "first"


def test_activated_ability_copy_can_choose_a_new_target() -> None:
    state = _state()
    source = CardInstance(
        id="pyromancer", name="Prodigal Pyromancer", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Creature"],
        oracle_text="{T}: Prodigal Pyromancer deals 1 damage to any target.",
    )
    state.cards[source.id] = source
    state.players[1].battlefield.append(source.id)
    state.stack.append(StackItem(
        id="pyromancer-ability", source_card_id=source.id, controller=1,
        label="Prodigal Pyromancer ability", effect_key="deal_damage",
        payload={"target_player": 2, "amount": 1,
                 "__announced_targets": {"target_player": 2},
                 "__ability_target_text": source.oracle_text},
    ))
    copy_ability(state, 1, {"target_stack_id": "pyromancer-ability", "may_choose_new_targets": True})
    assert state.pending_mechanic_choice["options"][:2] == ["keep", "target_player:1"]
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    restored = checked_action(restored, RulesEngine(), 1, {
        "type": "choose_mechanic", "card_ids": ["target_player:1"],
    })
    assert restored.stack[-1].payload["target_player"] == 1
    assert restored.stack[0].payload["target_player"] == 2
    assert resolve_top_of_stack(restored)
    assert resolve_top_of_stack(restored)
    assert (restored.players[1].life, restored.players[2].life) == (19, 19)


def test_triggered_ability_copy_uses_trigger_clause_for_legal_targets() -> None:
    state = _state()
    clause = "When Goblin Arsonist dies, you may have it deal 1 damage to any target."
    source = CardInstance(
        id="arsonist", name="Goblin Arsonist", owner=1, controller=1,
        zone=Zone.GRAVEYARD, types=["Creature"], oracle_text=clause,
    )
    state.cards[source.id] = source
    state.players[1].graveyard.append(source.id)
    state.stack.append(StackItem(
        id="arsonist-trigger", source_card_id=source.id, controller=1,
        label="Goblin Arsonist trigger", effect_key="deal_damage",
        payload={"target_player": 2, "amount": 1,
                 "__trigger_event": "creature_dies", "__trigger_target_clause": clause,
                 "__trigger_target_choice": True},
    ))
    copy_ability(state, 1, {"target_stack_id": "arsonist-trigger", "may_choose_new_targets": True})
    assert "target_player:1" in state.pending_mechanic_choice["options"]
    state = checked_action(state, RulesEngine(), 1, {
        "type": "choose_mechanic", "card_ids": ["target_player:1"],
    })
    assert resolve_top_of_stack(state)
    assert resolve_top_of_stack(state)
    assert (state.players[1].life, state.players[2].life) == (19, 19)


def test_activated_ability_copy_fizzles_when_new_target_becomes_illegal() -> None:
    state = _state()
    source = CardInstance(
        id="pyromancer", name="Prodigal Pyromancer", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Creature"],
        oracle_text="{T}: Prodigal Pyromancer deals 1 damage to any target.",
    )
    target = CardInstance(
        id="bear", name="Grizzly Bears", owner=2, controller=2,
        zone=Zone.BATTLEFIELD, types=["Creature"], power=2, toughness=2,
    )
    state.cards[source.id] = source
    state.cards[target.id] = target
    state.players[1].battlefield.append(source.id)
    state.players[2].battlefield.append(target.id)
    state.stack.append(StackItem(
        id="ability", source_card_id=source.id, controller=1,
        label="Prodigal Pyromancer ability", effect_key="deal_damage",
        payload={"target_player": 2, "amount": 1,
                 "__announced_targets": {"target_player": 2},
                 "__ability_target_text": source.oracle_text},
    ))
    copy_ability(state, 1, {"target_stack_id": "ability", "may_choose_new_targets": True})
    assert "target_card_id:bear" in state.pending_mechanic_choice["options"]
    state = checked_action(state, RulesEngine(), 1, {
        "type": "choose_mechanic", "card_ids": ["target_card_id:bear"],
    })
    state.players[2].battlefield.remove(target.id)
    state.players[2].graveyard.append(target.id)
    target.zone = Zone.GRAVEYARD
    assert resolve_top_of_stack(state)
    assert target.counters.get("__damage_marked", 0) == 0
    assert state.players[2].life == 20
    assert resolve_top_of_stack(state)
    assert state.players[2].life == 19


def test_lithoform_activation_copies_targeted_ability_with_human_choice() -> None:
    state = _state()
    state.step = Step.PRECOMBAT_MAIN
    state.players[1].mana_pool["C"] = 2
    pyromancer = CardInstance(
        id="pyromancer", name="Prodigal Pyromancer", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Creature"], summoning_sick=False,
        oracle_text="{T}: Prodigal Pyromancer deals 1 damage to any target.",
    )
    engine = CardInstance(
        id="lithoform", name="Lithoform Engine", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Artifact"], summoning_sick=False,
        oracle_text="{2}, {T}: Copy target activated or triggered ability you control. You may choose new targets for the copy.",
    )
    for card in (pyromancer, engine):
        state.cards[card.id] = card
        state.players[1].battlefield.append(card.id)
    rules = RulesEngine()
    state = checked_action(state, rules, 1, {
        "type": "activate_ability", "card_id": pyromancer.id,
        "ability_index": 0, "targets": {"target_player": 2},
    })
    assert state.stack[-1].payload["__announced_targets"] == {"target_player": 2}
    assert state.stack[-1].payload["__ability_target_text"]
    original_id = state.stack[-1].id
    state = checked_action(state, rules, 1, {
        "type": "activate_ability", "card_id": engine.id,
        "ability_index": 0, "targets": {"target_stack_id": original_id},
    })
    rules.take_action(state, 1, {"type": "pass_priority"})
    rules.take_action(state, 2, {"type": "pass_priority"})
    assert state.pending_mechanic_choice["kind"] == "copy_target"
    state = checked_action(state, rules, 1, {
        "type": "choose_mechanic", "card_ids": ["target_player:1"],
    })
    assert len(state.stack) == 2
    assert state.stack[-1].payload["target_player"] == 1
    assert state.stack[0].payload["target_player"] == 2
    assert resolve_top_of_stack(state)
    assert resolve_top_of_stack(state)
    assert (state.players[1].life, state.players[2].life) == (19, 19)


def test_lithoform_cannot_copy_an_opponents_ability() -> None:
    import pytest

    state = _state()
    state.step = Step.PRECOMBAT_MAIN
    state.players[1].mana_pool["C"] = 2
    source = CardInstance(
        id="opponent-source", name="Prodigal Pyromancer", owner=2, controller=2,
        zone=Zone.BATTLEFIELD, types=["Creature"],
        oracle_text="{T}: Prodigal Pyromancer deals 1 damage to any target.",
    )
    engine = CardInstance(
        id="lithoform", name="Lithoform Engine", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Artifact"], summoning_sick=False,
        oracle_text="{2}, {T}: Copy target activated or triggered ability you control. You may choose new targets for the copy.",
    )
    for card in (source, engine):
        state.cards[card.id] = card
        state.players[card.controller].battlefield.append(card.id)
    state.stack.append(StackItem(
        id="opponent-ability", source_card_id=source.id, controller=2,
        label="Prodigal Pyromancer ability", effect_key="deal_damage",
        payload={"target_player": 1, "amount": 1},
    ))
    before = serialize_match_snapshot(state)
    with pytest.raises(Exception):
        checked_action(state, RulesEngine(), 1, {
            "type": "activate_ability", "card_id": engine.id,
            "ability_index": 0, "targets": {"target_stack_id": "opponent-ability"},
        })
    assert serialize_match_snapshot(state) == before


def test_lithoform_permanent_spell_copy_enters_as_token() -> None:
    import pytest

    state = _state()
    state.step = Step.PRECOMBAT_MAIN
    state.players[1].mana_pool["C"] = 4
    engine = CardInstance(
        id="lithoform", name="Lithoform Engine", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Artifact"], summoning_sick=False,
        oracle_text=(
            "{2}, {T}: Copy target activated or triggered ability you control. You may choose new targets for the copy.\n"
            "{3}, {T}: Copy target instant or sorcery spell you control. You may choose new targets for the copy.\n"
            "{4}, {T}: Copy target permanent spell you control. (The copy becomes a token.)"
        ),
    )
    state.cards[engine.id] = engine
    state.players[1].battlefield.append(engine.id)
    for cid, types in (("bear", ["Creature"]), ("bolt", ["Instant"])):
        card = CardInstance(
            id=cid, name="Grizzly Bears" if cid == "bear" else "Lightning Bolt",
            owner=1, controller=1, zone=Zone.STACK, types=types,
            mana_cost="{1}{G}" if cid == "bear" else "{R}",
            power=2 if cid == "bear" else None,
            toughness=2 if cid == "bear" else None,
        )
        state.cards[cid] = card
        state.stack.append(StackItem(
            id=f"{cid}-spell", source_card_id=cid, controller=1,
            label=card.name, effect_key="noop", payload={},
        ))
    rules = RulesEngine()
    before = serialize_match_snapshot(state)
    with pytest.raises(Exception):
        checked_action(state, rules, 1, {
            "type": "activate_ability", "card_id": engine.id,
            "ability_index": 2, "targets": {"target_stack_id": "bolt-spell"},
        })
    assert serialize_match_snapshot(state) == before
    state = checked_action(state, rules, 1, {
        "type": "activate_ability", "card_id": engine.id,
        "ability_index": 2, "targets": {"target_stack_id": "bear-spell"},
    })
    rules.take_action(state, 1, {"type": "pass_priority"})
    rules.take_action(state, 2, {"type": "pass_priority"})
    assert state.pending_mechanic_choice is None
    assert state.stack[-1].label == "Grizzly Bears (copy)"
    assert resolve_top_of_stack(state)
    tokens = [state.cards[cid] for cid in state.players[1].battlefield if state.cards[cid].is_token]
    assert len(tokens) == 1
    assert (tokens[0].name, tokens[0].power, tokens[0].toughness) == ("Grizzly Bears", 2, 2)
    assert state.cards["bear"].zone == Zone.STACK


def _pyrotechnics(state):
    spell = CardInstance(
        id="pyrotechnics", name="Pyrotechnics", owner=1, controller=1,
        zone=Zone.STACK, types=["Sorcery"], mana_cost="{4}{R}",
        oracle_text="Pyrotechnics deals 4 damage divided as you choose among any number of targets.",
    )
    target = CardInstance(
        id="bear", name="Grizzly Bears", owner=2, controller=2,
        zone=Zone.BATTLEFIELD, types=["Creature"], power=2, toughness=2,
    )
    state.cards[spell.id] = spell
    state.cards[target.id] = target
    state.players[2].battlefield.append(target.id)
    distribution = {"1": 1, "2": 3}
    state.stack.append(StackItem(
        id="pyrotechnics-original", source_card_id=spell.id, controller=1,
        label=spell.name, effect_key="deal_damage_multi",
        payload={"target_distribution": dict(distribution),
                 "__announced_targets": {"target_distribution": dict(distribution), "divide_total": 4}},
    ))


def test_divided_copy_retargets_slots_without_reallocating_damage() -> None:
    state = _state()
    _pyrotechnics(state)
    copy_spell(state, 1, {"target_stack_id": "pyrotechnics-original", "may_choose_new_targets": True})
    pending = state.pending_mechanic_choice
    assert pending["kind"] == "copy_target" and pending["target_slot_number"] == 1
    assert "target_card_id:bear" in pending["options"]
    assert "target_player:2" not in pending["options"]
    rules = RulesEngine()
    state = checked_action(state, rules, 1, {
        "type": "choose_mechanic", "card_ids": ["target_card_id:bear"],
    })
    assert state.pending_mechanic_choice["target_slot_number"] == 2
    assert state.stack[-1].payload["target_distribution"] == {"bear": 1, "2": 3}
    assert state.stack[0].payload["target_distribution"] == {"1": 1, "2": 3}
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    restored = checked_action(restored, rules, 1, {
        "type": "choose_mechanic", "card_ids": ["keep"],
    })
    assert restored.pending_mechanic_choice is None
    assert resolve_top_of_stack(restored)
    assert restored.cards["bear"].counters.get("__damage_marked") == 1
    assert (restored.players[1].life, restored.players[2].life) == (20, 17)
    assert resolve_top_of_stack(restored)
    assert (restored.players[1].life, restored.players[2].life) == (19, 14)


def test_divided_copy_may_keep_an_illegal_original_target() -> None:
    state = _state()
    _pyrotechnics(state)
    target = state.cards["bear"]
    state.stack[0].payload["target_distribution"] = {"bear": 1, "2": 3}
    state.stack[0].payload["__announced_targets"]["target_distribution"] = {"bear": 1, "2": 3}
    state.players[2].battlefield.remove(target.id)
    state.players[2].graveyard.append(target.id)
    target.zone = Zone.GRAVEYARD
    copy_spell(state, 1, {"target_stack_id": "pyrotechnics-original", "may_choose_new_targets": True})
    assert state.pending_mechanic_choice["distribution_target"] == "bear"
    state = checked_action(state, RulesEngine(), 1, {
        "type": "choose_mechanic", "card_ids": ["keep"],
    })
    assert state.stack[-1].payload["target_distribution"]["bear"] == 1
    if state.pending_mechanic_choice:
        state = checked_action(state, RulesEngine(), 1, {
            "type": "choose_mechanic", "card_ids": ["keep"],
        })
    assert resolve_top_of_stack(state)
    assert target.counters.get("__damage_marked", 0) == 0
    assert state.players[2].life == 17


def test_ai_redirects_divided_copy_damage_to_opponent() -> None:
    from ai.agent import AIAgent

    state = _state()
    _pyrotechnics(state)
    distribution = {"1": 1, "bear": 3}
    state.stack[0].payload["target_distribution"] = dict(distribution)
    state.stack[0].payload["__announced_targets"]["target_distribution"] = dict(distribution)
    copy_spell(state, 1, {"target_stack_id": "pyrotechnics-original", "may_choose_new_targets": True})
    decision = AIAgent(archetype="Burn").choose_action(state, RulesEngine().legal_moves(state, 1), 1)
    assert decision.action == {"type": "choose_mechanic", "card_ids": ["target_player:2"]}


def test_twincast_divided_copy_finishes_only_after_all_target_choices() -> None:
    state = _state()
    state.step = Step.PRECOMBAT_MAIN
    state.players[1].mana_pool["U"] = 2
    _pyrotechnics(state)
    twincast = state.cards[state.players[1].hand[0]]
    twincast.name, twincast.types, twincast.type_line = "Twincast", ["Instant"], "Instant"
    twincast.mana_cost = "{U}{U}"
    twincast.oracle_text = "Copy target instant or sorcery spell. You may choose new targets for the copy."
    rules = RulesEngine()
    state = checked_action(state, rules, 1, {
        "type": "cast_spell", "card_id": twincast.id,
        "targets": {"target_stack_id": "pyrotechnics-original"},
    })
    rules.take_action(state, 1, {"type": "pass_priority"})
    rules.take_action(state, 2, {"type": "pass_priority"})
    assert state.pending_mechanic_choice["target_slot_number"] == 1
    assert state.cards[twincast.id].zone == Zone.STACK
    state = checked_action(state, rules, 1, {
        "type": "choose_mechanic", "card_ids": ["target_card_id:bear"],
    })
    assert state.pending_mechanic_choice["target_slot_number"] == 2
    assert state.cards[twincast.id].zone == Zone.STACK
    state = checked_action(state, rules, 1, {
        "type": "choose_mechanic", "card_ids": ["keep"],
    })
    assert state.pending_mechanic_choice is None
    assert state.cards[twincast.id].zone == Zone.GRAVEYARD
    assert len(state.stack) == 2
    assert state.players[2].life == 20


def test_divided_copy_does_not_offer_newly_hexproof_target() -> None:
    state = _state()
    _pyrotechnics(state)
    state.cards["bear"].keywords.append("hexproof")
    copy_spell(state, 1, {"target_stack_id": "pyrotechnics-original", "may_choose_new_targets": True})
    assert state.pending_mechanic_choice is None
    assert state.stack[-1].payload["target_distribution"] == {"1": 1, "2": 3}
