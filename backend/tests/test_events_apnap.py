from __future__ import annotations

from game_state.state import CardInstance, MatchFactory, StackItem, Zone
from rules_engine.events import emit_event
from rules_engine.stack_engine import add_to_stack
from rules_engine.engine import RulesEngine
from rules_engine.continuous import effective_power
from rules_engine.stack_engine import resolve_top_of_stack
from effects.handlers import destroy_permanent
from effects.handlers import create_token
from effects.handlers import sacrifice
from effects.handlers import discard_cards
from game_state.state import Step


def _put_trigger_creature(state, player_id: int, oracle: str) -> str:
    p = state.players[player_id]
    cid = p.hand[0]
    p.hand.remove(cid)
    p.battlefield.append(cid)
    c = state.cards[cid]
    c.zone = Zone.BATTLEFIELD
    c.types = ["Creature"]
    c.oracle_text = oracle
    c.name = f"T{player_id}-{cid[:4]}"
    return cid


def _put_trigger_permanent(state, player_id: int, oracle: str, types: list[str] | None = None) -> str:
    p = state.players[player_id]
    cid = p.hand[0]
    p.hand.remove(cid)
    p.battlefield.append(cid)
    c = state.cards[cid]
    c.zone = Zone.BATTLEFIELD
    c.types = list(types or ["Artifact"])
    c.oracle_text = oracle
    c.name = f"P{player_id}-{cid[:4]}"
    return cid


def test_apnap_trigger_order_on_shared_event() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1

    _put_trigger_creature(state, 1, "Whenever a creature dies, draw a card.")
    _put_trigger_creature(state, 2, "Whenever a creature dies, draw a card.")

    emit_event(state, "creature_dies", {"card_id": "x"})
    assert len(state.stack) >= 2
    assert state.stack[0].controller == 1
    assert state.stack[1].controller == 2


def test_begin_upkeep_triggers_apply_apnap_for_each_upkeep_text() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1

    _put_trigger_creature(state, 1, "At the beginning of each upkeep, draw a card.")
    _put_trigger_creature(state, 2, "At the beginning of each upkeep, draw a card.")

    emit_event(state, "begin_step", {"step": "upkeep", "active_player": 1})
    assert len(state.stack) >= 2
    assert state.stack[0].controller == 1
    assert state.stack[1].controller == 2


def test_begin_end_step_triggers_only_for_active_player_when_oracle_says_your() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1

    _put_trigger_creature(state, 1, "At the beginning of your end step, draw a card.")
    _put_trigger_creature(state, 2, "At the beginning of your end step, draw a card.")

    emit_event(state, "begin_step", {"step": "end_step", "active_player": 1})
    assert len(state.stack) == 1
    assert state.stack[0].controller == 1


def test_engine_upkeep_start_enqueues_begin_step_triggers() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.priority_player = 1
    state.step = state.step.UNTAP
    engine = RulesEngine()

    _put_trigger_creature(state, 1, "At the beginning of your upkeep, draw a card.")
    before = len(state.stack)
    # Advance UNTAP -> UPKEEP and run step-start hook.
    engine.take_action(state, 1, {"type": "pass_priority"})
    engine.take_action(state, 2, {"type": "pass_priority"})
    assert state.step == state.step.UPKEEP
    assert len(state.stack) >= before + 1


def test_spell_cast_trigger_from_permanent() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1

    _put_trigger_creature(state, 1, "Whenever you cast an instant or sorcery spell, draw a card.")
    source = state.players[1].hand[0]
    spell = state.cards[source]
    spell.types = ["Instant"]
    spell.zone = Zone.HAND

    state.players[1].hand.remove(source)
    spell.zone = Zone.STACK
    before = len(state.stack)
    add_to_stack(state, source, 1, "Test Instant", "draw_cards", {"amount": 1})

    assert len(state.stack) >= before + 2
    assert any(x.controller == 1 and "cast trigger" in x.label.lower() for x in state.stack)


