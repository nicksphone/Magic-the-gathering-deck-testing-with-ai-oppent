from __future__ import annotations
from tests.rules_printed_facts_e4 import canonical_card, canonical_deck_entry, raw_card, set_printed
from tests.controlled_basic_game_support import controlled_basic_game
from tests.oracle_effects_positive_fixtures_8d import remaining_card

from card_data.seed_cards import seed_card_payload
from game_state.state import CardInstance, MatchFactory, Step, Zone
from effects.registry import resolve_effect
from rules_engine.continuous import effective_power, effective_toughness
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.cast_choice import build_cast_hints
from rules_engine.oracle_effects import infer_effect_from_oracle
from rules_engine.oracle_effects import inspect_target_hints


def _published_fixture_frame(state, frame_id, source, label, effect_key, payload,
                             *, is_spell, ability_text=''):
    """Declared parser fixtures use native publication, not guessed source zones."""
    from game_state.state import object_incarnation
    from rules_engine.stack_engine import add_to_stack
    from rules_engine.targeting import capture_announced_target_references

    targets = {key: payload[key] for key in ('target_player', 'target_card_id') if key in payload}
    packet = {**payload, '__announced_targets': targets,
              '__announced_target_references': capture_announced_target_references(state, targets)}
    if is_spell:
        packet.update(mana_spent=0, snow_mana_spent=0, snow_mana_colors={}, __kicked=False)
    else:
        packet.update(__activation_source_origin=source.zone.value,
                      __activation_source_reference={'incarnation': object_incarnation(source),
                                                     'zone_change_sequence': source.zone_change_sequence},
                      __ability_target_text=ability_text)
    item = add_to_stack(state, source.id, source.controller, label, effect_key, packet, is_spell=is_spell)
    item.id = frame_id
    return item


def test_oracle_damage_parsing() -> None:
    deck = [canonical_deck_entry('Island', 60)]
    state = MatchFactory.from_decks(deck, deck)
    card = canonical_card("Lightning Bolt", id="x", owner=1, controller=1, zone=Zone.HAND)
    effect_key, payload = infer_effect_from_oracle(state, card, 1)
    assert effect_key == "deal_damage"
    assert payload["amount"] == 3


def test_oracle_counterspell_parsing() -> None:
    deck = [canonical_deck_entry('Island', 60)]
    state = MatchFactory.from_decks(deck, deck)
    state.stack.append(type("SI", (), {"id": "stack-1"})())
    card = canonical_card("Counterspell", id="c", owner=1, controller=1, zone=Zone.HAND)
    effect_key, payload = infer_effect_from_oracle(state, card, 1)
    assert effect_key == "counter_spell"
    assert payload["target_stack_id"] == "stack-1"


def test_oracle_copy_spell_parsing() -> None:
    deck = [canonical_deck_entry('Island', 60)]
    state = MatchFactory.from_decks(deck, deck)
    state.stack.append(type("SI", (), {"id": "stack-copy"})())
    card = canonical_card("Twincast", id="copy", owner=1, controller=1, zone=Zone.HAND)
    effect_key, payload = infer_effect_from_oracle(state, card, 1)
    assert effect_key == "copy_spell"
    assert payload["target_stack_id"] == "stack-copy"


def test_twincast_can_copy_instant_or_sorcery_but_not_creature_spell() -> None:
    from game_state.state import StackItem

    deck = [canonical_deck_entry('Island', 60)]
    state = MatchFactory.from_decks(deck, deck, seed=936)
    for cid, name, types in (
        ("instant", "Lightning Bolt", ["Instant"]),
        ("sorcery", "Divination", ["Sorcery"]),
        ("creature", "Grizzly Bears", ["Creature"]),
    ):
        state.cards[cid] = canonical_card(name, id=cid, owner=2, controller=2, zone=Zone.STACK)
        _published_fixture_frame(state, cid, state.cards[cid], name, "noop", {}, is_spell=True)
    twincast = canonical_card("Twincast", id="twincast", owner=1, controller=1, zone=Zone.HAND)
    hints = build_cast_hints(state, twincast, 1)
    assert {item["id"] for item in hints["stack_targets"]} == {"instant", "sorcery"}
    key, payload = infer_effect_from_oracle(
        state, twincast, 1, action_targets={"target_stack_id": "sorcery"},
    )
    assert key == "copy_spell" and payload["target_stack_id"] == "sorcery"


