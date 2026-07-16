from __future__ import annotations

from game_state.state import CardInstance, MatchFactory, Zone
from effects.registry import resolve_effect
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.oracle_effects import infer_effect_from_oracle
from rules_engine.oracle_effects import inspect_target_hints


def test_oracle_damage_parsing() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    card = CardInstance(
        id="x",
        name="Lightning Bolt",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Instant"],
        oracle_text="Lightning Bolt deals 3 damage to any target.",
    )
    effect_key, payload = infer_effect_from_oracle(state, card, 1)
    assert effect_key == "deal_damage"
    assert payload["amount"] == 3


def test_oracle_counterspell_parsing() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.stack.append(type("SI", (), {"id": "stack-1"})())
    card = CardInstance(
        id="c",
        name="Counterspell",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Instant"],
        oracle_text="Counter target spell.",
    )
    effect_key, payload = infer_effect_from_oracle(state, card, 1)
    assert effect_key == "counter_spell"
    assert payload["target_stack_id"] == "stack-1"


def test_oracle_copy_spell_parsing() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.stack.append(type("SI", (), {"id": "stack-copy"})())
    card = CardInstance(
        id="copy",
        name="Spell Swindle",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Instant"],
        oracle_text="Copy target spell.",
    )
    effect_key, payload = infer_effect_from_oracle(state, card, 1)
    assert effect_key == "copy_spell"
    assert payload["target_stack_id"] == "stack-copy"


def test_oracle_copy_ability_parsing() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.stack.append(type("SI", (), {"id": "stack-ability"})())
    card = CardInstance(
        id="copy-ability",
        name="Rings of Brighthearth",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Artifact"],
        oracle_text="Copy target activated ability you control.",
    )
    effect_key, payload = infer_effect_from_oracle(state, card, 1)
    assert effect_key == "copy_ability"
    assert payload["target_stack_id"] == "stack-ability"
    assert payload["copy_kind"] == "activated ability"


def test_oracle_counter_ability_parsing() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.stack.append(type("SI", (), {"id": "stack-ability"})())
    card = CardInstance(
        id="counter-ability",
        name="Stifle",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Instant"],
        oracle_text="Counter target activated ability.",
    )
    effect_key, payload = infer_effect_from_oracle(state, card, 1)
    assert effect_key == "counter_ability"
    assert payload["target_stack_id"] == "stack-ability"


def test_oracle_target_hints_include_artifact_and_enchantment_targets() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    card = CardInstance(
        id="rem",
        name="Disenchant",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Instant"],
        oracle_text="Destroy target artifact or enchantment.",
    )
    state.cards["artifact"] = CardInstance(
        id="artifact",
        name="Lockstone",
        owner=2,
        controller=2,
        zone=Zone.BATTLEFIELD,
        types=["Artifact"],
    )
    state.cards["enchantment"] = CardInstance(
        id="enchantment",
        name="Curse",
        owner=2,
        controller=2,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
    )
    state.players[2].battlefield.extend(["artifact", "enchantment"])

    hints = inspect_target_hints(state, card, 1)

    assert {entry["id"] for entry in hints.get("artifact_targets", [])} == {"artifact"}
    assert {entry["id"] for entry in hints.get("enchantment_targets", [])} == {"enchantment"}
    assert {entry["id"] for entry in hints.get("noncreature_permanent_targets", [])} == {"artifact", "enchantment"}


def test_oracle_target_hints_include_nonland_permanent_targets() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    card = CardInstance(
        id="rem",
        name="Vindicate",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Sorcery"],
        oracle_text="Destroy target nonland permanent.",
    )
    state.cards["artifact"] = CardInstance(
        id="artifact",
        name="Lockstone",
        owner=2,
        controller=2,
        zone=Zone.BATTLEFIELD,
        types=["Artifact"],
    )
    state.cards["enchantment"] = CardInstance(
        id="enchantment",
        name="Curse",
        owner=2,
        controller=2,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
    )
    state.cards["land"] = CardInstance(
        id="land",
        name="Island",
        owner=2,
        controller=2,
        zone=Zone.BATTLEFIELD,
        types=["Land"],
    )
    state.players[2].battlefield.extend(["artifact", "enchantment", "land"])

    hints = inspect_target_hints(state, card, 1)

    assert {entry["id"] for entry in hints.get("permanent_targets", [])} == {"artifact", "enchantment"}


