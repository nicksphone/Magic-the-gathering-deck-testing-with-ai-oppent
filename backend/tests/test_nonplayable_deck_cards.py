"""Auxiliary Scryfall art/token objects are not sixty-card deck cards."""
from fastapi.testclient import TestClient
from sqlmodel import Session

from card_data.hydration import is_playable_deck_card
from main import ACTIVE_MATCHES, app
from persistence.db import engine
from persistence.repository import Repository


def test_nonplayable_layouts_do_not_exclude_real_transform_cards():
    assert not is_playable_deck_card({"layout": "token", "type_line": "Token Creature - Goblin"})
    assert not is_playable_deck_card({"layout": "emblem", "type_line": "Emblem"})
    assert not is_playable_deck_card({"layout": "art_series", "type_line": "Card"})
    assert is_playable_deck_card({"layout": "transform", "type_line": "Enchantment - Saga"})
    assert is_playable_deck_card({"layout": "normal", "type_line": "Basic Land - Mountain"})


def test_art_series_card_is_reported_on_import_and_rejected_at_match_start():
    with TestClient(app) as client:
        with Session(engine) as session:
            Repository(session).upsert_card({
                "scryfall_id": "oracle-art-series-mountain", "name": "Mountain // Mountain",
                "layout": "art_series", "type_line": "Card", "oracle_text": "",
                "mana_cost": "", "image_uri": "/card-images/art-series-mountain.jpg",
            })
        imported = client.post("/decks/import", json={
            "name": "Art series is not a deck", "deck_text": "60 Mountain // Mountain",
        })
        assert imported.status_code == 200
        assert imported.json()["deck_id"] is None
        assert any("not a playable" in error.lower() for error in imported.json()["errors"])
        before = set(ACTIVE_MATCHES)
        started = client.post("/matches/start", json={
            "deck_a": [{"quantity": 60, "card_name": "Mountain // Mountain"}],
            "deck_b": [{"quantity": 60, "card_name": "Mountain // Mountain"}],
        })
        assert started.status_code == 422
        assert started.json()["detail"]["code"] == "nonplayable_card"
        assert set(ACTIVE_MATCHES) == before