def test_oracle_copy_ability_parsing() -> None:
    from rules_engine.targeting import stack_object_kind
    from tests.rings_activation_native_support_5763 import activate, board

    state = activate(board(1), 1)
    original, trigger = state.stack[0], state.stack[-1]
    effect_key, payload = trigger.effect_key, trigger.payload
    assert effect_key == "copy_referred_ability" and stack_object_kind(state, trigger) == "triggered"
    captured = payload["__activation_copy_original"]
    assert (captured["id"] == original.id
            and captured["source_card_id"] == original.source_card_id
            and "target_stack_id" not in payload)
    assert (captured["payload"]["__announced_stack_kind"] == "activated"
            and captured["payload"]["__announced_targets"] == original.payload["__announced_targets"]
            and payload["__optional_payment_cost"] == "{2}"
            and trigger.controller == original.controller == 1)


def test_lithoform_ability_copy_targets_only_controlled_abilities() -> None:
    from game_state.state import StackItem
    from rules_engine.action_validation import checked_action

    state = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Island"}],
        [{"quantity": 60, "card_name": "Island"}], seed=937,
    )
    for player_id in (1, 2):
        source = remaining_card('Prodigal Pyromancer', id=f"source-{player_id}", owner=player_id, controller=player_id, zone=Zone.BATTLEFIELD)
        state.cards[source.id] = source
        _published_fixture_frame(state, f"ability-{player_id}", source,
                                 "Prodigal Pyromancer ability", "deal_damage", {"amount": 1},
                                 is_spell=False, ability_text="This creature deals 1 damage to any target.")
    copier = remaining_card('Lithoform Engine', id="lithoform", owner=1, controller=1, zone=Zone.BATTLEFIELD)
    state.cards[copier.id] = copier
    state.players[1].battlefield.append(copier.id)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = 1
    state.players[1].mana_pool['C'] = 2
    rules = RulesEngine()
    move = next(move for move in rules.legal_moves(state, 1)
                if move['type'] == 'activate_ability' and move['card_id'] == copier.id
                and move['ability_index'] == 0)
    hints = move['target_hints']
    assert [item["id"] for item in hints["stack_targets"]] == ["ability-1"]
    state = checked_action(state, rules, 1, {
        'type': 'activate_ability', 'card_id': copier.id, 'ability_index': 0,
        'targets': {'target_stack_id': 'ability-1'}})
    key, payload = state.stack[-1].effect_key, state.stack[-1].payload
    assert key == "copy_ability"
    assert payload["may_choose_new_targets"] is True
    assert payload["copy_kind"] == "activated or triggered ability"


def test_copy_target_permanent_spell_excludes_instants_and_sorceries() -> None:
    from game_state.state import StackItem
    from rules_engine.action_validation import checked_action

    state = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Island"}],
        [{"quantity": 60, "card_name": "Island"}], seed=938,
    )
    for cid, types, controller in (("creature", ["Creature"], 1), ("artifact", ["Artifact"], 1),
                                   ("instant", ["Instant"], 1), ("sorcery", ["Sorcery"], 1),
                                   ("opponent-creature", ["Creature"], 2)):
        card = CardInstance(id=cid, name=cid, owner=controller, controller=controller,
                            zone=Zone.STACK, types=types)
        state.cards[cid] = card
        _published_fixture_frame(state, cid, card, cid, "noop", {}, is_spell=True)
    copier = remaining_card('Lithoform Engine', id="lithoform", owner=1, controller=1, zone=Zone.BATTLEFIELD)
    state.cards[copier.id] = copier
    state.players[1].battlefield.append(copier.id)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = 1
    state.players[1].mana_pool['C'] = 4
    rules = RulesEngine()
    move = next(move for move in rules.legal_moves(state, 1)
                if move['type'] == 'activate_ability' and move['card_id'] == copier.id
                and move['ability_index'] == 2)
    hints = move['target_hints']
    assert {target["id"] for target in hints["stack_targets"]} == {"creature", "artifact"}
    state = checked_action(state, rules, 1, {
        'type': 'activate_ability', 'card_id': copier.id, 'ability_index': 2,
        'targets': {'target_stack_id': 'creature'}})
    effect_key, payload = state.stack[-1].effect_key, state.stack[-1].payload
    assert effect_key == "copy_spell"
    assert payload["may_choose_new_targets"] is False