def test_nonland_permanent_removal_chooses_nonland_target() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    card = CardInstance(
        id="rem",
        name="Vindicate",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Sorcery"],
        oracle_text="Destroy target nonland permanent.",
    )
    state.cards["artifact"] = CardInstance(
        id="artifact",
        name="Lockstone",
        owner=2,
        controller=2,
        zone=Zone.BATTLEFIELD,
        types=["Artifact"],
    )
    state.cards["land"] = CardInstance(
        id="land",
        name="Island",
        owner=2,
        controller=2,
        zone=Zone.BATTLEFIELD,
        types=["Land"],
    )
    state.players[2].battlefield.extend(["artifact", "land"])

    effect_key, payload = infer_effect_from_oracle(state, card, 1)

    assert effect_key == "destroy_permanent"
    assert payload["target_card_id"] == "artifact"


def test_split_card_marks_split_hints() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    card = CardInstance(
        id="split",
        name="Fire // Ice",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Instant"],
        oracle_text="Choose one — Fire deals 2 damage divided as you choose among one or two targets; Ice taps target permanent and draws a card.",
    )
    hints = inspect_target_hints(state, card, 1)
    assert hints.get("split_card") is True
    assert hints.get("face_names") == ["Fire", "Ice"]
    assert hints.get("modes")


def test_selected_modal_face_drives_oracle_inference() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    card = CardInstance(
        id="modal",
        name="Modal Adept",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Creature"],
        mana_cost="{2}{G}",
        oracle_text="",
        card_faces=[
            {"name": "Adept Form", "oracle_text": "Create a 1/1 token.", "mana_cost": "{2}{G}", "type_line": "Creature - Elf"},
            {"name": "Scholar Form", "oracle_text": "Create two 1/1 tokens.", "mana_cost": "{2}{G}", "type_line": "Creature - Elf"},
        ],
    )
    effect_key, payload = infer_effect_from_oracle(state, card, 1, action_targets={"selected_face_index": 1})
    assert effect_key == "create_token"
    assert payload["amount"] == 2


def test_copy_spell_handler_replays_target_effect() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.players[1].life = 10
    state.players[2].life = 10
    state.stack.append(type("SI", (), {"id": "stack-dmg", "label": "Lightning Bolt", "source_card_id": "bolt-1", "effect_key": "deal_damage", "payload": {"target_player": 2, "amount": 3}})())
    state.cards["bolt-1"] = CardInstance(
        id="bolt-1",
        name="Lightning Bolt",
        owner=1,
        controller=1,
        zone=Zone.STACK,
        types=["Instant"],
        oracle_text="Lightning Bolt deals 3 damage to any target.",
    )
    resolve_effect(state, 1, "copy_spell", {"target_stack_id": "stack-dmg"})
    assert state.players[2].life == 7


def test_copy_ability_handler_replays_target_ability() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.players[1].life = 10
    state.stack.append(
        type(
            "SI",
            (),
            {
                "id": "stack-ability",
                "label": "Soul Warden trigger",
                "source_card_id": "warden-1",
                "effect_key": "gain_life",
                "payload": {"target_player": 1, "amount": 1},
                "targets": ["player:1"],
            },
        )()
    )
    state.cards["warden-1"] = CardInstance(
        id="warden-1",
        name="Soul Warden",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Creature"],
        oracle_text="Whenever another creature enters the battlefield, you gain 1 life.",
    )
    resolve_effect(state, 1, "copy_ability", {"target_stack_id": "stack-ability"})
    assert state.players[1].life == 11


def test_counter_ability_handler_removes_stack_item() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.stack.append(type("SI", (), {"id": "stack-ability", "label": "Soul Warden trigger", "source_card_id": "warden-1", "effect_key": "gain_life", "payload": {"target_player": 1, "amount": 1}})())
    state.cards["warden-1"] = CardInstance(
        id="warden-1",
        name="Soul Warden",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Creature"],
        oracle_text="Whenever another creature enters the battlefield, you gain 1 life.",
    )
    resolve_effect(state, 1, "counter_ability", {"target_stack_id": "stack-ability"})
    assert state.stack == []


