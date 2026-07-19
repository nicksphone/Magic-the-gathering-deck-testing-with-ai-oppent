from effects.handlers import destroy_all_creatures, exile_permanent
from effects.registry import resolve_effect
from game_state.state import CardInstance, MatchFactory, Zone
from rules_engine.stack_engine import resolve_top_of_stack


def test_permanent_leaving_battlefield_trigger_uses_event_path() -> None:
    state = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Forest"}],
        [{"quantity": 60, "card_name": "Forest"}],
        seed=55,
    )
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    engine_card = CardInstance(
        "engine",
        "Leave Engine",
        1,
        1,
        Zone.BATTLEFIELD,
        ["Enchantment"],
        oracle_text="Whenever another permanent you control leaves the battlefield, draw a card.",
        type_line="Enchantment",
    )
    target = CardInstance("target", "Bear", 1, 1, Zone.BATTLEFIELD, ["Creature"], type_line="Creature — Bear")
    state.cards[engine_card.id] = engine_card
    state.cards[target.id] = target
    state.players[1].battlefield.extend([engine_card.id, target.id])
    before_hand = len(state.players[1].hand)

    exile_permanent(state, 1, {"target_card_id": target.id})

    assert target.zone == Zone.EXILE
    assert state.stack
    assert state.stack[-1].effect_key == "draw_cards"
    resolve_top_of_stack(state)
    assert len(state.players[1].hand) == before_hand + 1


def test_mass_destroy_emits_leaves_battlefield_event_before_moving_creature() -> None:
    state = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Forest"}],
        [{"quantity": 60, "card_name": "Forest"}],
        seed=56,
    )
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    engine_card = CardInstance(
        "engine-mass",
        "Leave Engine",
        1,
        1,
        Zone.BATTLEFIELD,
        ["Enchantment"],
        oracle_text="Whenever another permanent you control leaves the battlefield, draw a card.",
        type_line="Enchantment",
    )
    target = CardInstance("target-mass", "Bear", 1, 1, Zone.BATTLEFIELD, ["Creature"], type_line="Creature — Bear")
    state.cards[engine_card.id] = engine_card
    state.cards[target.id] = target
    state.players[1].battlefield.extend([engine_card.id, target.id])
    before_hand = len(state.players[1].hand)

    destroy_all_creatures(state, 1, {})

    assert target.zone == Zone.GRAVEYARD
    assert state.stack
    assert state.stack[-1].effect_key == "draw_cards"
    resolve_top_of_stack(state)
    assert len(state.players[1].hand) == before_hand + 1


def test_mass_leave_trigger_with_one_or_more_fires_once_for_the_batch() -> None:
    state = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Forest"}],
        [{"quantity": 60, "card_name": "Forest"}],
        seed=57,
    )
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    engine_card = CardInstance(
        "batch-engine",
        "Batch Leave Engine",
        1,
        1,
        Zone.BATTLEFIELD,
        ["Enchantment"],
        oracle_text="Whenever one or more creatures you control leave the battlefield, draw a card.",
        type_line="Enchantment",
    )
    state.cards[engine_card.id] = engine_card
    state.players[1].battlefield.append(engine_card.id)
    for index in range(2):
        target = CardInstance(
            f"batch-target-{index}",
            f"Bear {index}",
            1,
            1,
            Zone.BATTLEFIELD,
            ["Creature"],
            type_line="Creature - Bear",
        )
        state.cards[target.id] = target
        state.players[1].battlefield.append(target.id)

    before_hand = len(state.players[1].hand)
    destroy_all_creatures(state, 1, {})

    assert len(state.stack) == 1
    resolve_top_of_stack(state)
    assert len(state.players[1].hand) == before_hand + 1