def test_oracle_counter_ability_parsing() -> None:
    deck = [canonical_deck_entry('Island', 60)]
    state = MatchFactory.from_decks(deck, deck)
    state.stack.append(type("SI", (), {"id": "stack-ability"})())
    card = canonical_card("Stifle", id="counter-ability", owner=1, controller=1, zone=Zone.HAND)
    effect_key, payload = infer_effect_from_oracle(state, card, 1)
    assert effect_key == "counter_ability"
    assert payload["target_stack_id"] == "stack-ability"
    assert payload["target_kind"] == "ability"


def test_oracle_target_hints_include_artifact_and_enchantment_targets() -> None:
    deck = [canonical_deck_entry('Island', 60)]
    state = MatchFactory.from_decks(deck, deck)
    card = canonical_card("Disenchant", id="rem", owner=1, controller=1, zone=Zone.HAND)
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
    card = remaining_card('Vindicate', id="rem", owner=1, controller=1, zone=Zone.HAND)
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
    state.cards["land"] = remaining_card('Island', id="land", owner=2, controller=2, zone=Zone.BATTLEFIELD)
    state.players[2].battlefield.extend(["artifact", "enchantment", "land"])

    hints = inspect_target_hints(state, card, 1)

    assert {entry["id"] for entry in hints.get("permanent_targets", [])} == {"artifact", "enchantment", "land"}


def test_nonland_permanent_removal_chooses_nonland_target() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    card = remaining_card('Vindicate', id="rem", owner=1, controller=1, zone=Zone.HAND)
    state.cards["artifact"] = CardInstance(
        id="artifact",
        name="Lockstone",
        owner=2,
        controller=2,
        zone=Zone.BATTLEFIELD,
        types=["Artifact"],
    )
    state.cards["land"] = remaining_card('Island', id="land", owner=2, controller=2, zone=Zone.BATTLEFIELD)
    state.players[2].battlefield.extend(["artifact", "land"])

    effect_key, payload = infer_effect_from_oracle(state, card, 1, action_targets={"target_card_id": "artifact"})

    assert effect_key == "destroy_permanent"
    assert payload["target_card_id"] == "artifact"


def test_split_card_marks_split_hints() -> None:
    import json
    from card_data.sync import ScryfallSyncService
    from game_state.state import _infer_keywords
    from rules_engine.card_types import printed_card_types

    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    card = canonical_card('Fire // Ice', id='split', owner=1, controller=1, zone=Zone.HAND)
    raw = raw_card('Fire // Ice')
    cached = ScryfallSyncService._normalize_payload(raw, None)
    expected = {field: cached[field] for field in
                ('name', 'oracle_text', 'mana_cost', 'type_line', 'layout', 'image_uri')}
    expected.update(types=printed_card_types(cached['type_line']),
        colors=cached['colors'].split(','), keywords=_infer_keywords(cached['oracle_text']),
        power=cached['power'], toughness=cached['toughness'], loyalty=cached['loyalty'],
        printed_power=cached['power'], printed_toughness=cached['toughness'],
        card_faces=json.loads(cached['card_faces_json']), selected_face_index=None,
        printed_characteristics={})
    assert (card.id, card.owner, card.controller, card.zone) == ('split', 1, 1, Zone.HAND)
    assert {field: getattr(card, field) for field in expected} == expected
    assert [face['name'] for face in card.card_faces] == ['Fire', 'Ice']
    hints = inspect_target_hints(state, card, 1)
    assert hints.get("split_card") is True
    assert hints.get("face_names") == ["Fire", "Ice"]
    assert not hints.get("modes")
    assert {field: getattr(card, field) for field in expected} == expected
    assert raw_card('Fire // Ice') == raw


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
    deck = [canonical_deck_entry('Island', 60)]
    state = MatchFactory.from_decks(deck, deck)
    state.players[1].life = 10
    state.players[2].life = 10
    state.cards["bolt-1"] = canonical_card("Lightning Bolt", id="bolt-1", owner=1, controller=1, zone=Zone.STACK)
    _published_fixture_frame(state, "stack-dmg", state.cards["bolt-1"], "Lightning Bolt",
                             "deal_damage", {"target_player": 2, "amount": 3}, is_spell=True)
    resolve_effect(state, 1, "copy_spell", {"target_stack_id": "stack-dmg"})
    assert state.players[2].life == 10
    assert len(state.stack) == 2
    resolve_top_of_stack(state)
    assert state.players[2].life == 7


