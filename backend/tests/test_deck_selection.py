from __future__ import annotations

import json
from types import SimpleNamespace

from decks.selection import select_representative_decks


def _row(name: str, archetype_guess: str, mainboard: list[dict] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        archetype_guess=archetype_guess,
        mainboard_json="[]" if mainboard is None else json.dumps(mainboard),
    )


def test_select_representative_decks_spreads_across_archetypes_before_filling() -> None:
    rows = [
        _row("Aggro One", "Aggro"),
        _row("Aggro Two", "Aggro"),
        _row("Control One", "Control"),
        _row("Tempo One", "Tempo"),
        _row("Ramp One", "Ramp"),
    ]

    selected = select_representative_decks(rows, 3, guess_archetype_fn=lambda _: "unknown")

    assert [item["name"] for item in selected] == ["Aggro One", "Control One", "Tempo One"]


def test_select_representative_decks_uses_guess_for_unknown_rows() -> None:
    calls: list[list[dict]] = []

    def fake_guess(mainboard: list[dict]) -> str:
        calls.append(mainboard)
        return "Tokens"

    rows = [_row("Mystery Deck", "unknown", [{"quantity": 4, "card_name": "Raise the Alarm"}])]

    selected = select_representative_decks(rows, 1, guess_archetype_fn=fake_guess)

    assert calls == [[{"quantity": 4, "card_name": "Raise the Alarm"}]]
    assert selected[0]["archetype"] == "Tokens"


def test_select_representative_decks_accepts_dict_rows() -> None:
    rows = [
        {"name": "Aggro One", "archetype_guess": "Aggro", "mainboard_json": "[]"},
        {"name": "Control One", "archetype_guess": "Control", "mainboard_json": "[]"},
    ]

    selected = select_representative_decks(rows, 2, guess_archetype_fn=lambda _: "unknown")

    assert [item["name"] for item in selected] == ["Aggro One", "Control One"]
