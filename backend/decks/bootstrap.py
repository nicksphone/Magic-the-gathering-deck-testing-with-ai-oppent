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
    by_source = {}
    for row in rows:
        source = (row.source or "").strip().lower()
        if source.startswith("expansion_top:"):
            by_source.setdefault(source, row)
    service = DeckService(repo)
    updated = False
    for item in EXPANSION_TOP_DECKS:
        name = item["deck_name"]
        source = f"expansion_top:{item['code']}".lower()
        row = by_source.get(source)
        if row is not None:
            reference_name = item.get("reference_builtin")
            reference = existing.get((reference_name.strip().lower(), "builtin")) if reference_name else None
            if reference is not None:
                expected = json.loads(reference.mainboard_json)
                sideboard = json.loads(reference.sideboard_json)
            else:
                parsed = service.parser.parse(item["deck_text"])
                if parsed.errors:
                    raise ValueError(f"Invalid expansion deck {name}: {parsed.errors}")
                expected = parsed.mainboard
                sideboard = parsed.sideboard
            if (row.name != name or json.loads(row.mainboard_json) != expected
                    or json.loads(row.sideboard_json) != sideboard or row.archetype_guess != item["archetype"]):
                row.name = name
                row.mainboard_json = json.dumps(expected)
                row.sideboard_json = json.dumps(sideboard)
                row.archetype_guess = item["archetype"]
                repo.session.add(row)
                updated = True
            continue
        service.import_deck_text(name=name, deck_text=item["deck_text"], source=source)
    if updated:
        repo.session.commit()