def test_copy_ability_handler_replays_target_ability() -> None:
    deck = [canonical_deck_entry('Island', 60)]
    state = MatchFactory.from_decks(deck, deck)
    state.players[1].life = 10
    state.cards["warden-1"] = canonical_card("Soul Warden", id="warden-1", owner=1, controller=1, zone=Zone.BATTLEFIELD)
    from rules_engine.events import emit_event
    state.players[1].battlefield.append("warden-1")
    entering = canonical_card("Grizzly Bears", id="entering", owner=1, controller=1, zone=Zone.BATTLEFIELD)
    state.cards[entering.id] = entering
    state.players[1].battlefield.append(entering.id)
    emit_event(state, "enters_battlefield", {"card_id": entering.id, "controller": 1})
    state.stack[-1].id = "stack-ability"
    resolve_effect(state, 1, "copy_ability", {"target_stack_id": "stack-ability"})
    assert state.players[1].life == 10
    assert len(state.stack) == 2
    resolve_top_of_stack(state)
    assert state.players[1].life == 11


def test_counter_ability_handler_removes_stack_item() -> None:
    deck = [canonical_deck_entry('Island', 60)]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = 1
    state.step = Step.PRECOMBAT_MAIN
    state.cards["warden-1"] = canonical_card("Soul Warden", id="warden-1", owner=1, controller=1, zone=Zone.BATTLEFIELD)
    state.players[1].battlefield.append("warden-1")
    import json
    from pathlib import Path
    from tests.test_linked_damage_targets import raw_card
    from rules_engine.action_validation import checked_action
    from rules_engine.targeting import stack_object_kind

    # The trigger is emitted by actual paid creature resolution, not a synthetic SI.
    raw = json.loads((Path(__file__).parent / 'fixtures/creature_observer_audit/grizzly-bears.json').read_text())
    bear = raw_card(state, raw, 1, Zone.HAND)
    state.players[1].mana_pool.update({"G": 1, "C": 1})
    state = checked_action(state, RulesEngine(), 1, {"type": "cast_spell", "card_id": bear.id})
    assert state.stack[-1].payload["mana_spent"] == 2
    assert resolve_top_of_stack(state)
    trigger = state.stack[-1]
    assert trigger.source_card_id == "warden-1"
    assert stack_object_kind(state, trigger) == "triggered"
    resolve_effect(state, 1, "counter_ability", {"target_stack_id": trigger.id})
    assert state.stack == []


def test_oracle_reanimate_parsing_and_resolution() -> None:
    deck = [canonical_deck_entry('Island', 60)]
    state = MatchFactory.from_decks(deck, deck)
    p1 = state.players[1]
    creature = canonical_card("Mulldrifter", id="reanimate-me", owner=1, controller=1, zone=Zone.GRAVEYARD)
    state.cards[creature.id] = creature
    p1.graveyard.append(creature.id)
    card = canonical_card("Reanimate", id="reanimate-spell", owner=1, controller=1, zone=Zone.HAND)
    hints = inspect_target_hints(state, card, 1)
    assert creature.id in {entry["id"] for entry in hints.get("graveyard_creature_targets", [])}
    effect_key, payload = infer_effect_from_oracle(state, card, 1, action_targets={"target_card_id": creature.id})
    assert effect_key == "return_creature_from_graveyard_to_battlefield"
    assert payload["target_card_id"] == creature.id
    resolve_effect(state, 1, effect_key, payload)
    assert creature.id in p1.battlefield


def test_oracle_any_color_mana_choice_uses_hand_needs() -> None:
    deck = [
        canonical_deck_entry('Counterspell', 1),
        canonical_deck_entry('Lightning Bolt', 1),
        canonical_deck_entry('Island', 58),
    ]
    state = MatchFactory.from_decks(deck, deck)
    # Pose the existing blue-demand card in hand; do not add cards or mana.
    player = state.players[1]
    if not any(state.cards[cid].name == 'Counterspell' for cid in player.hand):
        counter = next(cid for cid in player.library if state.cards[cid].name == 'Counterspell')
        displaced = player.hand[-1]
        player.library[player.library.index(counter)] = displaced
        player.hand[-1] = counter
        state.cards[counter].move_to_zone(Zone.HAND)
        state.cards[displaced].move_to_zone(Zone.LIBRARY)
    card = canonical_card("Lotus Cobra", id="cobra", owner=1, controller=1, zone=Zone.BATTLEFIELD)
    effect_key, payload = infer_effect_from_oracle(state, card, 1)
    assert effect_key == "add_mana"
    assert payload["amount"] == 1
    assert payload["color"] == "U"
    resolve_effect(state, 1, effect_key, payload)
    assert state.players[1].mana_pool["U"] == 1