def test_oracle_reanimate_parsing_and_resolution() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    p1 = state.players[1]
    creature = CardInstance(
        id="reanimate-me",
        name="Mulldrifter",
        owner=1,
        controller=1,
        zone=Zone.GRAVEYARD,
        types=["Creature"],
        oracle_text="",
        power=2,
        toughness=2,
    )
    state.cards[creature.id] = creature
    p1.graveyard.append(creature.id)
    card = CardInstance(
        id="reanimate-spell",
        name="Reanimate",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Sorcery"],
        oracle_text="Return target creature card from your graveyard to the battlefield.",
    )
    hints = inspect_target_hints(state, card, 1)
    assert creature.id in {entry["id"] for entry in hints.get("graveyard_creature_targets", [])}
    effect_key, payload = infer_effect_from_oracle(state, card, 1, action_targets={"target_card_id": creature.id})
    assert effect_key == "return_creature_from_graveyard_to_battlefield"
    assert payload["target_card_id"] == creature.id
    resolve_effect(state, 1, effect_key, payload)
    assert creature.id in p1.battlefield


def test_oracle_any_color_mana_choice_uses_hand_needs() -> None:
    deck = [
        {"quantity": 1, "card_name": "Counterspell"},
        {"quantity": 1, "card_name": "Lightning Bolt"},
        {"quantity": 58, "card_name": "Island"},
    ]
    state = MatchFactory.from_decks(deck, deck)
    card = CardInstance(
        id="cobra",
        name="Lotus Cobra",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Creature"],
        oracle_text="Whenever a land enters the battlefield under your control, add one mana of any color.",
    )
    effect_key, payload = infer_effect_from_oracle(state, card, 1)
    assert effect_key == "add_mana"
    assert payload["amount"] == 1
    assert payload["color"] == "U"
    resolve_effect(state, 1, effect_key, payload)
    assert state.players[1].mana_pool["U"] == 1


def test_oracle_reanimate_can_target_opponent_graveyard() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    p2 = state.players[2]
    creature = CardInstance(
        id="enemy-reanimate-me",
        name="Mulldrifter",
        owner=2,
        controller=2,
        zone=Zone.GRAVEYARD,
        types=["Creature"],
        oracle_text="",
        power=2,
        toughness=2,
    )
    state.cards[creature.id] = creature
    p2.graveyard.append(creature.id)
    card = CardInstance(
        id="reanimate-spell-2",
        name="Reanimate",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Sorcery"],
        oracle_text="Return target creature card from a graveyard to the battlefield under your control.",
    )
    hints = inspect_target_hints(state, card, 1)
    assert creature.id in {entry["id"] for entry in hints.get("graveyard_creature_targets", [])}
    effect_key, payload = infer_effect_from_oracle(state, card, 1, action_targets={"target_card_id": creature.id})
    assert effect_key == "return_creature_from_graveyard_to_battlefield"
    resolve_effect(state, 1, effect_key, payload)
    assert creature.id in state.players[1].battlefield
    assert creature.id not in p2.graveyard
    assert state.cards[creature.id].controller == 1
    assert state.cards[creature.id].owner == 2


def test_oracle_can_return_graveyard_artifact_or_enchantment() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    p2 = state.players[2]
    artifact = CardInstance(
        id="enemy-artifact",
        name="Lockstone",
        owner=2,
        controller=2,
        zone=Zone.GRAVEYARD,
        types=["Artifact"],
        oracle_text="",
    )
    enchantment = CardInstance(
        id="enemy-enchantment",
        name="Curse",
        owner=2,
        controller=2,
        zone=Zone.GRAVEYARD,
        types=["Enchantment"],
        oracle_text="",
    )
    state.cards[artifact.id] = artifact
    state.cards[enchantment.id] = enchantment
    p2.graveyard.extend([artifact.id, enchantment.id])
    card = CardInstance(
        id="vaults",
        name="Open the Vaults",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Sorcery"],
        oracle_text="Return target artifact or enchantment card from a graveyard to the battlefield.",
    )

    hints = inspect_target_hints(state, card, 1)
    assert {entry["id"] for entry in hints.get("graveyard_permanent_targets", [])} == {"enemy-artifact", "enemy-enchantment"}
    effect_key, payload = infer_effect_from_oracle(state, card, 1, action_targets={"target_card_id": artifact.id})
    assert effect_key == "return_permanent_from_graveyard_to_battlefield"
    resolve_effect(state, 1, effect_key, payload)
    assert artifact.id in state.players[1].battlefield
    assert artifact.id not in p2.graveyard
    assert state.cards[artifact.id].controller == 1


