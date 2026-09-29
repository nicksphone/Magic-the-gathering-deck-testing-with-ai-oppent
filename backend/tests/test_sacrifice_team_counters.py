"""Sacrifice-triggered team counters use real Oracle wording and resolution state."""

import pytest

from effects.handlers import sacrifice
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Zone
from rules_engine.keyword_actions import finish_mechanic_choice, resolve_annihilator
from rules_engine.stack_engine import resolve_top_of_stack


def _state():
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=675)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    cards = [
        CardInstance(
            "mazirek", "Mazirek, Kraul Death Priest", 1, 1, Zone.BATTLEFIELD, ["Creature"],
            power=2, toughness=2,
            oracle_text="Flying\nWhenever a player sacrifices another permanent, put a +1/+1 counter on each creature you control.",
        ),
        CardInstance("ally", "Llanowar Elves", 1, 1, Zone.BATTLEFIELD, ["Creature"], power=1, toughness=1),
        CardInstance("fuel", "Sol Ring", 1, 1, Zone.BATTLEFIELD, ["Artifact"]),
        CardInstance("enemy", "Llanowar Elves", 2, 2, Zone.BATTLEFIELD, ["Creature"], power=1, toughness=1),
        CardInstance("enemy_fuel", "Sol Ring", 2, 2, Zone.BATTLEFIELD, ["Artifact"]),
    ]
    for card in cards:
        state.cards[card.id] = card
        state.players[card.controller].battlefield.append(card.id)
    return state


@pytest.mark.parametrize("sacrificer,card_id", [(1, "fuel"), (2, "enemy_fuel")])
def test_either_player_sacrifice_puts_counter_on_current_friendly_creatures(sacrificer, card_id):
    state = _state()
    sacrifice(state, sacrificer, {"target_card_id": card_id})
    assert [item.source_card_id for item in state.stack] == ["mazirek"]
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert resolve_top_of_stack(state)
    assert state.cards["mazirek"].counters["+1/+1"] == 1
    assert state.cards["ally"].counters["+1/+1"] == 1
    assert "+1/+1" not in state.cards["enemy"].counters


def test_sacrificing_source_itself_does_not_trigger_another_permanent_wording():
    state = _state()
    sacrifice(state, 1, {"target_card_id": "mazirek"})
    assert not any(item.source_card_id == "mazirek" for item in state.stack)
    assert "+1/+1" not in state.cards["ally"].counters


def test_team_counter_trigger_uses_creatures_present_at_resolution():
    state = _state()
    sacrifice(state, 1, {"target_card_id": "fuel"})
    state.players[1].battlefield.remove("ally")
    state.players[1].graveyard.append("ally")
    state.cards["ally"].zone = Zone.GRAVEYARD
    newcomer = CardInstance("newcomer", "Llanowar Elves", 1, 1, Zone.BATTLEFIELD, ["Creature"], power=1, toughness=1)
    state.cards[newcomer.id] = newcomer
    state.players[1].battlefield.append(newcomer.id)
    assert resolve_top_of_stack(state)
    assert state.cards["mazirek"].counters["+1/+1"] == 1
    assert state.cards["newcomer"].counters["+1/+1"] == 1
    assert "+1/+1" not in state.cards["ally"].counters


def test_departed_watcher_sees_other_simultaneous_sacrifice_but_not_its_own():
    state = _state()
    resolve_annihilator(state, 2, {"target_player": 1, "amount": 2})
    assert finish_mechanic_choice(state, 1, {"card_ids": ["mazirek", "fuel"]})
    assert [item.source_card_id for item in state.stack] == ["mazirek"]
    assert resolve_top_of_stack(state)
    assert state.cards["ally"].counters["+1/+1"] == 1
    assert "+1/+1" not in state.cards["mazirek"].counters
