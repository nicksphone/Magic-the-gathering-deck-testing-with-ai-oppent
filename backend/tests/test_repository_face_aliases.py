from __future__ import annotations

from sqlmodel import Session

from persistence.db import engine, init_db
from persistence.repository import Repository


def test_get_cached_card_by_name_matches_split_face_alias() -> None:
    init_db()
    with Session(engine) as session:
        repo = Repository(session)
        repo.upsert_card(
            {
                "scryfall_id": "test-delver-alias",
                "name": "Delver of Secrets // Insectile Aberration",
                "oracle_text": "",
                "mana_cost": "{U}",
                "type_line": "Creature — Human Wizard",
                "colors": "U",
                "power": "1",
                "toughness": "1",
                "image_uri": "/card-images/test-delver.jpg",
                "legalities_json": "{}",
            }
        )
        looked = repo.get_cached_card_by_name("Delver of Secrets")
        assert looked is not None
        assert "Delver of Secrets" in looked.name


def test_get_cached_cards_by_names_includes_split_face_front_name() -> None:
    init_db()
    with Session(engine) as session:
        repo = Repository(session)
        repo.upsert_card(
            {
                "scryfall_id": "test-delver-alias-2",
                "name": "Delver of Secrets // Insectile Aberration",
                "oracle_text": "",
                "mana_cost": "{U}",
                "type_line": "Creature — Human Wizard",
                "colors": "U",
                "power": "1",
                "toughness": "1",
                "image_uri": "/card-images/test-delver2.jpg",
                "legalities_json": "{}",
            }
        )
        by_names = repo.get_cached_cards_by_names(["Delver of Secrets"])
        assert "delver of secrets" in by_names
        assert by_names["delver of secrets"].name.startswith("Delver of Secrets")
