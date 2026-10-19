from __future__ import annotations

import json

from game_state.state import CardInstance, MatchFactory, Zone, _infer_keywords
from rules_engine.ability_model import build_ability_spec
from rules_engine.card_types import printed_card_types
from tests.canonical_positive_fixtures import cached_card


def test_ability_model_exposes_effect_targets_modes_and_choices() -> None:
    state = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Island", "type_line": "Basic Land — Island"}],
        [{"quantity": 60, "card_name": "Island", "type_line": "Basic Land — Island"}],
        seed=4,
    )
    card = CardInstance(
        id="bolt", name="Test Bolt", owner=1, controller=1, zone=Zone.HAND,
        types=["Instant"], mana_cost="{R}", oracle_text="Deal 3 damage to any target.",
    )
    state.cards[card.id] = card
    spec = build_ability_spec(state, card, 1, {"target_player": 2})

    assert spec.source_card_id == "bolt"
    assert spec.effect.key == "deal_damage"
    assert spec.effect.payload["target_player"] == 2
    assert spec.choices["target_player"] == 2
    assert not spec.used_fallback


def test_ability_model_marks_unparsed_action_text_as_fallback() -> None:
    state = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Island", "type_line": "Basic Land — Island"}],
        [{"quantity": 60, "card_name": "Island", "type_line": "Basic Land — Island"}],
        seed=5,
    )
    card = CardInstance(
        id="unknown", name="Unknown Relic", owner=1, controller=1, zone=Zone.HAND,
        types=["Artifact"], mana_cost="{2}", oracle_text="Perform a complicated historical action.",
    )
    state.cards[card.id] = card
    spec = build_ability_spec(state, card, 1)

    assert spec.effect.key == "noop"
    assert spec.used_fallback


def test_planeswalker_static_and_loyalty_text_is_not_cast_time_fallback() -> None:
    state = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Island", "type_line": "Basic Land - Island"}],
        [{"quantity": 60, "card_name": "Island", "type_line": "Basic Land - Island"}],
    )
    printed = cached_card("Nissa, Who Shakes the World")
    card = CardInstance(
        id="nissa",
        name=printed.name,
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=printed_card_types(printed.type_line),
        type_line=printed.type_line,
        oracle_text=printed.oracle_text,
        mana_cost=printed.mana_cost,
        power=int(printed.power) if printed.power is not None else None,
        toughness=int(printed.toughness) if printed.toughness is not None else None,
        printed_power=printed.power,
        printed_toughness=printed.toughness,
        loyalty=int(printed.loyalty) if printed.loyalty is not None else None,
        colors=printed.colors.split(",") if printed.colors else [],
        keywords=_infer_keywords(printed.oracle_text),
        layout=printed.layout,
        card_faces=json.loads(printed.card_faces_json),
        image_uri=printed.image_uri,
    )

    spec = build_ability_spec(state, card, 1)

    assert spec.effect.key == "noop"
    assert not spec.used_fallback


def test_event_layer_patterns_are_not_reported_as_cast_parser_fallbacks() -> None:
    state = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Island"}],
        [{"quantity": 60, "card_name": "Island"}],
    )
    for index, oracle in enumerate(
        (
            "At the beginning of your upkeep, look at the top card of your library. If an instant or sorcery card is revealed this way, transform this creature.",
            "Whenever you cast a noncreature spell, put a +1/+1 counter on this creature.",
            "If a source you control would deal noncombat damage to a creature an opponent controls, put that many -1/-1 counters on that creature instead.",
        )
    ):
        card = CardInstance(
            id=f"event-{index}", name="Event Permanent", owner=1, controller=1,
            zone=Zone.BATTLEFIELD, types=["Creature"], oracle_text=oracle,
        )
        spec = build_ability_spec(state, card, 1)
        assert spec.effect.key == "noop"
        assert not spec.used_fallback
