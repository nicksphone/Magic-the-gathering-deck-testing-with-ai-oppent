from __future__ import annotations

from collections import Counter

from card_data.fallback_cards import fallback_card_payload
from decks.builtin_decks import BUILTIN_DECKS
from rules_engine.land_rules import apply_land_entry
from rules_engine.mana import _land_colors, parse_mana_cost


def test_every_builtin_has_sources_for_its_printed_spell_colors() -> None:
    for deck_name, deck_text in BUILTIN_DECKS.items():
        sources: Counter[str] = Counter()
        required: set[str] = set()
        total = 0
        for line in deck_text.splitlines():
            if not line.strip():
                continue
            quantity, card_name = line.strip().split(" ", 1)
            count = int(quantity)
            total += count
            card = fallback_card_payload(card_name)
            assert card is not None, f"{deck_name}: no offline data for {card_name}"
            if not card["type_line"].startswith("Basic Land"):
                assert count <= 4, f"{deck_name}: more than four {card_name}"
            if "Land" in card["type_line"].split(" — ", 1)[0]:
                for color in _land_colors(card["name"], card["type_line"], card["oracle_text"]):
                    sources[color] += count
            else:
                cost = parse_mana_cost(card.get("mana_cost", ""))
                required.update(color for color in "WUBRG" if cost[color])
        assert total == 60, deck_name
        for color in required:
            assert sources[color] >= 4, f"{deck_name}: {color} spells have only {sources[color]} land sources"


def test_builtin_duals_produce_both_colors_without_conditional_entry() -> None:
    expected = {
        "Badlands": {"B", "R"},
        "Bayou": {"B", "G"},
        "Savannah": {"G", "W"},
        "Tropical Island": {"G", "U"},
        "Underground Sea": {"U", "B"},
    }
    for name, colors in expected.items():
        card = fallback_card_payload(name)
        assert card is not None
        assert _land_colors(card["name"], card["type_line"], card["oracle_text"]) == colors
        entry = type("Land", (), {"name": name, "oracle_text": card["oracle_text"], "tapped": False})()
        apply_land_entry(entry)
        assert not entry.tapped
