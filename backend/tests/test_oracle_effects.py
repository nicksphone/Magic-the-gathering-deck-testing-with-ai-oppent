from __future__ import annotations

from game_state.state import CardInstance, MatchFactory, Zone
from rules_engine.oracle_effects import infer_effect_from_oracle


def test_oracle_damage_parsing() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    card = CardInstance(
        id="x",
        name="Lightning Bolt",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Instant"],
        oracle_text="Lightning Bolt deals 3 damage to any target.",
    )
    effect_key, payload = infer_effect_from_oracle(state, card, 1)
    assert effect_key == "deal_damage"
    assert payload["amount"] == 3


def test_oracle_counterspell_parsing() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.stack.append(type("SI", (), {"id": "stack-1"})())
    card = CardInstance(
        id="c",
        name="Counterspell",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Instant"],
        oracle_text="Counter target spell.",
    )
    effect_key, payload = infer_effect_from_oracle(state, card, 1)
    assert effect_key == "counter_spell"
    assert payload["target_stack_id"] == "stack-1"


def test_oracle_multiclause_sequence_parsing() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    card = CardInstance(
        id="m",
        name="Cruel Insight",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Sorcery"],
        oracle_text="Target player loses 2 life. You gain 2 life. Draw a card.",
    )
    effect_key, payload = infer_effect_from_oracle(state, card, 1, action_targets={"target_player": 2})
    assert effect_key == "effect_sequence"
    effects = payload["effects"]
    assert [x["effect_key"] for x in effects] == ["lose_life", "gain_life", "draw_cards"]
    assert effects[0]["payload"]["target_player"] == 2
    assert effects[0]["payload"]["amount"] == 2
    assert effects[1]["payload"]["amount"] == 2


def test_oracle_add_counters_parsing() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    target = state.players[1].battlefield[0] if state.players[1].battlefield else state.players[1].hand[0]
    card = CardInstance(
        id="counters",
        name="Growth Pattern",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Sorcery"],
        oracle_text="Put two +1/+1 counters on target creature.",
    )
    effect_key, payload = infer_effect_from_oracle(state, card, 1, action_targets={"target_card_id": target})
    assert effect_key == "add_counters"
    assert payload["target_card_id"] == target
    assert payload["amount"] == 2
