from __future__ import annotations

from dataclasses import dataclass

import main


@dataclass
class _DeckRow:
    name: str
    source: str


class _FakeSession:
    def __init__(self) -> None:
        self.deleted: list[_DeckRow] = []
        self.committed = 0

    def delete(self, row: _DeckRow) -> None:
        self.deleted.append(row)

    def commit(self) -> None:
        self.committed += 1


class _FakeRecord:
    def __init__(self, record_id: int) -> None:
        self.id = record_id


class _FakeRepo:
    def __init__(self) -> None:
        self.session = _FakeSession()
        self._rows = [_DeckRow(name="Ramp", source="builtin")]
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


def test_builtin_refresh_reimports_updated_builtin_decks() -> None:
    repo = _FakeRepo()

    main._ensure_builtin_decks(repo)  # type: ignore[arg-type]

    assert repo.session.deleted, "Expected stale builtin rows to be removed before reimport"
    assert len(repo.saved) >= 1
    ramp = next(item for item in repo.saved if item["name"] == "Ramp")
    mainboard_names = {entry["card_name"] for entry in ramp["mainboard"]}
    assert "Fatal Push" in mainboard_names
    assert "Swamp" in mainboard_names
