from __future__ import annotations

from game_state.state import CardInstance, MatchFactory, Zone
from rules_engine.oracle_effects import infer_effect_from_oracle, inspect_target_hints


def test_mode_and_x_hints_exposed() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    card = CardInstance(
        id="x",
        name="Modal X",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Sorcery"],
        mana_cost="{X}{R}",
        oracle_text="Choose one — Modal X deals X damage to any target; Draw X cards.",
    )
    hints = inspect_target_hints(state, card, 1)
    assert hints.get("modes")
    assert hints.get("requires_x_value") is True


def test_x_mode_inference_respects_selected_mode_and_x() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    card = CardInstance(
        id="x",
        name="Modal X",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Sorcery"],
        mana_cost="{X}{R}",
        oracle_text="Choose one — Modal X deals X damage to any target; Draw X cards.",
    )
    effect, payload = infer_effect_from_oracle(state, card, 1, action_targets={"mode_text": "Draw X cards", "x_value": 3})
    assert effect == "draw_cards"
    assert payload["amount"] == 3
