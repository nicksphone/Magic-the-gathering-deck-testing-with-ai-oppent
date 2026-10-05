from __future__ import annotations

from game_state.state import CardInstance, MatchFactory, StackItem, Zone
from rules_engine.ability_model import build_ability_spec
from rules_engine.oracle_effects import inspect_target_hints
from rules_engine.targeting import validate_cast_targets
from rules_engine.stack_engine import resolve_top_of_stack
from effects.handlers import counter_spell


DROWN_ORACLE = (
    "Choose one —\n"
    "• Counter target spell with mana value less than or equal to the number of cards in its controller's graveyard.\n"
    "• Destroy target creature with mana value less than or equal to the number of cards in its controller's graveyard."
)


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


def test_fatal_push_mana_value_condition_does_not_filter_targets() -> None:
    import json
    from pathlib import Path
    raw = next(row for row in json.loads((Path(__file__).parent /
               'fixtures/resolution_conditions/seed-cards.json').read_text()) if row['name'] == 'Fatal Push')
    state = _state()
    small = CardInstance("small", "Small Creature", 2, 2, Zone.BATTLEFIELD, ["Creature"], mana_cost="{2}")
    large = CardInstance("large", "Large Creature", 2, 2, Zone.BATTLEFIELD, ["Creature"], mana_cost="{3}")
    _put_opponent_card(state, small)
    _put_opponent_card(state, large)
    spell = CardInstance(
        "spell", "Fatal Push", 1, 1, Zone.HAND, ["Instant"], mana_cost="{B}",
        oracle_text=raw['oracle_text'],
    )

    hints = inspect_target_hints(state, spell, 1)
    assert {item["id"] for item in hints["creature_targets"]} == {"small", "large"}


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
        oracle_text=DROWN_ORACLE,
    )

    spec = build_ability_spec(state, spell, 1)
    assert spec.used_fallback is False
    assert spec.modes
    selected = build_ability_spec(state, spell, 1, {"mode_text": spec.modes[0]})
    assert selected.effect.key == "counter_spell"


def test_drown_counter_target_tracks_opponent_graveyard_at_cast_and_resolution() -> None:
    state = _state()
    drown = CardInstance("drown", "Drown in the Loch", 1, 1, Zone.HAND, ["Instant"], mana_cost="{U}{B}", oracle_text=DROWN_ORACLE)
    target = CardInstance("negate", "Negate", 2, 2, Zone.STACK, ["Instant"], mana_cost="{1}{U}", oracle_text="Counter target noncreature spell.")
    state.cards[drown.id] = drown
    state.cards[target.id] = target
    state.stack.append(StackItem("negate-stack", target.id, 2, target.name, "counter_spell", {}))
    mode = build_ability_spec(state, drown, 1).modes[0]
    selected = build_ability_spec(state, drown, 1, {"mode_text": mode, "target_stack_id": "negate-stack"})
    assert selected.effect.payload["target_restrictions"] == {"mana_value_max_source": "controller_graveyard"}
    counter_spell(state, 1, selected.effect.payload)
    assert [item.id for item in state.stack] == ["negate-stack"]

    def target_ids() -> list[str]:
        hints = inspect_target_hints(state, drown, 1, {"mode_text": mode})
        return [item["id"] for item in hints["stack_targets"]]

    assert target_ids() == []
    for index in range(2):
        card = CardInstance(f"grave-{index}", "Island", 2, 2, Zone.GRAVEYARD, ["Land"])
        state.cards[card.id] = card
        state.players[2].graveyard.append(card.id)
    assert target_ids() == ["negate-stack"]

    drown.zone = Zone.STACK
    state.stack.append(StackItem(
        "drown-stack", drown.id, 1, drown.name, "counter_spell",
        {"target_stack_id": "negate-stack", "__announced_targets": {"mode_text": mode, "target_stack_id": "negate-stack"}},
    ))
    state.players[2].graveyard.pop()
    assert resolve_top_of_stack(state)
    assert [item.id for item in state.stack] == ["negate-stack"]
    assert target.zone == Zone.STACK


def test_drown_stack_target_counts_announced_x_in_mana_value() -> None:
    state = _state()
    drown = CardInstance("drown", "Drown in the Loch", 1, 1, Zone.HAND, ["Instant"], mana_cost="{U}{B}", oracle_text=DROWN_ORACLE)
    wastes = CardInstance("wastes", "Secure the Wastes", 2, 2, Zone.STACK, ["Instant"], mana_cost="{X}{W}", oracle_text="Create X 1/1 white Warrior creature tokens.")
    state.cards[drown.id] = drown
    state.cards[wastes.id] = wastes
    state.stack.append(StackItem("wastes-stack", wastes.id, 2, wastes.name, "create_token", {"x_value": 3}))
    for index in range(2):
        card = CardInstance(f"grave-{index}", "Island", 2, 2, Zone.GRAVEYARD, ["Land"])
        state.cards[card.id] = card
        state.players[2].graveyard.append(card.id)
    mode = build_ability_spec(state, drown, 1).modes[0]
    hints = inspect_target_hints(state, drown, 1, {"mode_text": mode})
    assert hints["stack_targets"] == []
    for index in range(2, 4):
        card = CardInstance(f"grave-{index}", "Island", 2, 2, Zone.GRAVEYARD, ["Land"])
        state.cards[card.id] = card
        state.players[2].graveyard.append(card.id)
    hints = inspect_target_hints(state, drown, 1, {"mode_text": mode})
    assert [item["id"] for item in hints["stack_targets"]] == ["wastes-stack"]