def test_named_self_counter_trigger_resolves_without_card_specific_handler() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    source = _put_trigger_creature(
        state,
        1,
        "Whenever you cast a noncreature spell, put a +1/+1 counter on Sprite Dragon.",
    )
    state.cards[source].name = "Sprite Dragon"
    state.cards["spell-self-counter"] = CardInstance(
        id="spell-self-counter",
        name="Opt",
        owner=1,
        controller=1,
        zone=Zone.STACK,
        types=["Instant"],
    )
    emit_event(state, "spell_cast", {"source_card_id": "spell-self-counter", "controller": 1})

    trigger = next(item for item in state.stack if item.source_card_id == source)
    assert trigger.effect_key == "add_counters"
    assert trigger.payload["target_card_id"] == source
    from effects.registry import resolve_effect

    resolve_effect(state, 1, trigger.effect_key, trigger.payload)
    assert state.cards[source].counters["+1/+1"] == 1


def test_counted_creature_type_trigger_uses_resolution_time_board_state() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    source = _put_trigger_creature(
        state,
        1,
        "When Shaman of the Pack enters the battlefield, target opponent loses life equal to the number of Elves you control.",
    )
    state.cards[source].name = "Shaman of the Pack"
    elf = _put_trigger_creature(state, 1, "")
    state.cards[elf].type_line = "Creature — Elf Warrior"
    emit_event(state, "enters_battlefield", {"card_id": source, "controller": 1})

    trigger = next(item for item in state.stack if item.source_card_id == source)
    from effects.registry import resolve_effect

    before = state.players[2].life
    resolve_effect(state, 1, trigger.effect_key, trigger.payload)
    assert state.players[2].life == before - 1


def test_goblin_guide_attack_trigger_queues_structured_reveal() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1

    guide = _put_trigger_creature(
        state,
        1,
        "Whenever Goblin Guide attacks, defending player reveals the top card of their library. If it's a land card, that player puts it into their hand.",
    )
    state.cards[guide].name = "Goblin Guide"

    emit_event(state, "attack_declared", {"card_id": guide, "defending_player": 2})

    trigger = next(item for item in state.stack if item.source_card_id == guide)
    assert trigger.effect_key == "reveal_defending_top_land"
    assert trigger.payload["target_player"] == 2


def test_generic_controlled_creature_attack_trigger_still_matches() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1

    source = _put_trigger_creature(state, 1, "Whenever a creature you control attacks, draw a card.")
    attacker = _put_trigger_creature(state, 1, "")
    emit_event(state, "attack_declared", {"card_id": attacker, "defending_player": 2})

    assert any(item.source_card_id == source for item in state.stack)


def test_prowess_style_noncreature_spell_trigger_grants_temporary_pump() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1

    creature = _put_trigger_creature(state, 1, "Prowess")
    state.cards[creature].power = 1
    state.cards[creature].toughness = 1
    spell_id = "spell-1"
    state.cards[spell_id] = CardInstance(
        id=spell_id,
        name="Opt",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Instant"],
        oracle_text="Draw a card.",
    )
    state.players[1].hand.append(spell_id)
    state.players[1].hand.remove(spell_id)
    state.cards[spell_id].zone = Zone.STACK

    add_to_stack(state, spell_id, 1, "Opt", "draw_cards", {"amount": 1})
    resolve_top_of_stack(state)

    assert effective_power(state, creature) == 2
    assert state.cards[creature].counters.get("__eot_power") == 1

    engine = RulesEngine()
    state.step = Step.CLEANUP
    engine._apply_step_start_actions(state)
    assert state.cards[creature].counters.get("__eot_power") is None
    assert effective_power(state, creature) == 1


def test_copying_a_spell_triggers_magecraft_style_pump() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1

    creature = _put_trigger_creature(state, 1, "Magecraft — Whenever you cast or copy an instant or sorcery spell, this creature gets +1/+1 until end of turn.")
    state.cards[creature].power = 1
    state.cards[creature].toughness = 1

    spell_id = "spell-2"
    state.cards[spell_id] = CardInstance(
        id=spell_id,
        name="Opt",
        owner=1,
        controller=1,
        zone=Zone.STACK,
        types=["Instant"],
        oracle_text="Draw a card.",
    )
    state.stack.append(StackItem(id="stack-1", source_card_id=spell_id, controller=1, label="Opt", effect_key="draw_cards", payload={"amount": 1}))

    from effects.registry import resolve_effect

    resolve_effect(state, 1, "copy_spell", {"target_stack_id": "stack-1"})
    resolve_top_of_stack(state)

    assert effective_power(state, creature) == 2
    assert state.cards[creature].counters.get("__eot_power") == 1


