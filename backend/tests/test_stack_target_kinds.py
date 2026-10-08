from tests.counter_native_frames import trigger_and_spell
import pytest

from effects.handlers import counter_ability, counter_spell, counter_spell_unless_pay
from game_state.state import CardInstance, Zone
from rules_engine.cast_choice import build_cast_hints
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import infer_effect_from_oracle
from rules_engine.action_validation import ActionRejected
from rules_engine.stack_engine import resolve_top_of_stack


def _state_with_trigger_and_spell(**options):
    return trigger_and_spell(**options)

def test_counterspell_targets_only_spells_and_does_not_move_trigger_source():
    state = _state_with_trigger_and_spell()
    trigger_id, spell_id = [item.id for item in state.stack]
    sheoldred_id, bolt_id = [item.source_card_id for item in state.stack]
    counter = CardInstance(
        id="counter", name="Counterspell", owner=1, controller=1,
        zone=Zone.HAND, types=["Instant"], mana_cost="{U}{U}", oracle_text="Counter target spell.",
    )
    state.cards[counter.id] = counter
    assert [item["id"] for item in build_cast_hints(state, counter, 1)["stack_targets"]] == [spell_id]
    counter_spell(state, 1, {"target_stack_id": trigger_id})
    counter_spell_unless_pay(state, 1, {"target_stack_id": trigger_id, "unless_cost": "{2}", "pay_unless_counter": False})
    assert [item.id for item in state.stack] == [trigger_id, spell_id]
    assert state.cards[sheoldred_id].zone == Zone.BATTLEFIELD
    assert state.players[2].battlefield == [sheoldred_id]
    assert sheoldred_id not in state.players[2].graveyard

    state.stack.pop()
    state.players[1].hand.append(counter.id)
    for _ in range(2):
        land_id = state.players[1].library.pop()
        state.players[1].battlefield.append(land_id)
        state.cards[land_id].zone = Zone.BATTLEFIELD
        state.cards[land_id].types = ["Land"]
    assert not any(move.get("card_id") == counter.id and move["type"] == "cast_spell" for move in RulesEngine().legal_moves(state, 1))
    with pytest.raises(ActionRejected):
        RulesEngine().take_action(state, 1, {
            "type": "cast_spell", "card_id": counter.id,
            "targets": {"target_stack_id": trigger_id},
        }, reject_invalid=True)
    assert counter.id in state.players[1].hand
    assert all(not state.cards[cid].tapped for cid in state.players[1].battlefield)
    assert state.players[2].battlefield == [sheoldred_id]


def test_stifle_targets_abilities_not_spells_or_their_sources():
    state = _state_with_trigger_and_spell(activated=True)
    trigger_id, spell_id, activated_id = [item.id for item in state.stack]
    sheoldred_id, bolt_id, ballista_id = [item.source_card_id for item in state.stack]
    stifle = CardInstance(
        id="stifle", name="Stifle", owner=1, controller=1,
        zone=Zone.HAND, types=["Instant"], mana_cost="{U}",
        oracle_text="Counter target activated or triggered ability. (Mana abilities can't be targeted.)",
    )
    state.cards[stifle.id] = stifle
    assert [item["id"] for item in build_cast_hints(state, stifle, 1)["stack_targets"]] == [trigger_id, activated_id]
    effect_key, payload = infer_effect_from_oracle(state, stifle, 1, {"target_stack_id": trigger_id})
    assert effect_key == "counter_ability"
    counter_ability(state, 1, {"target_stack_id": spell_id})
    counter_ability(state, 1, {"target_stack_id": activated_id, "target_kind": "triggered"})
    assert [item.id for item in state.stack] == [trigger_id, spell_id, activated_id]
    counter_ability(state, 1, payload)
    counter_ability(state, 1, {"target_stack_id": activated_id, "target_kind": "activated"})
    assert [item.id for item in state.stack] == [spell_id]
    assert state.cards[sheoldred_id].zone == Zone.BATTLEFIELD
    assert state.players[2].battlefield == [sheoldred_id, ballista_id]


def test_negate_only_counters_noncreature_spells():
    state = _state_with_trigger_and_spell(creature=True)
    trigger_id, spell_id, creature_stack_id = [item.id for item in state.stack]
    sheoldred_id, bolt_id, creature_id = [item.source_card_id for item in state.stack]
    creature = state.cards[creature_id]
    negate = CardInstance(
        id="negate", name="Negate", owner=1, controller=1,
        zone=Zone.HAND, types=["Instant"], mana_cost="{1}{U}",
        oracle_text="Counter target noncreature spell.",
    )
    state.cards[negate.id] = negate
    assert [item["id"] for item in build_cast_hints(state, negate, 1)["stack_targets"]] == [spell_id]
    effect_key, payload = infer_effect_from_oracle(state, negate, 1, {"target_stack_id": spell_id})
    assert (effect_key, payload) == ("counter_spell", {"target_stack_id": spell_id, "target_kind": "noncreature"})
    counter_spell(state, 1, {**payload, "target_stack_id": creature_stack_id})
    counter_spell_unless_pay(state, 1, {**payload, "target_stack_id": creature_stack_id, "unless_cost": "{2}", "pay_unless_counter": False})
    assert state.cards[creature.id].zone == Zone.STACK
    assert [item.id for item in state.stack] == [trigger_id, spell_id, creature_stack_id]
    counter_spell(state, 1, payload)
    assert [item.id for item in state.stack] == [trigger_id, creature_stack_id]
    assert state.cards[bolt_id].zone == Zone.GRAVEYARD


def test_negate_cast_path_counters_noncreature_spell():
    state = _state_with_trigger_and_spell()
    trigger_id, spell_id = [item.id for item in state.stack]
    sheoldred_id, bolt_id = [item.source_card_id for item in state.stack]
    negate = CardInstance(
        id="negate", name="Negate", owner=1, controller=1,
        zone=Zone.HAND, types=["Instant"], mana_cost="{1}{U}",
        oracle_text="Counter target noncreature spell.",
    )
    state.cards[negate.id] = negate
    state.players[1].hand.append(negate.id)
    for _ in range(2):
        land_id = state.players[1].library.pop()
        state.players[1].battlefield.append(land_id)
        state.cards[land_id].zone = Zone.BATTLEFIELD
        state.cards[land_id].types = ["Land"]
    assert any(move.get("card_id") == negate.id for move in RulesEngine().legal_moves(state, 1))
    RulesEngine().take_action(state, 1, {
        "type": "cast_spell", "card_id": negate.id,
        "targets": {"target_stack_id": spell_id},
    }, reject_invalid=True)
    assert state.stack[-1].effect_key == "counter_spell"
    resolve_top_of_stack(state)
    assert [item.id for item in state.stack] == [trigger_id]
    assert state.cards[bolt_id].zone == Zone.GRAVEYARD
    assert state.cards[sheoldred_id].zone == Zone.BATTLEFIELD
