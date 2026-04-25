from __future__ import annotations

from game_state.state import CardInstance, MatchFactory, Zone
from rules_engine.cast_choice import enrich_divide_total
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


def test_planeswalker_cast_does_not_require_x_value_from_loyalty_text() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    card = CardInstance(
        id="ugin",
        name="Ugin, the Spirit Dragon",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Planeswalker"],
        mana_cost="{8}",
        oracle_text="+2: Ugin, the Spirit Dragon deals 3 damage to any target.\n-X: Exile each permanent with mana value X or less that's one or more colors.\n-10: You gain 7 life and draw seven cards.",
    )
    hints = inspect_target_hints(state, card, 1)
    assert hints.get("requires_x_value") is not True


def test_memory_deluge_does_not_require_x_value_for_cast() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    card = CardInstance(
        id="deluge",
        name="Memory Deluge",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Instant"],
        mana_cost="{2}{U}{U}",
        oracle_text="Look at the top X cards of your library, where X is the amount of mana spent to cast this spell.",
    )
    hints = inspect_target_hints(state, card, 1)
    assert hints.get("requires_x_value") is not True


def test_shark_typhoon_does_not_require_x_value_for_cast() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    card = CardInstance(
        id="shark",
        name="Shark Typhoon",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Enchantment"],
        mana_cost="{5}{U}",
        oracle_text="Cycling {X}{1}{U}. When you cycle Shark Typhoon, create an X/X blue Shark creature token with flying.",
    )
    hints = inspect_target_hints(state, card, 1)
    assert hints.get("requires_x_value") is not True


def test_non_divide_x_spell_does_not_auto_set_divide_total() -> None:
    card = CardInstance(
        id="march",
        name="March of Otherworldly Light",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Instant"],
        mana_cost="{X}{W}",
        oracle_text="Exile target artifact, creature, or enchantment with mana value X or less.",
    )
    targets = enrich_divide_total(card, {"x_value": 3, "target_card_id": "c1"})
    assert "divide_total" not in targets
