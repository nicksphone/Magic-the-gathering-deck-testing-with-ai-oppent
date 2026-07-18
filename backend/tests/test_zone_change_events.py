from effects.handlers import exile_permanent
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
