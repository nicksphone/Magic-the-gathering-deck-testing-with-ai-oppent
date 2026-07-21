from __future__ import annotations

from game_state.state import CardInstance, MatchFactory, Zone
from rules_engine.ability_model import build_ability_spec


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
    card = CardInstance(
        id="nissa",
        name="Nissa, Who Shakes the World",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Planeswalker"],
        oracle_text=(
            "Lands you control have '{T}: Add two mana of any one color.'\n"
            "+1: Put a +1/+1 counter on up to one target land you control.\n"
            "-3: You may put a green creature card from your hand onto the battlefield."
        ),
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
