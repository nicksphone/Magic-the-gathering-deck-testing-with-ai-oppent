from __future__ import annotations

from decks.builtin_decks import BUILTIN_DECKS
from decks.expansion_top_decks import EXPANSION_TOP_DECKS
from decks.service import DeckService
from persistence.repository import Repository


def ensure_builtin_decks(repo: Repository) -> None:
    existing = {
        (row.name.strip().lower(), (row.source or "").strip().lower()): row
        for row in repo.list_decks()
    }
    service = DeckService(repo)
    for name in sorted(BUILTIN_DECKS.keys()):
        key = (name.strip().lower(), "builtin")
        row = existing.get(key)
        if row is not None:
            repo.session.delete(row)
    repo.session.commit()
    for name in sorted(BUILTIN_DECKS.keys()):
        service.import_deck_text(name=name, deck_text=BUILTIN_DECKS[name], source="builtin")


def ensure_expansion_top_decks(repo: Repository) -> None:
    existing = {
        (row.name.strip().lower(), (row.source or "").strip().lower())
        for row in repo.list_decks()
    }
    service = DeckService(repo)
    for item in EXPANSION_TOP_DECKS:
        name = item["deck_name"]
        source = f"expansion_top:{item['code']}".lower()
        key = (name.strip().lower(), source)
        if key in existing:
            continue
        service.import_deck_text(name=name, deck_text=item["deck_text"], source=source)
