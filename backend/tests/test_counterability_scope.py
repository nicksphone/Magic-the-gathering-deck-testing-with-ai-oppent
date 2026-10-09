"""Spell-only protection does not protect the source's other stack objects."""
import json
from pathlib import Path

import pytest

from effects.handlers import copy_spell, counter_ability, counter_spell, counter_spell_unless_pay
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, StackItem, Step, Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack


CARDS = {row["name"]: row for row in json.loads(
    (Path(__file__).parent / "fixtures" / "counterability.json").read_text())}


def state_with_card(name, zone=Zone.STACK, controller=2):
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=707)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.priority_player = 1
    state.step = Step.PRECOMBAT_MAIN
    card = add_card(state, name, zone, controller)
    # Declare the fixture's kind now; targeting must not infer it from later source zones.
    kind = "spell" if zone == Zone.STACK else "activated"
    state.stack.append(StackItem("target", card.id, controller, name, "noop",
                                 {"__announced_stack_kind": kind}))
    return state, card


def add_card(state, name, zone, controller):
    raw = CARDS[name]
    cid = f"{name}-{len(state.cards)}"
    types = [kind for kind in ["Creature", "Enchantment", "Instant", "Sorcery"]
             if kind in raw["type_line"].split()]
    card = CardInstance(cid, name, controller, controller, zone, types,
                        mana_cost=raw["mana_cost"], type_line=raw["type_line"],
                        oracle_text=raw["oracle_text"], colors=raw["colors"],
                        power=int(raw["power"]) if raw["power"] else None,
                        toughness=int(raw["toughness"]) if raw["toughness"] else None)
    state.cards[cid] = card
    if zone != Zone.STACK:
        getattr(state.players[controller], zone.value).append(cid)
    return card


@pytest.mark.parametrize("name", ["Allosaurus Shepherd", "Destiny Spinner"])
def test_spell_protection_does_not_protect_source_activated_ability(name):
    state, card = state_with_card(name, Zone.BATTLEFIELD)
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    counter_ability(state, 1, {"target_stack_id": "target"})
    assert state.stack == []
    assert state.cards[card.id].zone == Zone.BATTLEFIELD
    assert card.id in state.players[2].battlefield


def test_stifle_cast_and_resolution_counters_shepherd_ability_not_source():
    state, card = state_with_card("Allosaurus Shepherd", Zone.BATTLEFIELD)
    stifle = add_card(state, "Stifle", Zone.HAND, 1)
    state.players[1].mana_pool["U"] = 1
    state = checked_action(state, RulesEngine(), 1, {
        "type": "cast_spell", "card_id": stifle.id,
        "targets": {"target_stack_id": "target"},
    })
    assert resolve_top_of_stack(state)
    assert state.stack == [] and state.cards[card.id].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize("name,protected", [("Allosaurus Shepherd", True), ("Destiny Spinner", False)])
@pytest.mark.parametrize("taxed", [False, True])
def test_static_protection_text_on_spell_is_not_self_protection(name, protected, taxed):
    state, card = state_with_card(name)
    handler = counter_spell_unless_pay if taxed else counter_spell
    handler(state, 1, {"target_stack_id": "target", "pay_unless_counter": False})
    assert bool(state.stack) == protected
    assert state.cards[card.id].zone == (Zone.STACK if protected else Zone.GRAVEYARD)


@pytest.mark.parametrize("source,name,controller,protected", [
    ("Allosaurus Shepherd", "Llanowar Elves", 2, True),
    ("Allosaurus Shepherd", "Cultivate", 2, True),
    ("Allosaurus Shepherd", "Lightning Bolt", 2, False),
    ("Allosaurus Shepherd", "Llanowar Elves", 1, False),
    ("Destiny Spinner", "Llanowar Elves", 2, True),
    ("Destiny Spinner", "Cultivate", 2, False),
    ("Destiny Spinner", "Llanowar Elves", 1, False),
])
@pytest.mark.parametrize("taxed", [False, True])
def test_battlefield_spell_protection_checks_printed_scope(source, name, controller, protected, taxed):
    state, card = state_with_card(name, controller=controller)
    add_card(state, source, Zone.BATTLEFIELD, 2)
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    handler = counter_spell_unless_pay if taxed else counter_spell
    handler(state, 1, {"target_stack_id": "target", "pay_unless_counter": False})
    assert bool(state.stack) == protected
    assert state.cards[card.id].zone == (Zone.STACK if protected else Zone.GRAVEYARD)


def test_removed_static_source_no_longer_protects_spell_at_counter_resolution():
    state, _ = state_with_card("Llanowar Elves")
    spinner = add_card(state, "Destiny Spinner", Zone.BATTLEFIELD, 2)
    counter = add_card(state, "Counterspell", Zone.HAND, 1)
    state.players[1].mana_pool["U"] = 2
    # Protection doesn't make the spell an illegal counterspell target.
    state = checked_action(state, RulesEngine(), 1, {
        "type": "cast_spell", "card_id": counter.id,
        "targets": {"target_stack_id": "target"},
    })
    from effects.handlers import destroy_permanent
    destroy_permanent(state, 1, {"target_card_id": spinner.id})
    assert resolve_top_of_stack(state)
    assert state.stack == []


def test_uncounterable_spell_remains_legal_target_and_survives_counter_resolution():
    state, card = state_with_card("Allosaurus Shepherd")
    counter = add_card(state, "Counterspell", Zone.HAND, 1)
    state.players[1].mana_pool["U"] = 2
    state = checked_action(state, RulesEngine(), 1, {
        "type": "cast_spell", "card_id": counter.id,
        "targets": {"target_stack_id": "target"},
    })
    assert resolve_top_of_stack(state)
    assert len(state.stack) == 1 and state.cards[card.id].zone == Zone.STACK
    assert counter.id in state.players[1].graveyard


def test_copy_keeps_intrinsic_spell_protection_after_source_changes_zone():
    state, card = state_with_card("Allosaurus Shepherd")
    copy_spell(state, 1, {"target_stack_id": "target"})
    copy_id = state.stack[-1].id
    # Direct zone movement models non-counter removal of the original.
    from rules_engine.zone_actions import move_spell_from_stack
    original = state.stack.pop(0)
    move_spell_from_stack(state, original)
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    counter_spell(state, 2, {"target_stack_id": copy_id})
    assert [item.id for item in state.stack] == [copy_id]
    assert state.cards[card.id].zone == Zone.GRAVEYARD


def test_global_protection_uses_copy_controller_not_physical_card_controller():
    state, card = state_with_card("Llanowar Elves")
    add_card(state, "Allosaurus Shepherd", Zone.BATTLEFIELD, 2)
    copy_spell(state, 1, {"target_stack_id": "target"})
    copy_id = state.stack[-1].id
    counter_spell(state, 2, {"target_stack_id": copy_id})
    assert [item.id for item in state.stack] == ["target"]
    assert card.zone == Zone.STACK
