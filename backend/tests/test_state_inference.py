from __future__ import annotations

from game_state.state import _infer_types
from rules_engine.mana import can_pay_with_pool_and_lands
from game_state.state import MatchFactory, Zone


def test_control_ramp_name_fallback_types_are_not_misclassified_as_creatures() -> None:
    assert _infer_types("Hallowed Fountain") == ["Land"]
    assert _infer_types("Growth Spiral") == ["Instant"]
    assert _infer_types("Migration Path") == ["Sorcery"]
    assert _infer_types("March of Otherworldly Light") == ["Instant"]
    assert _infer_types("Shark Typhoon") == ["Enchantment"]


def test_named_dual_land_without_type_line_still_provides_expected_colors() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    p1 = state.players[1]
    p1.battlefield = []
    for _ in range(2):
        cid = p1.library.pop()
        p1.battlefield.append(cid)
        card = state.cards[cid]
        card.zone = Zone.BATTLEFIELD
        card.types = ["Land"]
        card.name = "Hallowed Fountain"
        card.type_line = ""
        card.oracle_text = ""
        card.tapped = False

    assert can_pay_with_pool_and_lands(state, 1, "{W}{U}") is True
