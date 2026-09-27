from __future__ import annotations

from sqlmodel import Session
from sqlmodel import SQLModel, create_engine

from persistence.db import engine, init_db
from persistence.repository import Repository
from card_data.hydration import hydrate_deck_cards
from game_state.state import MatchFactory


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


def test_exact_basic_land_beats_art_series_face_alias(tmp_path) -> None:
    local_engine = create_engine(f"sqlite:///{tmp_path / 'alias.db'}")
    SQLModel.metadata.create_all(local_engine)
    with Session(local_engine) as session:
        repo = Repository(session)
        repo.upsert_card({
            "scryfall_id": "canonical-mountain", "name": "Mountain",
            "type_line": "Basic Land \u2014 Mountain", "oracle_text": "({T}: Add {R}.)",
        })
        repo.upsert_card({
            "scryfall_id": "canonical-mountain-art", "name": "Mountain // Mountain",
            "type_line": "Card", "layout": "art_series", "oracle_text": "",
        })
        bulk = repo.get_cached_cards_by_names(["Mountain"])
        assert bulk["mountain"].name == "Mountain"
        hydrated = hydrate_deck_cards(repo, [{"quantity": 60, "card_name": "Mountain"}])
        assert hydrated[0]["type_line"] == "Basic Land \u2014 Mountain"
        game = MatchFactory.from_decks(hydrated, hydrated, seed=4)
        assert all(card.types == ["Land"] for card in game.cards.values())
        assert repo.get_cached_card_by_name("Mountain").name == "Mountain"
        session.delete(bulk["mountain"])
        session.commit()
        assert repo.get_cached_card_by_name("Mountain") is None
        assert "mountain" not in repo.get_cached_cards_by_names(["Mountain"])
