"""Artifact-to-graveyard triggers share the actual destination, not the action verb."""

import pytest

from effects.handlers import destroy_all_creatures, destroy_permanent, sacrifice
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Zone
from rules_engine.events import flush_staged_triggers, resume_trigger_order
from rules_engine.stack_engine import resolve_top_of_stack


MASTER_ORACLE = (
    "Fabricate 3 (When this creature enters, put three +1/+1 counters on it or create "
    "three 1/1 colorless Servo artifact creature tokens.)\n"
    "Whenever an artifact you control is put into a graveyard from the battlefield, "
    "target opponent loses life equal to this creature's power."
)
CHALICE_ORACLE = (
    "Multikicker {2} (You may pay an additional {2} any number of times as you cast this spell.)\n"
    "This artifact enters with a charge counter on it for each time it was kicked.\n"
    "{T}: Add {C} for each charge counter on this artifact."
)
RIP_ORACLE = (
    "When this enchantment enters, exile all graveyards.\n"
    "If a card or token would be put into a graveyard from anywhere, exile it instead."
)


def _state(with_replacement=False):
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=602)
    state.pregame_pending = False
    cards = [
        CardInstance(
            "master", "Marionette Master", 1, 1, Zone.BATTLEFIELD, ["Creature"],
            power=1, toughness=3, oracle_text=MASTER_ORACLE, counters={"+1/+1": 2},
        ),
        CardInstance(
            "chalice", "Everflowing Chalice", 1, 1, Zone.BATTLEFIELD, ["Artifact"],
            oracle_text=CHALICE_ORACLE, counters={"charge": 1},
        ),
    ]
    if with_replacement:
        cards.append(CardInstance(
            "rip", "Rest in Peace", 2, 2, Zone.BATTLEFIELD, ["Enchantment"],
            oracle_text=RIP_ORACLE,
        ))
    for card in cards:
        state.cards[card.id] = card
        state.players[card.controller].battlefield.append(card.id)
    return state


@pytest.mark.parametrize("move", [destroy_permanent, sacrifice])
def test_artifact_death_uses_marionette_masters_effective_power(move):
    state = _state()
    move(state, 1, {"target_card_id": "chalice"})
    state = deserialize_match_snapshot(serialize_match_snapshot(state))

    triggers = [item for item in state.stack if item.source_card_id == "master"]
    assert len(triggers) == 1
    assert triggers[0].effect_key == "lose_life"
    assert triggers[0].payload["target_player"] == 2
    assert triggers[0].payload["amount"] == 3
    life = state.players[2].life
    assert resolve_top_of_stack(state)
    assert state.players[2].life == life - 3


@pytest.mark.parametrize("move", [destroy_permanent, sacrifice])
def test_exile_replacement_does_not_trigger_artifact_graveyard_clause(move):
    state = _state(with_replacement=True)
    move(state, 1, {"target_card_id": "chalice"})
    assert state.cards["chalice"].zone == Zone.EXILE
    assert not any(item.source_card_id == "master" for item in state.stack)


def test_simultaneous_wipe_uses_departing_trigger_source_and_artifact():
    state = _state()
    memnite = CardInstance(
        "memnite", "Memnite", 1, 1, Zone.BATTLEFIELD, ["Artifact", "Creature"],
        type_line="Artifact Creature — Construct", power=1, toughness=1,
    )
    state.cards[memnite.id] = memnite
    state.players[1].battlefield.append(memnite.id)

    destroy_all_creatures(state, 2, {})
    triggers = [item for item in state.stack if item.source_card_id == "master"]
    assert len(triggers) == 1
    assert triggers[0].payload["amount"] == 3
    assert state.cards["master"].zone == Zone.GRAVEYARD
    assert state.cards[memnite.id].zone == Zone.GRAVEYARD


def test_opponents_artifact_does_not_trigger_marionette_master():
    state = _state()
    artifact = CardInstance(
        "opposing-chalice", "Everflowing Chalice", 2, 2, Zone.BATTLEFIELD,
        ["Artifact"], oracle_text=CHALICE_ORACLE,
    )
    state.cards[artifact.id] = artifact
    state.players[2].battlefield.append(artifact.id)

    destroy_permanent(state, 1, {"target_card_id": artifact.id})
    assert not any(item.source_card_id == "master" for item in state.stack)


def test_prior_departure_cannot_trigger_on_later_artifact_death():
    state = _state()
    destroy_permanent(state, 2, {"target_card_id": "master"})
    assert state.cards["master"].last_known_battlefield

    destroy_permanent(state, 2, {"target_card_id": "chalice"})
    assert not any(item.source_card_id == "master" for item in state.stack)


def _add_merchant(state):
    merchant = CardInstance(
        "merchant", "Merchant of Venom", 1, 1, Zone.BATTLEFIELD, ["Creature"],
        type_line="Creature — Cat Warlock", power=1, toughness=1,
        oracle_text=(
            "Menace\nWhen this creature enters, each player sacrifices a creature of their choice.\n"
            "Whenever a player sacrifices a permanent, put a +1/+1 counter on this creature."
        ),
    )
    state.cards[merchant.id] = merchant
    state.players[1].battlefield.append(merchant.id)


def test_sacrifice_and_graveyard_triggers_share_human_order_choice():
    state = _state()
    _add_merchant(state)
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {1}

    sacrifice(state, 1, {"target_card_id": "chalice"})
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    pending = state.pending_trigger_order
    assert pending is not None
    group = pending["groups"]["1"]
    assert {item["source_card_id"] for item in group} == {"master", "merchant"}
    requested = [item["_choice_id"] for item in reversed(group)]
    assert resume_trigger_order(state, requested)
    assert [item.source_card_id for item in state.stack] == [item["source_card_id"] for item in reversed(group)]


def test_sacrifice_preserves_outer_trigger_staging():
    state = _state()
    _add_merchant(state)
    state.trigger_staging = True
    state.trigger_staging_event = "outer"

    sacrifice(state, 1, {"target_card_id": "chalice"})
    assert state.trigger_staging
    assert state.stack == []
    assert {item["source_card_id"] for item in state.staged_triggers} == {"master", "merchant"}
    flush_staged_triggers(state)
    assert {item.source_card_id for item in state.stack} == {"master", "merchant"}


def test_exiled_sacrifice_still_triggers_merchant_only():
    state = _state(with_replacement=True)
    _add_merchant(state)

    sacrifice(state, 1, {"target_card_id": "chalice"})
    assert state.cards["chalice"].zone == Zone.EXILE
    assert {item.source_card_id for item in state.stack} == {"merchant"}
    assert state.stack[-1].effect_key == "add_counters"
    assert resolve_top_of_stack(state)
    assert state.cards["merchant"].counters["+1/+1"] == 1


def test_opponent_sacrifice_triggers_merchant():
    state = _state()
    _add_merchant(state)
    artifact = CardInstance(
        "opposing-chalice", "Everflowing Chalice", 2, 2, Zone.BATTLEFIELD,
        ["Artifact"], oracle_text=CHALICE_ORACLE,
    )
    state.cards[artifact.id] = artifact
    state.players[2].battlefield.append(artifact.id)

    sacrifice(state, 2, {"target_card_id": artifact.id})
    triggers = [item for item in state.stack if item.source_card_id == "merchant"]
    assert len(triggers) == 1
    assert triggers[0].controller == 1
