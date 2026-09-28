from __future__ import annotations

import pytest

from game_state.state import CardInstance, MatchFactory, Zone
from rules_engine.replacement import replacement_options
from rules_engine.state_based_actions import apply_state_based_actions
from rules_engine.zone_actions import discard_selected


LORCAN_ORACLE = (
    "Flying\n"
    "Whenever a creature card is put into an opponent's graveyard from anywhere, "
    "you may pay life equal to its mana value. If you do, put it onto the battlefield "
    "under your control. It's a Warlock in addition to its other types.\n"
    "If a Warlock you control would die, exile it instead."
)
REST_IN_PEACE_ORACLE = (
    "When this enchantment enters, exile all graveyards.\n"
    "If a card or token would be put into a graveyard from anywhere, exile it instead."
)


def _rest_in_peace_state():
    deck = [{"quantity": 60, "card_name": "Plains"}]
    state = MatchFactory.from_decks(deck, deck, seed=37)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.cards["rip"] = CardInstance(
        id="rip", name="Rest in Peace", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Enchantment"], type_line="Enchantment",
        oracle_text=REST_IN_PEACE_ORACLE,
    )
    state.players[1].battlefield.append("rip")
    return state


@pytest.mark.xfail(strict=True, reason="Canonical Rest in Peace does not yet replace every graveyard move")
def test_rest_in_peace_exiles_a_dying_creature() -> None:
    state = _rest_in_peace_state()
    cid = state.players[2].hand.pop()
    state.players[2].battlefield.append(cid)
    card = state.cards[cid]
    card.zone = Zone.BATTLEFIELD
    card.types = ["Creature"]
    card.name = "Grizzly Bears"
    card.type_line = "Creature — Bear"
    card.power = card.toughness = 2
    card.counters["__damage_marked"] = 2

    apply_state_based_actions(state)

    assert card.zone == Zone.EXILE
    assert cid in state.players[2].exile


@pytest.mark.xfail(strict=True, reason="Canonical Rest in Peace does not yet replace every graveyard move")
def test_rest_in_peace_exiles_a_discarded_card() -> None:
    state = _rest_in_peace_state()
    cid = state.players[2].hand[0]

    assert discard_selected(state, 2, [cid])
    assert state.cards[cid].zone == Zone.EXILE
    assert cid in state.players[2].exile


def test_real_subtype_replacement_applies_before_simultaneous_source_death() -> None:
    deck = [{"quantity": 60, "card_name": "Swamp"}]
    state = MatchFactory.from_decks(deck, deck, seed=31)
    state.pregame_pending = False
    state.kept_hands = {1, 2}

    for cid, name, type_line, power, toughness, oracle in (
        ("lorcan", "Lorcan, Warlock Collector", "Legendary Creature — Devil", 6, 6, LORCAN_ORACLE),
        (
            "poet", "Arrogant Poet", "Creature — Human Warlock", 2, 1,
            "Whenever this creature attacks, you may pay 2 life. If you do, it gains flying until end of turn.",
        ),
        ("bears", "Grizzly Bears", "Creature — Bear", 2, 2, ""),
    ):
        state.cards[cid] = CardInstance(
            id=cid, name=name, owner=1, controller=1, zone=Zone.BATTLEFIELD,
            types=["Creature"], type_line=type_line, power=power,
            toughness=toughness, oracle_text=oracle,
            counters={"__damage_marked": toughness},
        )
        state.players[1].battlefield.append(cid)

    assert [option["source_id"] for option in replacement_options(state, "die_zone", target_card_id="poet")] == ["lorcan"]
    assert replacement_options(state, "die_zone", target_card_id="bears") == []

    apply_state_based_actions(state)

    assert state.cards["lorcan"].zone == Zone.GRAVEYARD
    assert state.cards["poet"].zone == Zone.EXILE
    assert state.cards["bears"].zone == Zone.GRAVEYARD
    assert "poet" not in state.players[1].graveyard