def test_oracle_reanimate_can_target_opponent_graveyard() -> None:
    deck = [canonical_deck_entry('Island', 60)]
    state = MatchFactory.from_decks(deck, deck)
    p2 = state.players[2]
    creature = canonical_card("Mulldrifter", id="enemy-reanimate-me", owner=2, controller=2, zone=Zone.GRAVEYARD)
    state.cards[creature.id] = creature
    p2.graveyard.append(creature.id)
    card = canonical_card("Reanimate", id="reanimate-spell-2", owner=1, controller=1, zone=Zone.HAND)
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
    from tests.graveyard_batch_native_support_bf62 import cast_vaults, place, position, snapshot

    state = position(('Open the Vaults', 'Sol Ring', 'Oath of Nissa', 'Grizzly Bears'),
                     ('Sol Ring', 'Oath of Nissa', 'Forest'))
    artifact = state.cards[place(state, 'Sol Ring', Zone.GRAVEYARD, 2)]
    enchantment = state.cards[place(state, 'Oath of Nissa', Zone.GRAVEYARD, 2)]
    own_artifact = place(state, 'Sol Ring', Zone.GRAVEYARD)
    own_enchantment = place(state, 'Oath of Nissa', Zone.GRAVEYARD)
    noneligible = [place(state, 'Grizzly Bears', Zone.GRAVEYARD),
                   place(state, 'Forest', Zone.GRAVEYARD, 2)]
    card = state.cards[place(state, 'Open the Vaults', Zone.HAND)]
    cohort = {own_artifact: 1, own_enchantment: 1, artifact.id: 2, enchantment.id: 2}

    hints = inspect_target_hints(state, card, 1)
    assert hints == {'artifact_targets': [], 'enchantment_targets': [], 'noncreature_permanent_targets': []}
    effect_key, payload = infer_effect_from_oracle(state, card, 1)
    state, source = cast_vaults(state, 1)
    p2, frame = state.players[2], state.stack[-1]
    eligible = {cid: owner for owner in (1, 2) for cid in state.players[owner].graveyard
                if set(state.cards[cid].types) & {'Artifact', 'Enchantment'}}
    assert (effect_key == 'return_graveyard_permanents_batch'
            and payload == {'graveyard_batch_clause': card.oracle_text}
            and frame.effect_key == effect_key and source == card.id
            and frame.targets == [] and frame.payload['__announced_targets'] == {}
            and sum(state.players[1].mana_pool.values()) == 0 and eligible == cohort)
    resolved = resolve_top_of_stack(state)
    assert (resolved and artifact.id in state.players[2].battlefield
            and {cid for player in state.players.values() for cid in player.battlefield} == set(cohort))
    assert (artifact.id not in p2.graveyard
            and all(cid not in state.players[owner].graveyard for cid, owner in cohort.items())
            and all(state.cards[cid].zone == Zone.GRAVEYARD for cid in noneligible)
            and state.cards[source].zone == Zone.GRAVEYARD)
    restored = snapshot(state)
    assert (state.cards[artifact.id].controller == 2
            and all(state.cards[cid].controller == owner and cid in state.players[owner].battlefield
                    and restored.cards[cid].controller == owner and cid in restored.players[owner].battlefield
                    for cid, owner in cohort.items()))


def test_oracle_can_return_generic_permanent_from_graveyard() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    p2 = state.players[2]
    land = remaining_card('Tropical Island', id="enemy-land", owner=2, controller=2, zone=Zone.GRAVEYARD)
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
    deck = [canonical_deck_entry('Island', 60)]
    state = MatchFactory.from_decks(deck, deck)
    artifact_id = "artifact-library"
    artifact = canonical_card("Sol Ring", id=artifact_id, owner=1, controller=1, zone=Zone.LIBRARY)
    state.cards[artifact.id] = artifact
    state.players[1].library.append(artifact.id)
    second = canonical_card("Arcane Signet", id="second-artifact-library", owner=1, controller=1, zone=Zone.LIBRARY)
    state.cards[second.id] = second
    state.players[1].library.append(second.id)
    card = canonical_card("Fabricate", id="tutor", owner=1, controller=1, zone=Zone.HAND)

    effect_key, payload = infer_effect_from_oracle(state, card, 1)
    assert effect_key == "search_library"
    assert payload["contains"] == "artifact"
    assert payload["count"] == 1
    resolve_effect(state, 1, effect_key, payload)
    assert sum(cid in state.players[1].hand for cid in (artifact.id, second.id)) == 1
    assert sum(cid in state.players[1].library for cid in (artifact.id, second.id)) == 1


