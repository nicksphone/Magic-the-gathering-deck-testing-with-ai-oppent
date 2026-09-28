from __future__ import annotations

from collections import Counter

from card_data.fallback_cards import fallback_card_payload
from decks.builtin_decks import BUILTIN_DECKS
from rules_engine.land_rules import apply_land_entry
from rules_engine.mana import _land_colors, parse_mana_cost


def test_every_builtin_has_land_sources_for_its_colored_spell_packages() -> None:
    for deck_name, deck_text in BUILTIN_DECKS.items():
        sources: Counter[str] = Counter()
        spell_copies: Counter[str] = Counter()
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
                for color in "WUBRG":
                    if cost[color]:
                        spell_copies[color] += count
        assert total == 60, deck_name
        for color, copies in spell_copies.items():
            minimum = max(4, (copies + 1) // 2)
            assert sources[color] >= minimum, f"{deck_name}: {copies} {color} spells have only {sources[color]} land sources"


def test_builtin_duals_produce_both_colors_without_conditional_entry() -> None:
    expected = {
        "Badlands": {"B", "R"},
        "Bayou": {"B", "G"},
        "Plateau": {"R", "W"},
        "Savannah": {"G", "W"},
        "Taiga": {"R", "G"},
        "Tropical Island": {"G", "U"},
        "Underground Sea": {"U", "B"},
        "Volcanic Island": {"U", "R"},
    }
    for name, colors in expected.items():
        card = fallback_card_payload(name)
        assert card is not None
        assert _land_colors(card["name"], card["type_line"], card["oracle_text"]) == colors
        entry = type("Land", (), {"name": name, "oracle_text": card["oracle_text"], "tapped": False})()
        apply_land_entry(entry)
        assert not entry.tapped
