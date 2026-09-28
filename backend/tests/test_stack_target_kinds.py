import pytest

from effects.handlers import counter_ability, counter_spell, counter_spell_unless_pay
from game_state.state import CardInstance, MatchFactory, StackItem, Step, Zone
from rules_engine.cast_choice import build_cast_hints
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import infer_effect_from_oracle
from rules_engine.action_validation import ActionRejected


def _state_with_trigger_and_spell():
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=100)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.DRAW
    state.priority_player = 1
    source = CardInstance(
        id="sheoldred", name="Sheoldred, the Apocalypse", owner=2, controller=2,
        zone=Zone.BATTLEFIELD, types=["Creature"], type_line="Legendary Creature — Phyrexian Praetor",
        oracle_text="Deathtouch\nWhenever you draw a card, you gain 2 life.\nWhenever an opponent draws a card, they lose 2 life.",
    )
    bolt = CardInstance(
        id="bolt", name="Lightning Bolt", owner=2, controller=2,
        zone=Zone.STACK, types=["Instant"], oracle_text="Lightning Bolt deals 3 damage to any target.",
    )
    state.cards[source.id] = source
    state.cards[bolt.id] = bolt
    state.players[2].battlefield.append(source.id)
    state.stack.extend([
        StackItem("trigger", source.id, 2, "Sheoldred trigger", "lose_life", {"__trigger_event": "draw_card"}),
        StackItem("spell", bolt.id, 2, "Lightning Bolt", "deal_damage", {"target_player": 1, "amount": 3}),
    ])
    return state


def test_counterspell_targets_only_spells_and_does_not_move_trigger_source():
    state = _state_with_trigger_and_spell()
    counter = CardInstance(
        id="counter", name="Counterspell", owner=1, controller=1,
        zone=Zone.HAND, types=["Instant"], mana_cost="{U}{U}", oracle_text="Counter target spell.",
    )
    state.cards[counter.id] = counter
    assert [item["id"] for item in build_cast_hints(state, counter, 1)["stack_targets"]] == ["spell"]
    counter_spell(state, 1, {"target_stack_id": "trigger"})
    counter_spell_unless_pay(state, 1, {"target_stack_id": "trigger", "unless_cost": "{2}", "pay_unless_counter": False})
    assert [item.id for item in state.stack] == ["trigger", "spell"]
    assert state.cards["sheoldred"].zone == Zone.BATTLEFIELD
    assert state.players[2].battlefield == ["sheoldred"]
    assert "sheoldred" not in state.players[2].graveyard

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
            "targets": {"target_stack_id": "trigger"},
        }, reject_invalid=True)
    assert counter.id in state.players[1].hand
    assert all(not state.cards[cid].tapped for cid in state.players[1].battlefield)
    assert state.players[2].battlefield == ["sheoldred"]


def test_stifle_targets_abilities_not_spells_or_their_sources():
    state = _state_with_trigger_and_spell()
    ballista = CardInstance(
        id="ballista", name="Walking Ballista", owner=2, controller=2,
        zone=Zone.BATTLEFIELD, types=["Creature"],
        oracle_text="Remove a +1/+1 counter from this creature: It deals 1 damage to any target.",
    )
    state.cards[ballista.id] = ballista
    state.players[2].battlefield.append(ballista.id)
    state.stack.append(StackItem(
        "activated", ballista.id, 2, "Walking Ballista ability", "deal_damage",
        {"target_player": 1, "amount": 1},
    ))
    stifle = CardInstance(
        id="stifle", name="Stifle", owner=1, controller=1,
        zone=Zone.HAND, types=["Instant"], mana_cost="{U}",
        oracle_text="Counter target activated or triggered ability. (Mana abilities can't be targeted.)",
    )
    state.cards[stifle.id] = stifle
    assert [item["id"] for item in build_cast_hints(state, stifle, 1)["stack_targets"]] == ["trigger", "activated"]
    effect_key, payload = infer_effect_from_oracle(state, stifle, 1, {"target_stack_id": "trigger"})
    assert effect_key == "counter_ability"
    counter_ability(state, 1, {"target_stack_id": "spell"})
    counter_ability(state, 1, {"target_stack_id": "activated", "target_kind": "triggered"})
    assert [item.id for item in state.stack] == ["trigger", "spell", "activated"]
    counter_ability(state, 1, payload)
    counter_ability(state, 1, {"target_stack_id": "activated", "target_kind": "activated"})
    assert [item.id for item in state.stack] == ["spell"]
    assert state.cards["sheoldred"].zone == Zone.BATTLEFIELD
    assert state.players[2].battlefield == ["sheoldred", "ballista"]