def test_oracle_search_library_can_put_creature_onto_battlefield() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    creature_id = "creature-library"
    creature = remaining_card('Elvish Mystic', id=creature_id, owner=1, controller=1, zone=Zone.LIBRARY)
    state.cards[creature.id] = creature
    state.players[1].library.append(creature.id)
    card = remaining_card('Collected Company', id="tutor-battlefield", owner=1, controller=1, zone=Zone.HAND)

    effect_key, payload = infer_effect_from_oracle(state, card, 1)
    assert effect_key == "topdeck_put_creatures_battlefield"
    assert (payload["top_n"], payload["max_creatures"], payload["mv_max"]) == (6, 2, 3)
    resolve_effect(state, 1, effect_key, payload)
    assert creature.id in state.players[1].battlefield
    assert creature.id not in state.players[1].library


def test_oracle_search_library_honors_count_and_mana_value_on_battlefield_tutors() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    player = state.players[1]
    player.library = []

    low_a = remaining_card('Llanowar Elves', id="low-a", owner=1, controller=1, zone=Zone.LIBRARY)
    low_b = remaining_card('Elvish Mystic', id="low-b", owner=1, controller=1, zone=Zone.LIBRARY)
    high = remaining_card('Steel Hellkite', id="high", owner=1, controller=1, zone=Zone.LIBRARY)
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
    deck = [canonical_deck_entry('Island', 60)]
    state = MatchFactory.from_decks(deck, deck)
    card = canonical_card("Call the Cavalry", id="tok", owner=1, controller=1, zone=Zone.HAND)
    effect_key, payload = infer_effect_from_oracle(state, card, 1)
    assert effect_key == "create_token"
    assert payload["amount"] == 2
    assert payload["power"] == 2
    assert payload["toughness"] == 2
    assert payload["name"] == "Knight"
    assert payload["colors"] == ["W"]
    assert "vigilance" in payload["keywords"]


def test_oracle_destroy_all_creatures_resolution_wipes_board() -> None:
    deck = [canonical_deck_entry('Island', 60)]
    state = MatchFactory.from_decks(deck, deck)
    p1 = state.players[1]
    p2 = state.players[2]
    creature_a = canonical_card("Runeclaw Bear", id="crea", owner=1, controller=1, zone=Zone.BATTLEFIELD)
    creature_b = canonical_card("Elvish Mystic", id="creb", owner=2, controller=2, zone=Zone.BATTLEFIELD)
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
    deck = [canonical_deck_entry('Island', 60)]
    state = MatchFactory.from_decks(deck, deck)
    p2 = state.players[2]
    artifact = canonical_card("Mystic Forge", id="art", owner=2, controller=2, zone=Zone.BATTLEFIELD)
    enchantment = canonical_card("Rest in Peace", id="ench", owner=2, controller=2, zone=Zone.BATTLEFIELD)
    state.cards[artifact.id] = artifact
    state.cards[enchantment.id] = enchantment
    p2.battlefield.extend([artifact.id, enchantment.id])

    card = canonical_card("Disenchant", id="remove", owner=1, controller=1, zone=Zone.HAND)
    effect_key, payload = infer_effect_from_oracle(state, card, 1)
    assert effect_key == "destroy_permanent"
    assert payload["target_card_id"] in {artifact.id, enchantment.id}


def test_oracle_destroy_all_artifacts_and_enchantments_wipes_both_types() -> None:
    deck = [canonical_deck_entry('Island', 60)]
    state = MatchFactory.from_decks(deck, deck)
    p1 = state.players[1]
    p2 = state.players[2]
    artifact = canonical_card("Sol Ring", id="art", owner=1, controller=1, zone=Zone.BATTLEFIELD)
    enchantment = canonical_card("Oath of Nissa", id="ench", owner=2, controller=2, zone=Zone.BATTLEFIELD)
    state.cards[artifact.id] = artifact
    state.cards[enchantment.id] = enchantment
    p1.battlefield.append(artifact.id)
    p2.battlefield.append(enchantment.id)

    resolve_effect(state, 1, "destroy_all_artifacts_and_enchantments", {})

    assert artifact.id in p1.graveyard
    assert enchantment.id in p2.graveyard


