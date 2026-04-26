from __future__ import annotations

from decks.expansion_top_decks import EXPANSION_TOP_DECKS, EXPANSION_TOP_DECKS_BY_CODE


def test_expansion_top_deck_codes_are_unique() -> None:
    codes = [d["code"] for d in EXPANSION_TOP_DECKS]
    assert len(codes) == len(set(codes))


def test_expansion_top_lookup_map_matches_catalog_size() -> None:
    assert len(EXPANSION_TOP_DECKS_BY_CODE) == len(EXPANSION_TOP_DECKS)


def test_expansion_top_entries_have_deck_text() -> None:
    assert len(EXPANSION_TOP_DECKS) >= 40
    for item in EXPANSION_TOP_DECKS:
        text = (item.get("deck_text") or "").strip()
        assert text
        assert "\n" in text
