from __future__ import annotations

from game_state.state import CardInstance, MatchFactory, Zone
from rules_engine.replacement import replacement_options
from rules_engine.state_based_actions import apply_state_based_actions


LORCAN_ORACLE = (
    "Flying\n"
    "Whenever a creature card is put into an opponent's graveyard from anywhere, "
    "you may pay life equal to its mana value. If you do, put it onto the battlefield "
    "under your control. It's a Warlock in addition to its other types.\n"
    "If a Warlock you control would die, exile it instead."
)


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
