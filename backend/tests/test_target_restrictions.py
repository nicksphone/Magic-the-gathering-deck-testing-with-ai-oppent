from __future__ import annotations

from game_state.state import CardInstance, MatchFactory, Zone
from rules_engine.ability_model import build_ability_spec
from rules_engine.oracle_effects import inspect_target_hints
from rules_engine.targeting import validate_cast_targets


def _state() -> object:
    return MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Plains", "type_line": "Basic Land - Plains", "oracle_text": "{T}: Add {W}."}],
        [{"quantity": 60, "card_name": "Island", "type_line": "Basic Land - Island", "oracle_text": "{T}: Add {U}."}],
        seed=19,
    )


def _put_opponent_card(state, card: CardInstance) -> None:
    state.cards[card.id] = card
    state.players[2].battlefield.append(card.id)


def test_nonartifact_restriction_filters_creature_targets() -> None:
    state = _state()
    artifact = CardInstance("artifact", "Artifact Creature", 2, 2, Zone.BATTLEFIELD, ["Artifact", "Creature"], mana_cost="{1}")
    creature = CardInstance("creature", "Normal Creature", 2, 2, Zone.BATTLEFIELD, ["Creature"], mana_cost="{2}")
    _put_opponent_card(state, artifact)
    _put_opponent_card(state, creature)
    spell = CardInstance(
        "spell", "Go for the Throat", 1, 1, Zone.HAND, ["Instant"], mana_cost="{1}{B}",
        oracle_text="Destroy target nonartifact creature.",
    )

    hints = inspect_target_hints(state, spell, 1)
    ids = {item["id"] for item in hints["creature_targets"]}
    assert ids == {"creature"}
    assert validate_cast_targets(hints, {"target_card_id": "artifact"})[0] is False
    assert validate_cast_targets(hints, {"target_card_id": "creature"})[0] is True


def test_static_mana_value_restriction_filters_targets() -> None:
    state = _state()
    small = CardInstance("small", "Small Creature", 2, 2, Zone.BATTLEFIELD, ["Creature"], mana_cost="{2}")
    large = CardInstance("large", "Large Creature", 2, 2, Zone.BATTLEFIELD, ["Creature"], mana_cost="{3}")
    _put_opponent_card(state, small)
    _put_opponent_card(state, large)
    spell = CardInstance(
        "spell", "Fatal Push", 1, 1, Zone.HAND, ["Instant"], mana_cost="{B}",
        oracle_text="Destroy target creature if it has mana value 2 or less.",
    )

    hints = inspect_target_hints(state, spell, 1)
    assert {item["id"] for item in hints["creature_targets"]} == {"small"}


def test_controlled_type_restriction_uses_current_battlefield_count() -> None:
    state = _state()
    state.players[1].battlefield.clear()
    for index in range(2):
        land = CardInstance(f"plains-{index}", "Plains", 1, 1, Zone.BATTLEFIELD, ["Land"], type_line="Basic Land - Plains")
        state.cards[land.id] = land
        state.players[1].battlefield.append(land.id)
    small = CardInstance("small", "Two Drop", 2, 2, Zone.BATTLEFIELD, ["Creature"], mana_cost="{2}")
    large = CardInstance("large", "Three Drop", 2, 2, Zone.BATTLEFIELD, ["Creature"], mana_cost="{3}")
    _put_opponent_card(state, small)
    _put_opponent_card(state, large)
    spell = CardInstance(
        "spell", "Lay Down Arms", 1, 1, Zone.HAND, ["Sorcery"], mana_cost="{W}",
        oracle_text="Exile target creature with mana value less than or equal to the number of Plains you control.",
    )

    hints = inspect_target_hints(state, spell, 1)
    assert {item["id"] for item in hints["creature_targets"]} == {"small"}


def test_modal_counter_mode_is_structured_before_stack_target_exists() -> None:
    state = _state()
    spell = CardInstance(
        "spell", "Drown in the Loch", 1, 1, Zone.HAND, ["Instant"], mana_cost="{U}{B}",
        oracle_text=(
            "Choose one -\n"
            "Counter target spell with mana value less than or equal to the number of cards in its controller's graveyard.\n"
            "Destroy target creature with mana value less than or equal to the number of cards in its controller's graveyard."
        ),
    )

    spec = build_ability_spec(state, spell, 1)
    assert spec.used_fallback is False
    assert spec.modes
    selected = build_ability_spec(state, spell, 1, {"mode_text": spec.modes[0]})
    assert selected.effect.key == "counter_spell"