def test_oracle_mass_artifact_and_enchantment_removal_is_inferred() -> None:
    from tests.oracle_effects_semantic_support_8d import purify_card

    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    card = purify_card(id="wipe", owner=1, controller=1, zone=Zone.HAND)
    effect_key, payload = infer_effect_from_oracle(state, card, 1)
    assert effect_key == "destroy_all_artifacts_and_enchantments"
    assert payload == {}


def test_oracle_collected_company_style_parsing() -> None:
    deck = [canonical_deck_entry('Island', 60)]
    state = MatchFactory.from_decks(deck, deck)
    card = canonical_card("Collected Company", id="cc", owner=1, controller=1, zone=Zone.HAND)
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
    import pytest
    from game_state.serializers import serialize_match_snapshot
    from rules_engine.action_validation import ActionRejected, checked_action

    deck = [{"quantity": 60, "card_name": "Island"}]
    state = controlled_basic_game(deck, deck)
    # This handler unit resolves during play; pregame entries do not count in land history.
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    land_id = state.players[1].hand[0]
    set_printed(state.cards[land_id], 'Forest')
    grazer = canonical_card("Arboreal Grazer", id="grazer", owner=1, controller=1, zone=Zone.BATTLEFIELD)
    state.cards[grazer.id] = grazer
    effect_key, payload = infer_effect_from_oracle(state, grazer, 1)

    assert effect_key == "put_land_from_hand"
    assert payload == {"tapped": True}  # Preserve this legacy mandatory handler contract.
    hand_count = len(state.players[1].hand)
    land_plays = state.players[1].lands_played_this_turn
    resolve_effect(state, 1, effect_key, payload)
    assert land_id in state.players[1].hand
    assert land_id not in state.players[1].battlefield
    assert state.pending_mechanic_choice["kind"] == "land_from_hand"
    assert state.pending_mechanic_choice["min_count"] == 1
    offered = RulesEngine().legal_moves(state, 1)[0]
    assert land_id in offered["options"] and offered["count"] == 1
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, {"type": "choose_mechanic", "card_ids": []})
    assert serialize_match_snapshot(state) == before
    state = checked_action(state, RulesEngine(), 1,
                           {"type": "choose_mechanic", "card_ids": [land_id]})
    assert land_id in state.players[1].battlefield
    assert land_id not in state.players[1].hand
    assert state.cards[land_id].tapped
    assert len(state.players[1].hand) == hand_count - 1
    assert state.players[1].lands_played_this_turn == land_plays
    assert state.land_entries_this_turn[1] == 1
    assert state.pending_mechanic_choice is None


def test_torrential_gearhulk_style_casts_target_instant_from_graveyard() -> None:
    from tests.test_activation_modifiers import board
    from tests.test_surveil_mill import add
    state = board()
    spell = add(state, 'Lightning Bolt', 1, Zone.GRAVEYARD)
    source = add(state, 'Torrential Gearhulk', 1)
    set_printed(spell, 'Lightning Bolt')
    set_printed(source, 'Torrential Gearhulk')
    effect_key, payload = infer_effect_from_oracle(state, source, 1)

    assert effect_key == "cast_from_graveyard"
    assert payload["target_card_id"] == spell.id
    resolve_effect(state, 1, effect_key, payload)
    assert state.stack and state.stack[-1].source_card_id == spell.id
    assert spell.id not in state.players[1].graveyard
    resolve_top_of_stack(state)
    assert spell.id in state.players[1].exile
    assert state.players[2].life == 17


def test_nissa_loyalty_lines_animate_land_and_put_green_creature() -> None:
    deck = [{"quantity": 60, "card_name": "Forest"}]
    state = MatchFactory.from_decks(deck, deck)
    p1 = state.players[1]
    land_id = p1.hand[0]
    p1.hand.remove(land_id)
    p1.battlefield.append(land_id)
    land = state.cards[land_id]
    land.zone = Zone.BATTLEFIELD
    set_printed(land, 'Forest')
    creature_id = p1.hand[0]
    creature = state.cards[creature_id]
    creature.types = ["Creature"]
    creature.mana_cost = "{G}"
    creature.name = "Green Creature"
    nissa = remaining_card('Nissa, Who Shakes the World', id="nissa-loyalty", owner=1, controller=1, zone=Zone.BATTLEFIELD)
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
    from rules_engine.continuous import effective_keywords
    assert "haste" in effective_keywords(state, land_id)
    assert 'haste' not in land.keywords  # A resolved grant is not a printed ability.
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


