from __future__ import annotations

import json
from dataclasses import dataclass

from sqlmodel import Session as SqlSession, SQLModel, create_engine

from decks import bootstrap
from decks.expansion_top_decks import EXPANSION_TOP_DECKS
from persistence.repository import Repository


@dataclass
class DeckRow:
    id: int
    name: str
    source: str
    mainboard_json: str


class Session:
    def __init__(self) -> None:
        self.added: list[DeckRow] = []
        self.commits = 0

    def add(self, row: DeckRow) -> None:
        self.added.append(row)

    def commit(self) -> None:
        self.commits += 1


class Repo:
    def __init__(self, rows: list[DeckRow]) -> None:
        self.rows = rows
        self.session = Session()

    def list_decks(self) -> list[DeckRow]:
        return self.rows


def test_saved_expansion_templates_refresh_in_place_without_touching_user_decks(monkeypatch) -> None:
    ramp_entry = next(item for item in EXPANSION_TOP_DECKS if item["code"] == "USG")
    aggro_entry = next(item for item in EXPANSION_TOP_DECKS if item["code"] == "LEA")
    monkeypatch.setattr(bootstrap, "EXPANSION_TOP_DECKS", [ramp_entry, aggro_entry])
    current_ramp = [{"quantity": 4, "card_name": "Tropical Island"}]
    old_ramp = [{"quantity": 4, "card_name": "Forest"}]
    aggro = [{"quantity": 20, "card_name": "Mountain"}]
    stale = DeckRow(31, ramp_entry["deck_name"], "expansion_top:USG", json.dumps(old_ramp))
    unchanged = DeckRow(32, aggro_entry["deck_name"], "expansion_top:LEA", json.dumps(aggro))
    user = DeckRow(33, "My Ramp", "user", json.dumps(old_ramp))
    repo = Repo([
        DeckRow(1, "Ramp", "builtin", json.dumps(current_ramp)),
        DeckRow(2, "Mono Red Aggro", "builtin", json.dumps(aggro)),
        stale, unchanged, user,
    ])

    bootstrap.ensure_expansion_top_decks(repo)  # type: ignore[arg-type]

    assert stale.id == 31 and json.loads(stale.mainboard_json) == current_ramp
    assert repo.session.added == [stale]
    assert repo.session.commits == 1
    assert json.loads(user.mainboard_json) == old_ramp

    bootstrap.ensure_expansion_top_decks(repo)  # type: ignore[arg-type]
    assert repo.session.commits == 1


def test_template_refresh_preserves_real_sqlite_deck_ids(tmp_path, monkeypatch) -> None:
    ramp_entry = next(item for item in EXPANSION_TOP_DECKS if item["code"] == "USG")
    monkeypatch.setattr(bootstrap, "BUILTIN_DECKS", {"Ramp": ramp_entry["deck_text"]})
    monkeypatch.setattr(bootstrap, "EXPANSION_TOP_DECKS", [ramp_entry])
    db = create_engine(f"sqlite:///{tmp_path / 'decks.sqlite'}")
    SQLModel.metadata.create_all(db)
    old = [{"quantity": 60, "card_name": "Forest"}]
    with SqlSession(db) as session:
        repo = Repository(session)
        builtin = repo.save_deck("Ramp", "builtin", old, [], "Ramp")
        expansion = repo.save_deck(ramp_entry["deck_name"], "expansion_top:USG", old, [], "Ramp")
        user = repo.save_deck("My Ramp", "user", old, [], "Ramp")
        ids = {"builtin": builtin.id, "expansion_top:USG": expansion.id, "user": user.id}

        bootstrap.ensure_builtin_decks(repo)
        bootstrap.ensure_expansion_top_decks(repo)
        rows = {row.source: row for row in repo.list_decks()}
        assert {source: row.id for source, row in rows.items()} == ids
        assert any(item["card_name"] == "Tropical Island" for item in json.loads(rows["builtin"].mainboard_json))
        assert json.loads(rows["builtin"].mainboard_json) == json.loads(rows["expansion_top:USG"].mainboard_json)
        assert json.loads(rows["user"].mainboard_json) == old