def test_oracle_can_return_generic_permanent_from_graveyard() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    p2 = state.players[2]
    land = CardInstance(
        id="enemy-land",
        name="Tropical Island",
        owner=2,
        controller=2,
        zone=Zone.GRAVEYARD,
        types=["Land"],
        oracle_text="{T}: Add {G} or {U}.",
    )
    state.cards[land.id] = land
    p2.graveyard.append(land.id)
    card = CardInstance(
        id="revival",
        name="Revival of the Lost",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Sorcery"],
        oracle_text="Return target permanent card from a graveyard to the battlefield under your control.",
    )

    hints = inspect_target_hints(state, card, 1)
    assert {entry["id"] for entry in hints.get("graveyard_permanent_targets", [])} == {"enemy-land"}
    effect_key, payload = infer_effect_from_oracle(state, card, 1, action_targets={"target_card_id": land.id})
    assert effect_key == "return_permanent_from_graveyard_to_battlefield"
    resolve_effect(state, 1, effect_key, payload)
    assert land.id in state.players[1].battlefield
    assert land.id not in p2.graveyard
    assert state.cards[land.id].controller == 1


def test_oracle_search_library_for_artifact_card_uses_type_based_filtering() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    artifact_id = "artifact-library"
    artifact = CardInstance(
        id=artifact_id,
        name="Sol Ring",
        owner=1,
        controller=1,
        zone=Zone.LIBRARY,
        types=["Artifact"],
        oracle_text="",
    )
    state.cards[artifact.id] = artifact
    state.players[1].library.append(artifact.id)
    card = CardInstance(
        id="tutor",
        name="Fabricate",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Sorcery"],
        oracle_text="Search your library for an artifact card, reveal it, put it into your hand, then shuffle.",
    )

    effect_key, payload = infer_effect_from_oracle(state, card, 1)
    assert effect_key == "search_library"
    assert payload["contains"] == "artifact"
    resolve_effect(state, 1, effect_key, payload)
    assert artifact.id in state.players[1].hand
    assert artifact.id not in state.players[1].library


def test_oracle_search_library_can_put_creature_onto_battlefield() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    creature_id = "creature-library"
    creature = CardInstance(
        id=creature_id,
        name="Elvish Mystic",
        owner=1,
        controller=1,
        zone=Zone.LIBRARY,
        types=["Creature"],
        oracle_text="",
    )
    state.cards[creature.id] = creature
    state.players[1].library.append(creature.id)
    card = CardInstance(
        id="tutor-battlefield",
        name="Collected Company",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Instant"],
        oracle_text="Search your library for up to two creature cards with mana value 3 or less, put them onto the battlefield, then shuffle your library.",
    )

    effect_key, payload = infer_effect_from_oracle(state, card, 1, action_targets={"search_contains": "creature"})
    assert effect_key == "search_library"
    assert payload["destination"] == "battlefield"
    resolve_effect(state, 1, effect_key, payload)
    assert creature.id in state.players[1].battlefield
    assert creature.id not in state.players[1].library


def test_oracle_search_library_honors_count_and_mana_value_on_battlefield_tutors() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    player = state.players[1]
    player.library = []

    low_a = CardInstance(id="low-a", name="Llanowar Elves", owner=1, controller=1, zone=Zone.LIBRARY, types=["Creature"], mana_cost="{G}")
    low_b = CardInstance(id="low-b", name="Elvish Mystic", owner=1, controller=1, zone=Zone.LIBRARY, types=["Creature"], mana_cost="{G}")
    high = CardInstance(id="high", name="Steel Hellkite", owner=1, controller=1, zone=Zone.LIBRARY, types=["Creature"], mana_cost="{6}")
    state.cards[low_a.id] = low_a
    state.cards[low_b.id] = low_b
    state.cards[high.id] = high
    player.library.extend([low_a.id, high.id, low_b.id])

    card = CardInstance(
        id="tutor-battlefield",
        name="Natural Order Variant",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Sorcery"],
        oracle_text="Search your library for up to two creature cards with mana value 1 or less, put them onto the battlefield, then shuffle.",
    )

    effect_key, payload = infer_effect_from_oracle(state, card, 1)
    assert effect_key == "search_library"
    assert payload["destination"] == "battlefield"
    assert payload["count"] == 2
    assert payload["mv_max"] == 1

    resolve_effect(state, 1, effect_key, payload)
    assert low_a.id in player.battlefield
    assert low_b.id in player.battlefield
    assert high.id in player.library
    assert low_a.id not in player.library
    assert low_b.id not in player.library