def test_trigger_stack_items_include_order_metadata() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.players[1].battlefield = ["c1", "c2"]
    state.cards["c1"] = CardInstance(
        id="c1",
        name="B Trigger",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Creature"],
        oracle_text="Whenever a creature dies, draw a card.",
    )
    state.cards["c2"] = CardInstance(
        id="c2",
        name="A Trigger",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Creature"],
        oracle_text="Whenever a creature dies, draw a card.",
    )

    emit_event(state, "creature_dies", {"card_id": "x"})
    assert len(state.stack) == 2
    assert state.stack[0].payload["__trigger_order"] == 0
    assert state.stack[1].payload["__trigger_order"] == 1
    assert state.stack[0].payload["__trigger_event"] == "creature_dies"


def test_creature_dies_trigger_matches_you_control_clause() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.players[1].battlefield = ["c1"]
    state.cards["c1"] = CardInstance(
        id="c1",
        name="Grim Haruspex",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Creature"],
        oracle_text="Whenever a nontoken creature you control dies, draw a card.",
    )
    dead = CardInstance(
        id="dead",
        name="Soldier",
        owner=1,
        controller=1,
        zone=Zone.GRAVEYARD,
        types=["Creature"],
    )
    state.cards[dead.id] = dead

    emit_event(state, "creature_dies", {"card_id": dead.id})
    assert len(state.stack) == 1
    assert state.stack[0].controller == 1


def test_creature_dies_trigger_matches_one_or_more_variant() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.players[1].battlefield = ["c1"]
    state.cards["c1"] = CardInstance(
        id="c1",
        name="Sifter",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Creature"],
        oracle_text="Whenever one or more creatures you control die, draw a card.",
    )
    dead = CardInstance(
        id="dead",
        name="Soldier",
        owner=1,
        controller=1,
        zone=Zone.GRAVEYARD,
        types=["Creature"],
    )
    state.cards[dead.id] = dead

    emit_event(state, "creature_dies", {"card_id": dead.id})
    assert len(state.stack) == 1
    assert state.stack[0].controller == 1


def test_artifact_etb_triggers_from_generic_permanent_entry() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1

    _put_trigger_permanent(state, 1, "Whenever an artifact enters the battlefield under your control, draw a card.", ["Artifact"])
    token_id = "artifact-token"
    state.cards[token_id] = CardInstance(
        id=token_id,
        name="Treasure",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Artifact", "Token"],
    )

    emit_event(state, "enters_battlefield", {"card_id": token_id, "controller": 1})
    assert len(state.stack) == 1
    assert state.stack[0].controller == 1
    assert state.stack[0].effect_key == "draw_cards"


def test_enchantment_dies_triggers_from_permanent_death_event() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1

    _put_trigger_permanent(state, 1, "Whenever an enchantment you control dies, draw a card.", ["Enchantment"])
    dead_id = "enchant-dead"
    state.cards[dead_id] = CardInstance(
        id=dead_id,
        name="Dead Enchantment",
        owner=1,
        controller=1,
        zone=Zone.GRAVEYARD,
        types=["Enchantment"],
    )

    emit_event(state, "permanent_dies", {"card_id": dead_id, "controller": 1})
    assert len(state.stack) == 1
    assert state.stack[0].controller == 1
    assert state.stack[0].effect_key == "draw_cards"


def test_artifact_or_enchantment_etb_and_death_clauses_match_both_types() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1

    _put_trigger_permanent(state, 1, "Whenever an artifact or enchantment enters the battlefield under your control, draw a card.", ["Artifact"])
    _put_trigger_permanent(state, 1, "Whenever an artifact or enchantment you control dies, draw a card.", ["Enchantment"])

    artifact_id = "combo-artifact"
    enchant_id = "combo-enchantment"
    state.cards[artifact_id] = CardInstance(
        id=artifact_id,
        name="Treasure",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Artifact", "Token"],
    )
    state.cards[enchant_id] = CardInstance(
        id=enchant_id,
        name="Dead Aura",
        owner=1,
        controller=1,
        zone=Zone.GRAVEYARD,
        types=["Enchantment"],
    )

    emit_event(state, "enters_battlefield", {"card_id": artifact_id, "controller": 1})
    emit_event(state, "permanent_dies", {"card_id": enchant_id, "controller": 1})
    assert len(state.stack) == 2
    assert all(item.effect_key == "draw_cards" for item in state.stack)


