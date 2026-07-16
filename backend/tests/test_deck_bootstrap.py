from __future__ import annotations

from dataclasses import dataclass

from decks.bootstrap import ensure_builtin_decks
from decks.parser import DeckParser


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
        self._rows = [_DeckRow(name="Tempo", source="builtin")]
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


def test_ensure_builtin_decks_reimports_current_builtin_list() -> None:
    repo = _FakeRepo()

    ensure_builtin_decks(repo)  # type: ignore[arg-type]

    assert repo.session.deleted, "Expected stale builtin rows to be removed before refresh"
    tempo = next(item for item in repo.saved if item["name"] == "Tempo")
    mainboard_names = {entry["card_name"] for entry in tempo["mainboard"]}
    assert "Mountain" in mainboard_names


def test_deck_parser_accepts_common_sideboard_headers() -> None:
    repo = _FakeRepo()
    repo.list_cards = lambda: [type("C", (), {"name": "Island"})(), type("C", (), {"name": "Negate"})()]  # type: ignore[assignment]
    parser = DeckParser(repo)  # type: ignore[arg-type]

    parsed = parser.parse(
        "\n".join(
            [
                "4 Island",
                "56 Island",
                "SB:",
                "3 Negate",
            ]
        )
    )

    assert sum(item["quantity"] for item in parsed.mainboard) == 60
    assert sum(item["quantity"] for item in parsed.sideboard) == 3


def test_deck_parser_strips_common_set_annotations_from_card_names() -> None:
    repo = _FakeRepo()
    repo.list_cards = lambda: [type("C", (), {"name": "Lightning Bolt"})(), type("C", (), {"name": "Island"})()]  # type: ignore[assignment]
    parser = DeckParser(repo)  # type: ignore[arg-type]

    parsed = parser.parse(
        "\n".join(
            [
                "4 Lightning Bolt [M11]",
                "56 Island (XLN)",
            ]
        )
    )

    assert parsed.errors == []
    assert {item["card_name"] for item in parsed.mainboard} == {"Lightning Bolt", "Island"}


def test_deck_parser_accepts_x_multiplier_notation_and_comments() -> None:
    repo = _FakeRepo()
    repo.list_cards = lambda: [type("C", (), {"name": "Lightning Bolt"})(), type("C", (), {"name": "Island"})()]  # type: ignore[assignment]
    parser = DeckParser(repo)  # type: ignore[arg-type]

    parsed = parser.parse(
        "\n".join(
            [
                "# comment line",
                "Deck",
                "4x Lightning Bolt",
                "56 Island",
                "// sideboard note",
                "SB:",
                "; another comment",
                "3x Negate",
            ]
        )
    )

    assert sum(item["quantity"] for item in parsed.mainboard) == 60
    assert sum(item["quantity"] for item in parsed.sideboard) == 3
    assert parsed.errors == []