def test_unknown_oracle_text_falls_back_to_noop() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    card = CardInstance(
        id="mystery",
        name="Mystery Permanent",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Enchantment"],
        oracle_text="At the beginning of your turn, do a thing the engine does not know.",
    )
    effect_key, payload = infer_effect_from_oracle(state, card, 1)
    assert effect_key == "noop"
    assert payload == {}
    assert any("oracle effect not inferred" in line.lower() for line in state.log)




def test_oracle_multiclause_sequence_parsing() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    card = CardInstance(
        id="m",
        name="Cruel Insight",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Sorcery"],
        oracle_text="Target player loses 2 life. You gain 2 life. Draw a card.",
    )
    effect_key, payload = infer_effect_from_oracle(state, card, 1, action_targets={"target_player": 2})
    assert effect_key == "effect_sequence"
    effects = payload["effects"]
    assert [x["effect_key"] for x in effects] == ["lose_life", "gain_life", "draw_cards"]
    assert effects[0]["payload"]["target_player"] == 2
    assert effects[0]["payload"]["amount"] == 2
    assert effects[1]["payload"]["amount"] == 2


def test_oracle_add_counters_parsing() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    target = state.players[1].battlefield[0] if state.players[1].battlefield else state.players[1].hand[0]
    card = CardInstance(
        id="counters",
        name="Growth Pattern",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Sorcery"],
        oracle_text="Put two +1/+1 counters on target creature.",
    )
    effect_key, payload = infer_effect_from_oracle(state, card, 1, action_targets={"target_card_id": target})
    assert effect_key == "add_counters"
    assert payload["target_card_id"] == target
    assert payload["amount"] == 2


def test_oracle_token_count_and_keywords_parsing() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    card = CardInstance(
        id="tok",
        name="Raise Patrol",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Sorcery"],
        oracle_text="Create two 1/1 white Soldier creature tokens with vigilance.",
    )
    effect_key, payload = infer_effect_from_oracle(state, card, 1)
    assert effect_key == "create_token"
    assert payload["amount"] == 2
    assert payload["power"] == 1
    assert payload["toughness"] == 1
    assert payload["name"] == "White Soldier"
    assert "vigilance" in payload["keywords"]


def test_oracle_destroy_all_creatures_resolution_wipes_board() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    p1 = state.players[1]
    p2 = state.players[2]
    creature_a = CardInstance(
        id="crea",
        name="Runeclaw Bear",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Creature"],
        oracle_text="",
        power=2,
        toughness=2,
    )
    creature_b = CardInstance(
        id="creb",
        name="Elvish Mystic",
        owner=2,
        controller=2,
        zone=Zone.BATTLEFIELD,
        types=["Creature"],
        oracle_text="",
        power=1,
        toughness=1,
    )
    state.cards[creature_a.id] = creature_a
    state.cards[creature_b.id] = creature_b
    p1.battlefield.append(creature_a.id)
    p2.battlefield.append(creature_b.id)

    resolve_effect(state, 1, "destroy_all_creatures", {})

    assert creature_a.id in p1.graveyard
    assert creature_b.id in p2.graveyard
    assert creature_a.zone == Zone.GRAVEYARD
    assert creature_b.zone == Zone.GRAVEYARD