def test_artifact_and_enchantment_sacrifice_clauses_trigger_from_sacrificed_permanents() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1

    _put_trigger_permanent(state, 1, "Whenever an artifact you control is sacrificed, draw a card.", ["Artifact"])
    _put_trigger_permanent(state, 1, "Whenever an enchantment or artifact you control is sacrificed, draw a card.", ["Enchantment"])

    artifact_id = "artifact-sac"
    enchant_id = "enchant-sac"
    state.cards[artifact_id] = CardInstance(
        id=artifact_id,
        name="Treasure",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Artifact", "Token"],
    )
    state.cards[enchant_id] = CardInstance(
        id=enchant_id,
        name="Blessing",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
    )

    emit_event(state, "sacrifice", {"card_id": artifact_id, "controller": 1})
    emit_event(state, "sacrifice", {"card_id": enchant_id, "controller": 1})
    assert len(state.stack) == 3
    assert all(item.effect_key == "draw_cards" for item in state.stack)


def test_creature_dies_trigger_does_not_match_opponent_creature() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.players[1].battlefield = ["c1"]
    state.cards["c1"] = CardInstance(
        id="c1",
        name="Grim Haruspex",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Creature"],
        oracle_text="Whenever a creature you control dies, draw a card.",
    )
    dead = CardInstance(
        id="dead",
        name="Soldier",
        owner=2,
        controller=2,
        zone=Zone.GRAVEYARD,
        types=["Creature"],
    )
    state.cards[dead.id] = dead

    emit_event(state, "creature_dies", {"card_id": dead.id})
    assert len(state.stack) == 0


def test_permanent_dies_trigger_matches_noncreature_permanent() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.players[1].battlefield = ["p1"]
    state.cards["p1"] = CardInstance(
        id="p1",
        name="Afterlife Archive",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="Whenever a permanent you control dies, draw a card.",
    )
    dead = CardInstance(
        id="dead",
        name="Seal of Removal",
        owner=1,
        controller=1,
        zone=Zone.GRAVEYARD,
        types=["Enchantment"],
    )
    state.cards[dead.id] = dead

    emit_event(state, "permanent_dies", {"card_id": dead.id})
    assert len(state.stack) == 1
    assert state.stack[0].controller == 1


def test_permanent_dies_trigger_does_not_match_opponent_permanent() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.players[1].battlefield = ["p1"]
    state.cards["p1"] = CardInstance(
        id="p1",
        name="Afterlife Archive",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="Whenever a permanent you control dies, draw a card.",
    )
    dead = CardInstance(
        id="dead",
        name="Seal of Removal",
        owner=2,
        controller=2,
        zone=Zone.GRAVEYARD,
        types=["Enchantment"],
    )
    state.cards[dead.id] = dead

    emit_event(state, "permanent_dies", {"card_id": dead.id})
    assert len(state.stack) == 0


def test_destroy_permanent_emits_permanent_dies_for_noncreature() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.players[1].battlefield = ["p1"]
    state.cards["p1"] = CardInstance(
        id="p1",
        name="Afterlife Archive",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="Whenever a permanent you control dies, draw a card.",
    )
    target = state.players[1].hand[0]
    state.players[1].hand.remove(target)
    state.players[1].battlefield.append(target)
    state.cards[target].zone = Zone.BATTLEFIELD
    state.cards[target].controller = 1
    state.cards[target].owner = 1
    state.cards[target].types = ["Artifact"]
    state.cards[target].name = "Talisman of Progress"

    destroy_permanent(state, 1, {"target_card_id": target})

    assert len(state.stack) == 1
    assert state.stack[0].controller == 1


def test_create_token_emits_enters_battlefield_for_etb_triggers() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.players[1].battlefield = ["p1"]
    state.cards["p1"] = CardInstance(
        id="p1",
        name="Soul Warden",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Creature"],
        oracle_text="Whenever another creature enters the battlefield under your control, you gain 1 life.",
    )

    create_token(
        state,
        1,
        {
            "name": "White Soldier",
            "power": 1,
            "toughness": 1,
            "amount": 1,
            "types": ["Creature", "Token"],
        },
    )

    assert any(item.controller == 1 for item in state.stack)


