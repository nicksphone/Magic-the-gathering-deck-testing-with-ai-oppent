from game_state.state import CardInstance, MatchFactory, StackItem, Step, Zone
from effects.handlers import counter_spell_unless_pay
from rules_engine.oracle_effects import infer_effect_from_oracle, inspect_target_hints


def _state_with_stack(target_types: list[str], target_oracle: str = ""):
    state = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Island"}],
        [{"quantity": 60, "card_name": "Island"}],
        seed=7,
    )
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    for _ in range(2):
        land_id = state.players[2].library.pop()
        state.players[2].battlefield.append(land_id)
        state.cards[land_id].zone = Zone.BATTLEFIELD
        state.cards[land_id].summoning_sick = False
    target_id = "target-spell"
    state.cards[target_id] = CardInstance(
        id=target_id,
        name="Target Spell",
        owner=2,
        controller=2,
        zone=Zone.STACK,
        types=target_types,
        mana_cost="{2}",
        oracle_text=target_oracle,
    )
    state.stack.append(
        StackItem(
            id="target-stack",
            source_card_id=target_id,
            controller=2,
            label="Target Spell",
            effect_key="noop",
            payload={},
        )
    )
    return state


def _spell_pierce(state):
    return CardInstance(
        id="pierce",
        name="Spell Pierce",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Instant"],
        mana_cost="{U}",
        oracle_text="Counter target noncreature spell unless its controller pays {2}.",
    )


def test_spell_pierce_is_structured_and_filters_creature_spells() -> None:
    state = _state_with_stack(["Creature"])
    card = _spell_pierce(state)

    effect_key, payload = infer_effect_from_oracle(
        state, card, 1, {"target_stack_id": "target-stack"}
    )
    hints = inspect_target_hints(state, card, 1)

    assert effect_key == "counter_spell_unless_pay"
    assert payload["unless_cost"] == "{2}"
    assert hints["stack_targets"] == []
    assert hints["unless_payment"]["choice_key"] == "pay_unless_counter"


def test_spell_pierce_target_can_pay_and_keep_spell_on_stack() -> None:
    state = _state_with_stack(["Sorcery"], "Draw a card.")
    lands = state.players[2].battlefield
    for cid in lands[:2]:
        state.cards[cid].tapped = False
    counter_spell_unless_pay(
        state,
        1,
        {
            "target_stack_id": "target-stack",
            "unless_cost": "{2}",
            "pay_unless_counter": True,
        },
    )

    assert len(state.stack) == 1
    assert sum(card.tapped for card in (state.cards[cid] for cid in lands[:2])) == 2
    assert any("pays {2}" in line for line in state.log)


def test_spell_pierce_counters_when_target_declines_payment() -> None:
    state = _state_with_stack(["Sorcery"], "Draw a card.")
    counter_spell_unless_pay(
        state,
        1,
        {
            "target_stack_id": "target-stack",
            "unless_cost": "{2}",
            "pay_unless_counter": False,
        },
    )

    assert state.stack == []
    assert "target-spell" in state.players[2].graveyard


def test_spell_pierce_cannot_counter_an_uncounterable_spell() -> None:
    state = _state_with_stack(["Sorcery"], "This spell can't be countered.")
    counter_spell_unless_pay(
        state,
        1,
        {
            "target_stack_id": "target-stack",
            "unless_cost": "{2}",
            "pay_unless_counter": False,
        },
    )

    assert len(state.stack) == 1
    assert any("can't be countered" in line for line in state.log)