def test_oracle_destroy_target_artifact_or_enchantment_prefers_matching_permanent() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    p2 = state.players[2]
    artifact = CardInstance(
        id="art",
        name="Mystic Forge",
        owner=2,
        controller=2,
        zone=Zone.BATTLEFIELD,
        types=["Artifact"],
        oracle_text="",
    )
    enchantment = CardInstance(
        id="ench",
        name="Rest in Peace",
        owner=2,
        controller=2,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="",
    )
    state.cards[artifact.id] = artifact
    state.cards[enchantment.id] = enchantment
    p2.battlefield.extend([artifact.id, enchantment.id])

    card = CardInstance(
        id="remove",
        name="Disenchant",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Instant"],
        oracle_text="Destroy target artifact or enchantment.",
    )
    effect_key, payload = infer_effect_from_oracle(state, card, 1)
    assert effect_key == "destroy_permanent"
    assert payload["target_card_id"] in {artifact.id, enchantment.id}


def test_oracle_destroy_all_artifacts_and_enchantments_wipes_both_types() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    p1 = state.players[1]
    p2 = state.players[2]
    artifact = CardInstance(
        id="art",
        name="Sol Ring",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Artifact"],
        oracle_text="",
    )
    enchantment = CardInstance(
        id="ench",
        name="Oath of Nissa",
        owner=2,
        controller=2,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="",
    )
    state.cards[artifact.id] = artifact
    state.cards[enchantment.id] = enchantment
    p1.battlefield.append(artifact.id)
    p2.battlefield.append(enchantment.id)

    resolve_effect(state, 1, "destroy_all_artifacts_and_enchantments", {})

    assert artifact.id in p1.graveyard
    assert enchantment.id in p2.graveyard


def test_oracle_mass_artifact_and_enchantment_removal_is_inferred() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    card = CardInstance(
        id="wipe",
        name="Bane of Progress",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Creature"],
        oracle_text="Destroy all artifacts and enchantments.",
    )
    effect_key, payload = infer_effect_from_oracle(state, card, 1)
    assert effect_key == "destroy_all_artifacts_and_enchantments"
    assert payload == {}


def test_oracle_collected_company_style_parsing() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    card = CardInstance(
        id="cc",
        name="Collected Company",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Instant"],
        mana_cost="{3}{G}",
        oracle_text=(
            "Look at the top six cards of your library. "
            "Put up to two creature cards with mana value 3 or less from among them onto the battlefield. "
            "Put the rest on the bottom of your library in any order."
        ),
    )
    effect_key, payload = infer_effect_from_oracle(state, card, 1)
    assert effect_key == "topdeck_put_creatures_battlefield"
    assert payload["top_n"] == 6
    assert payload["max_creatures"] == 2
    assert payload["mv_max"] == 3


def test_oracle_prevent_next_damage_parsing() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    target = state.players[1].hand[0]
    card = CardInstance(
        id="foglet",
        name="Protective Burst",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Instant"],
        oracle_text="Prevent the next 3 damage that would be dealt to target creature this turn.",
    )
    effect_key, payload = infer_effect_from_oracle(state, card, 1, action_targets={"target_card_id": target})
    assert effect_key == "prevent_damage"
    assert payload["amount"] == 3
    assert payload["target_card_id"] == target


def test_topdeck_creature_deploy_effect_puts_eligible_creatures_onto_battlefield() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    p1 = state.players[1]
    p1.battlefield = []
    p1.library = p1.library + p1.hand
    p1.hand = []

    top6 = p1.library[-6:]
    # Build top six: two eligible creatures (<=3 MV), one too expensive creature, three noncreatures.
    state.cards[top6[0]].name = "Spell A"
    state.cards[top6[0]].types = ["Instant"]
    state.cards[top6[0]].mana_cost = "{1}{U}"

    state.cards[top6[1]].name = "Elf 2"
    state.cards[top6[1]].types = ["Creature"]
    state.cards[top6[1]].mana_cost = "{1}{G}"

    state.cards[top6[2]].name = "Big 5"
    state.cards[top6[2]].types = ["Creature"]
    state.cards[top6[2]].mana_cost = "{3}{G}{G}"

    state.cards[top6[3]].name = "Elf 3"
    state.cards[top6[3]].types = ["Creature"]
    state.cards[top6[3]].mana_cost = "{2}{G}"

    state.cards[top6[4]].name = "Spell B"
    state.cards[top6[4]].types = ["Sorcery"]
    state.cards[top6[4]].mana_cost = "{2}{G}"

    state.cards[top6[5]].name = "Spell C"
    state.cards[top6[5]].types = ["Instant"]
    state.cards[top6[5]].mana_cost = "{1}{G}"

    resolve_effect(state, 1, "topdeck_put_creatures_battlefield", {"top_n": 6, "max_creatures": 2, "mv_max": 3})
    names = [state.cards[cid].name for cid in p1.battlefield]
    assert "Elf 2" in names
    assert "Elf 3" in names
    assert "Big 5" not in names