def test_real_noncreature_land_loyalty_clause_uses_legal_target_and_keywords() -> None:
    deck = [{"quantity": 60, "card_name": "Forest", "type_line": "Basic Land — Forest"}]
    state = MatchFactory.from_decks(deck, deck, seed=57)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = 1
    land_id, animated_id = state.players[1].hand[:2]
    for cid in (land_id, animated_id):
        state.players[1].hand.remove(cid)
        state.players[1].battlefield.append(cid)
        state.cards[cid].zone = Zone.BATTLEFIELD
    state.cards[land_id].tapped = True
    state.cards[animated_id].types.append("Creature")
    oracle = seed_card_payload("Nissa, Who Shakes the World")
    assert oracle is not None
    nissa = remaining_card('Nissa, Who Shakes the World', id="nissa", owner=1, controller=1, zone=Zone.BATTLEFIELD)
    state.cards[nissa.id] = nissa
    state.players[1].battlefield.append(nissa.id)

    rules = RulesEngine()
    move = next(m for m in rules.legal_moves(state, 1) if m.get("type") == "activate_loyalty" and m.get("ability_index") == 0)
    assert [item["id"] for item in move["target_hints"]["land_targets"]] == [land_id]
    rules.take_action(state, 1, {"type": "activate_loyalty", "card_id": nissa.id, "ability_index": 0, "targets": {"target_card_id": land_id}})
    assert state.stack[-1].effect_key == "add_counters"
    resolve_top_of_stack(state)

    land = state.cards[land_id]
    assert nissa.loyalty == 6
    assert land.counters["+1/+1"] == 3
    assert effective_power(state, land_id) == effective_toughness(state, land_id) == 3
    assert {"Land", "Creature"}.issubset(set(land.types))
    from rules_engine.continuous import effective_keywords
    assert {"vigilance", "haste"}.issubset(set(effective_keywords(state, land_id)))
    assert land.keywords == []
    assert not land.tapped
    assert not any("Oracle effect not inferred" in line for line in state.log)


def test_storm_the_festival_style_puts_permanents_from_top() -> None:
    state = MatchFactory.from_decks([canonical_deck_entry('Forest', 60)], [canonical_deck_entry('Forest', 60)])
    card = canonical_card("Storm the Festival", id="storm", owner=1, controller=1, zone=Zone.HAND)
    key, payload = infer_effect_from_oracle(state, card, 1)

    assert key == "topdeck_put_permanents_battlefield"
    assert payload == {"top_n": 5, "max_permanents": 2, "mv_max": 5, "bottom_random": True, "bottom_any_order": False}
    resolve_effect(state, 1, key, payload)
    assert len(state.players[1].battlefield) == 2


def test_shark_typhoon_style_effect_uses_cast_spell_mana_value() -> None:
    state = MatchFactory.from_decks([canonical_deck_entry('Island', 60)], [canonical_deck_entry('Island', 60)])
    enchantment = canonical_card("Shark Typhoon", id="typhoon", owner=1, controller=1, zone=Zone.BATTLEFIELD)
    spell = canonical_card("Memory Deluge", id="spell", owner=1, controller=1, zone=Zone.STACK)
    state.cards[enchantment.id] = enchantment
    state.cards[spell.id] = spell
    state.players[1].battlefield.append(enchantment.id)
    state.stack.append(type("Stack", (), {"source_card_id": spell.id, "controller": 1, "id": "stack", "payload": {}})())

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
    proxy = remaining_card('Light Up the Stage', id='stage-parser', owner=1, controller=1, zone=Zone.HAND)

    key, payload = infer_effect_from_oracle(state, proxy, 1)

    assert key == "exile_top_cards_playable"
    resolve_effect(state, 1, key, payload)
    assert top_id in state.players[1].exile
    assert state.players[1].exile_play_until[top_id] == state.turn + 1


def test_goblin_guide_style_reveals_defending_top_land() -> None:
    state = MatchFactory.from_decks([canonical_deck_entry('Mountain', 60)], [canonical_deck_entry('Mountain', 60)])
    target = state.players[2].library[-1]
    state.cards[target].types = ["Land"]
    state.cards[target].name = "Revealed Mountain"
    source = canonical_card("Goblin Guide", id="guide", owner=1, controller=1, zone=Zone.BATTLEFIELD)
    state.cards[source.id] = source
    key, payload = infer_effect_from_oracle(state, source, 1)

    assert key == "reveal_defending_top_land"
    resolve_effect(state, 1, key, payload)
    assert target in state.players[2].hand