def test_controller_scoped_etb_trigger_does_not_fire_for_opponent_creature() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.players[1].battlefield = ["p1"]
    state.cards["p1"] = CardInstance(
        id="p1",
        name="Soul Warden",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Creature"],
        oracle_text="Whenever a creature enters the battlefield under your control, you gain 1 life.",
    )
    state.cards["opponent-creature"] = CardInstance(
        id="opponent-creature",
        name="Opponent Creature",
        owner=2,
        controller=2,
        zone=Zone.BATTLEFIELD,
        types=["Creature"],
        oracle_text="",
    )

    emit_event(state, "enters_battlefield", {"card_id": "opponent-creature", "controller": 2})

    assert not any(item.controller == 1 for item in state.stack)


def test_gearhulk_etb_trigger_uses_graveyard_spell_effect() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
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
    state.players[1].battlefield = [source.id]
    spell = CardInstance(
        id="grave-spell",
        name="Opt",
        owner=1,
        controller=1,
        zone=Zone.GRAVEYARD,
        types=["Instant"],
        oracle_text="Draw a card.",
    )
    state.cards[spell.id] = spell
    state.players[1].graveyard = [spell.id]

    emit_event(state, "enters_battlefield", {"card_id": source.id, "controller": 1})

    assert len(state.stack) == 1
    assert state.stack[0].effect_key == "cast_from_graveyard"


def test_create_token_emits_enters_battlefield_for_permanent_etb_triggers() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.players[1].battlefield = ["p1"]
    state.cards["p1"] = CardInstance(
        id="p1",
        name="Anointed Procession",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="Whenever a permanent enters the battlefield under your control, draw a card.",
    )

    create_token(
        state,
        1,
        {
            "name": "White Soldier",
            "power": 1,
            "toughness": 1,
            "amount": 1,
            "types": ["Creature", "Token"],
        },
    )

    assert any(item.controller == 1 for item in state.stack)


def test_create_token_emits_enters_battlefield_for_another_permanent_etb_triggers() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.players[1].battlefield = ["p1"]
    state.cards["p1"] = CardInstance(
        id="p1",
        name="Anointed Procession",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="Whenever another permanent enters the battlefield under your control, draw a card.",
    )

    create_token(
        state,
        1,
        {
            "name": "White Soldier",
            "power": 1,
            "toughness": 1,
            "amount": 1,
            "types": ["Creature", "Token"],
        },
    )

    assert any(item.controller == 1 for item in state.stack)


def test_play_land_emits_landfall_trigger() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.priority_player = 1
    state.step = Step.PRECOMBAT_MAIN
    state.players[1].battlefield = ["p1"]
    state.cards["p1"] = CardInstance(
        id="p1",
        name="Lotus Cobra",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Creature"],
        oracle_text="Whenever a land enters the battlefield under your control, add one mana of any color.",
    )

    land_id = state.players[1].hand[0]
    state.cards[land_id].types = ["Land"]
    state.cards[land_id].zone = Zone.HAND
    from rules_engine.engine import RulesEngine

    RulesEngine().take_action(state, 1, {"type": "play_land", "card_id": land_id})

    assert any(item.controller == 1 for item in state.stack)


def test_sacrifice_emits_sacrifice_trigger_for_creature() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.players[1].battlefield = ["p1", "c1"]
    state.cards["p1"] = CardInstance(
        id="p1",
        name="Blood Artist",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Creature"],
        oracle_text="Whenever another creature you control is sacrificed, draw a card.",
    )
    state.cards["c1"] = CardInstance(
        id="c1",
        name="Token",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Creature", "Token"],
        oracle_text="",
    )

    sacrifice(state, 1, {"target_card_id": "c1"})

    assert any(item.controller == 1 for item in state.stack)


def test_discard_emits_discard_trigger_for_controller() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.players[1].battlefield = ["p1"]
    state.cards["p1"] = CardInstance(
        id="p1",
        name="Waste Not",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="Whenever you discard a card, draw a card.",
    )

    discard_cards(state, 1, {"target_player": 1, "amount": 1})

    assert any(item.controller == 1 for item in state.stack)


def test_discard_emits_one_or_more_variant_trigger_for_controller() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.players[1].battlefield = ["p1"]
    state.cards["p1"] = CardInstance(
        id="p1",
        name="Waste Not Plus",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="Whenever one or more cards are discarded, draw a card.",
    )

    discard_cards(state, 1, {"target_player": 1, "amount": 2})

    assert any(item.controller == 1 for item in state.stack)
