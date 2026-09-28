from __future__ import annotations

from dataclasses import dataclass
import json

import main


@dataclass
class _DeckRow:
    id: int
    name: str
    source: str
    mainboard_json: str
    sideboard_json: str = "[]"


class _FakeSession:
    def __init__(self) -> None:
        self.added: list[_DeckRow] = []
        self.committed = 0

    def add(self, row: _DeckRow) -> None:
        self.added.append(row)

    def commit(self) -> None:
        self.committed += 1


class _FakeRecord:
    def __init__(self, record_id: int) -> None:
        self.id = record_id


class _FakeRepo:
    def __init__(self) -> None:
        self.session = _FakeSession()
        self._rows = [_DeckRow(74, "Ramp", "builtin", json.dumps([{"quantity": 60, "card_name": "Forest"}]))]
        self.saved: list[dict] = []
        self._next_id = 1

    def list_decks(self):
        return list(self._rows)

    def save_deck(self, **kwargs):
        self.saved.append(kwargs)
        record = _FakeRecord(self._next_id)
        self._next_id += 1
        return record

    def get_cached_cards_by_names(self, names: list[str]):
        return {}

    def list_cards(self):
        return []


def test_builtin_refresh_updates_saved_deck_in_place() -> None:
    repo = _FakeRepo()

    main._ensure_builtin_decks(repo)  # type: ignore[arg-type]

    ramp = repo._rows[0]
    assert ramp.id == 74 and repo.session.added == [ramp]
    mainboard_names = {entry["card_name"] for entry in json.loads(ramp.mainboard_json)}
    assert "Fatal Push" in mainboard_names
    assert "Swamp" in mainboard_names
    assert "Tropical Island" in mainboard_names