def test_arboreal_grazer_style_land_from_hand_enters_tapped_without_land_play() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    land_id = state.players[1].hand[0]
    state.cards[land_id].name = "Forest"
    state.cards[land_id].types = ["Land"]
    state.cards[land_id].oracle_text = "{T}: Add {G}."
    grazer = CardInstance(
        id="grazer",
        name="Arboreal Grazer",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Creature"],
        oracle_text="When Arboreal Grazer enters the battlefield, you may put a land card from your hand onto the battlefield tapped.",
    )
    state.cards[grazer.id] = grazer
    effect_key, payload = infer_effect_from_oracle(state, grazer, 1)

    assert effect_key == "put_land_from_hand"
    resolve_effect(state, 1, effect_key, payload)
    assert land_id in state.players[1].battlefield
    assert land_id not in state.players[1].hand
    assert state.cards[land_id].tapped


def test_torrential_gearhulk_style_casts_target_instant_from_graveyard() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    spell = CardInstance(
        id="grave-spell",
        name="Shock",
        owner=1,
        controller=1,
        zone=Zone.GRAVEYARD,
        types=["Instant"],
        oracle_text="Shock deals 2 damage to any target.",
    )
    state.cards[spell.id] = spell
    state.players[1].graveyard.append(spell.id)
    source = CardInstance(
        id="gearhulk",
        name="Torrential Gearhulk",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Artifact", "Creature"],
        oracle_text="When Torrential Gearhulk enters the battlefield, you may cast target instant card from your graveyard without paying its mana cost.",
    )
    state.cards[source.id] = source
    effect_key, payload = infer_effect_from_oracle(state, source, 1)

    assert effect_key == "cast_from_graveyard"
    assert payload["target_card_id"] == spell.id
    resolve_effect(state, 1, effect_key, payload)
    assert state.stack and state.stack[-1].source_card_id == spell.id
    assert spell.id not in state.players[1].graveyard
    resolve_top_of_stack(state)
    assert spell.id in state.players[1].graveyard


def test_nissa_loyalty_lines_animate_land_and_put_green_creature() -> None:
    deck = [{"quantity": 60, "card_name": "Forest"}]
    state = MatchFactory.from_decks(deck, deck)
    p1 = state.players[1]
    land_id = p1.hand[0]
    p1.hand.remove(land_id)
    p1.battlefield.append(land_id)
    land = state.cards[land_id]
    land.zone = Zone.BATTLEFIELD
    land.types = ["Land"]
    land.name = "Forest"
    land.type_line = "Basic Land - Forest"
    creature_id = p1.hand[0]
    creature = state.cards[creature_id]
    creature.types = ["Creature"]
    creature.mana_cost = "{G}"
    creature.name = "Green Creature"
    nissa = CardInstance(
        id="nissa-loyalty",
        name="Nissa, Who Shakes the World",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Planeswalker"],
        oracle_text="",
    )
    state.cards[nissa.id] = nissa
    state.players[1].battlefield.append(nissa.id)

    key, payload = infer_effect_from_oracle(
        state,
        type("Proxy", (), {"name": nissa.name, "oracle_text": "Put a +1/+1 counter on up to one target land you control. Untap it. It becomes a 0/0 Elemental creature with haste that's still a land.", "mana_cost": ""})(),
        1,
        {"target_card_id": land_id},
    )
    assert key == "add_counters"
    assert payload["animate_land"] is True
    resolve_effect(state, 1, key, payload)
    assert "Creature" in land.types
    assert "haste" in land.keywords
    assert not land.tapped

    key, payload = infer_effect_from_oracle(
        state,
        type("Proxy", (), {"name": nissa.name, "oracle_text": "You may put a green creature card from your hand onto the battlefield.", "mana_cost": ""})(),
        1,
    )
    assert key == "put_green_creature_from_hand"
    resolve_effect(state, 1, key, payload)
    assert creature_id in p1.battlefield
    assert creature.summoning_sick


