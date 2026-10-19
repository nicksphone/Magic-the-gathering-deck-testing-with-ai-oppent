from tests.rules_printed_facts_e4 import canonical_card, canonical_deck_entry, raw_card, set_printed
from effects.registry import resolve_effect
from game_state.state import CardInstance, MatchFactory, Zone
from rules_engine.events import emit_event
from rules_engine.stack_engine import add_to_stack, resolve_top_of_stack


def test_creature_death_trigger_deals_its_power_as_damage() -> None:
    state = MatchFactory.from_decks(
        [canonical_deck_entry('Island', 60)],
        [canonical_deck_entry('Island', 60)],
        seed=51,
    )
    source = canonical_card("Dreadhorde Butcher", id="butcher", owner=1, controller=1, zone=Zone.BATTLEFIELD, counters={'__eot_power': 2})
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
        [canonical_deck_entry('Island', 60)],
        [canonical_deck_entry('Island', 60)],
        seed=52,
    )
    source = canonical_card("Torrential Gearhulk", id="gearhulk", owner=1, controller=1, zone=Zone.BATTLEFIELD)
    instant = canonical_card("Opt", id="grave-instant", owner=1, controller=1, zone=Zone.GRAVEYARD)
    state.cards.update({source.id: source, instant.id: instant})
    state.players[1].battlefield.append(source.id)
    state.players[1].graveyard.append(instant.id)

    emit_event(state, "enters_battlefield", {"card_id": source.id, "controller": 1})

    trigger = next(item for item in state.stack if item.source_card_id == source.id)
    assert trigger.effect_key == "cast_from_graveyard"
    assert trigger.payload["target_card_id"] == instant.id


def test_hydroid_krasis_self_cast_trigger_resolves_before_x_creature_enters() -> None:
    state = MatchFactory.from_decks(
        [canonical_deck_entry('Island', 60)],
        [canonical_deck_entry('Island', 60)],
        seed=53,
    )
    source = canonical_card("Hydroid Krasis", id="krasis", owner=1, controller=1, zone=Zone.STACK)
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
