from __future__ import annotations

from decks.expansion_top_decks import EXPANSION_TOP_DECKS, EXPANSION_TOP_DECKS_BY_CODE
from fastapi.testclient import TestClient

from main import app


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


def test_catalog_does_not_present_templates_as_tournament_decks() -> None:
    for item in EXPANSION_TOP_DECKS:
        if item["kind"] == "archetype_template":
            assert "Template" in item["deck_name"]
            assert item["decklist_source_url"] is None
            assert item["event_source_url"] is None
        else:
            assert item["kind"] == "tournament"
            assert item["decklist_source_url"]
            assert item["event_source_url"]
            assert item["format"] and item["player_name"] and item["finish"]


def test_otj_winning_tournament_list_has_60_plus_15_cards() -> None:
    item = EXPANSION_TOP_DECKS_BY_CODE["OTJ"]
    main, side = item["deck_text"].split("Sideboard:")
    count = lambda text: sum(int(line.split()[0]) for line in text.splitlines() if line.strip())
    assert count(main) == 60
    assert count(side) == 15
    assert item["kind"] == "tournament"


def test_expansion_api_exposes_tournament_provenance_and_template_warning() -> None:
    with TestClient(app) as client:
        catalog = client.get("/decks/expansion-top")
        tournament = client.get("/decks/expansion-top/OTJ")
        template = client.get("/decks/expansion-top/LEA")
    assert catalog.status_code == tournament.status_code == template.status_code == 200
    assert next(item for item in catalog.json() if item["code"] == "OTJ")["kind"] == "tournament"
    assert tournament.json()["decklist_source_url"] == EXPANSION_TOP_DECKS_BY_CODE["OTJ"]["decklist_source_url"]
    assert tournament.json()["event_source_url"] == EXPANSION_TOP_DECKS_BY_CODE["OTJ"]["event_source_url"]
    assert template.json()["kind"] == "archetype_template"
    assert template.json()["decklist_source_url"] is None
