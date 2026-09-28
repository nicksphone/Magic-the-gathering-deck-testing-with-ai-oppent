from __future__ import annotations

import json

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
    updated = False
    for name in sorted(BUILTIN_DECKS.keys()):
        key = (name.strip().lower(), "builtin")
        row = existing.get(key)
        if row is not None:
            parsed = service.parser.parse(BUILTIN_DECKS[name])
            if parsed.errors:
                raise ValueError(f"Invalid built-in template {name}: {parsed.errors}")
            if json.loads(row.mainboard_json) != parsed.mainboard or json.loads(row.sideboard_json) != parsed.sideboard:
                row.mainboard_json = json.dumps(parsed.mainboard)
                row.sideboard_json = json.dumps(parsed.sideboard)
                repo.session.add(row)
                updated = True
            continue
        service.import_deck_text(name=name, deck_text=BUILTIN_DECKS[name], source="builtin")
    if updated:
        repo.session.commit()


def ensure_expansion_top_decks(repo: Repository) -> None:
    rows = repo.list_decks()
    existing = {
        (row.name.strip().lower(), (row.source or "").strip().lower()): row
        for row in rows
    }
    service = DeckService(repo)
    updated = False
    for item in EXPANSION_TOP_DECKS:
        name = item["deck_name"]
        source = f"expansion_top:{item['code']}".lower()
        key = (name.strip().lower(), source)
        row = existing.get(key)
        if row is not None:
            reference = existing.get((item["reference_builtin"].strip().lower(), "builtin"))
            if reference is not None:
                expected = json.loads(reference.mainboard_json)
            else:
                parsed = service.parser.parse(item["deck_text"])
                if parsed.errors:
                    raise ValueError(f"Invalid expansion template {name}: {parsed.errors}")
                expected = parsed.mainboard
            if json.loads(row.mainboard_json) != expected:
                row.mainboard_json = json.dumps(expected)
                repo.session.add(row)
                updated = True
            continue
        service.import_deck_text(name=name, deck_text=item["deck_text"], source=source)
    if updated:
        repo.session.commit()