def test_storm_the_festival_style_puts_permanents_from_top() -> None:
    state = MatchFactory.from_decks([{"quantity": 60, "card_name": "Forest"}], [{"quantity": 60, "card_name": "Forest"}])
    card = CardInstance(
        id="storm",
        name="Storm the Festival",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Sorcery"],
        oracle_text="Look at the top five cards of your library. You may put up to two permanent cards with mana value 5 or less from among them onto the battlefield.",
    )
    key, payload = infer_effect_from_oracle(state, card, 1)

    assert key == "topdeck_put_permanents_battlefield"
    assert payload == {"top_n": 5, "max_permanents": 2, "mv_max": 5}
    resolve_effect(state, 1, key, payload)
    assert len(state.players[1].battlefield) == 2


def test_shark_typhoon_style_effect_uses_cast_spell_mana_value() -> None:
    state = MatchFactory.from_decks([{"quantity": 60, "card_name": "Island"}], [{"quantity": 60, "card_name": "Island"}])
    enchantment = CardInstance(
        id="typhoon",
        name="Shark Typhoon",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="Whenever you cast a noncreature spell, create a blue X/X Shark creature token with flying, where X is that spell's mana value.",
    )
    spell = CardInstance(
        id="spell",
        name="Memory Deluge",
        owner=1,
        controller=1,
        zone=Zone.STACK,
        types=["Instant"],
        mana_cost="{2}{U}{U}",
        oracle_text="Draw two cards.",
    )
    state.cards[enchantment.id] = enchantment
    state.cards[spell.id] = spell
    state.players[1].battlefield.append(enchantment.id)
    state.stack.append(type("Stack", (), {"source_card_id": spell.id, "controller": 1, "id": "stack"})())

    from rules_engine.events import emit_event
    emit_event(state, "spell_cast", {"source_card_id": spell.id, "controller": 1})

    assert state.stack[-1].effect_key == "create_shark_token"
    resolve_effect(state, 1, "create_shark_token", state.stack.pop().payload)
    shark = state.cards[state.players[1].battlefield[-1]]
    assert shark.name == "Shark"
    assert shark.power == 4 and shark.toughness == 4
    assert "flying" in shark.keywords


def test_light_up_the_stage_style_exiles_cards_with_temporary_play_permission() -> None:
    state = MatchFactory.from_decks([{"quantity": 60, "card_name": "Mountain"}], [{"quantity": 60, "card_name": "Mountain"}])
    top_id = state.players[1].library[-1]
    state.cards[top_id].name = "Playable Mountain"
    state.cards[top_id].types = ["Land"]
    state.cards[top_id].type_line = "Basic Land - Mountain"
    proxy = type("Proxy", (), {"name": "Light Up the Stage", "oracle_text": "Exile the top two cards of your library. Until the end of your next turn, you may play those cards.", "mana_cost": ""})()

    key, payload = infer_effect_from_oracle(state, proxy, 1)

    assert key == "exile_top_cards_playable"
    resolve_effect(state, 1, key, payload)
    assert top_id in state.players[1].exile
    assert state.players[1].exile_play_until[top_id] == state.turn + 1


def test_goblin_guide_style_reveals_defending_top_land() -> None:
    state = MatchFactory.from_decks([{"quantity": 60, "card_name": "Mountain"}], [{"quantity": 60, "card_name": "Mountain"}])
    target = state.players[2].library[-1]
    state.cards[target].types = ["Land"]
    state.cards[target].name = "Revealed Mountain"
    source = CardInstance(
        id="guide",
        name="Goblin Guide",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Creature"],
        oracle_text="Whenever Goblin Guide attacks, defending player reveals the top card of their library. That player may put that card into their hand if it's a land card.",
    )
    state.cards[source.id] = source
    key, payload = infer_effect_from_oracle(state, source, 1)

    assert key == "reveal_defending_top_land"
    resolve_effect(state, 1, key, payload)
    assert target in state.players[2].hand
