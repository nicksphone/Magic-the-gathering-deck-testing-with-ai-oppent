from effects.registry import resolve_effect
from game_state.state import CardInstance, MatchFactory, Zone
from rules_engine.events import emit_event
from rules_engine.stack_engine import add_to_stack, resolve_top_of_stack


def test_creature_death_trigger_deals_its_power_as_damage() -> None:
    state = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Island"}],
        [{"quantity": 60, "card_name": "Island"}],
        seed=51,
    )
    source = CardInstance(
        id="butcher",
        name="Dreadhorde Butcher",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Creature"],
        power=3,
        toughness=1,
        oracle_text="When this creature dies, it deals damage equal to its power to any target.",
    )
    state.cards[source.id] = source
    state.players[1].battlefield.append(source.id)

    emit_event(state, "creature_dies", {"card_id": source.id, "controller": 1, "power": 3})

    trigger = next(item for item in state.stack if item.source_card_id == source.id)
    assert trigger.effect_key == "deal_damage"
    assert trigger.payload["amount"] == 3
    before = state.players[2].life
    resolve_effect(state, 1, trigger.effect_key, {**trigger.payload, "__source_card_id": source.id})
    assert state.players[2].life == before - 3


def test_enter_trigger_casts_target_instant_from_graveyard() -> None:
    state = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Island"}],
        [{"quantity": 60, "card_name": "Island"}],
        seed=52,
    )
    source = CardInstance(
        id="gearhulk",
        name="Torrential Gearhulk",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Artifact", "Creature"],
        oracle_text=(
            "Flash When this creature enters, you may cast target instant card "
            "from your graveyard without paying its mana cost."
        ),
    )
    instant = CardInstance(
        id="grave-instant",
        name="Opt",
        owner=1,
        controller=1,
        zone=Zone.GRAVEYARD,
        types=["Instant"],
        oracle_text="Draw a card.",
    )
    state.cards.update({source.id: source, instant.id: instant})
    state.players[1].battlefield.append(source.id)
    state.players[1].graveyard.append(instant.id)

    emit_event(state, "enters_battlefield", {"card_id": source.id, "controller": 1})

    trigger = next(item for item in state.stack if item.source_card_id == source.id)
    assert trigger.effect_key == "cast_from_graveyard"
    assert trigger.payload["target_card_id"] == instant.id


def test_hydroid_krasis_self_cast_trigger_resolves_before_x_creature_enters() -> None:
    state = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Island"}],
        [{"quantity": 60, "card_name": "Island"}],
        seed=53,
    )
    source = CardInstance(
        id="krasis",
        name="Hydroid Krasis",
        owner=1,
        controller=1,
        zone=Zone.STACK,
        types=["Creature"],
        power=0,
        toughness=0,
        oracle_text=(
            "When you cast this spell, you gain half X life and draw half X cards. "
            "Round down each time. Flying, trample This creature enters with X +1/+1 counters on it."
        ),
    )
    state.cards[source.id] = source
    state.players[1].library.extend([f"draw-{idx}" for idx in range(2)])
    for idx in range(2):
        state.cards[f"draw-{idx}"] = CardInstance(
            id=f"draw-{idx}",
            name="Draw Card",
            owner=1,
            controller=1,
            zone=Zone.LIBRARY,
        )
    before_life = state.players[1].life

    add_to_stack(state, source.id, 1, source.name, "noop", {"x_value": 4})
    assert len(state.stack) == 2
    assert state.stack[-1].payload["__trigger_event"] == "spell_cast"

    resolve_top_of_stack(state)
    assert state.players[1].life == before_life + 2
    assert source.zone == Zone.STACK
    assert len(state.players[1].hand) == 9

    resolve_top_of_stack(state)
    assert source.zone == Zone.BATTLEFIELD
    assert source.counters["+1/+1"] == 4
