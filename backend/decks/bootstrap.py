from __future__ import annotations

import json
from collections.abc import Iterable

from ai.deck_analysis import analyze_deck
from card_data.hydration import hydrate_deck_cards, ready_for_match
from decks.builtin_decks import BUILTIN_DECKS
from decks.expansion_top_decks import EXPANSION_TOP_DECKS
from decks.service import DeckService
from persistence.models import DeckRecord
from persistence.repository import Repository


def _latest_decks_by_identity(rows: Iterable[DeckRecord]) -> dict[tuple[str, str], DeckRecord]:
    # Repository order is newest first; preserve historical duplicates untouched.
    existing = {}
    for row in rows:
        key = (row.name.strip().lower(), (row.source or "").strip().lower())
        existing.setdefault(key, row)
    return existing


def _admitted_builtin_archetype(repo: Repository, mainboard: list[dict]) -> str | None:
    deck = hydrate_deck_cards(repo, mainboard)
    if not deck or not all(card.get("card_data_sources") and ready_for_match(card) for card in deck):
        return None
    analysis = analyze_deck(deck)
    if (analysis["type_metadata_coverage"] == 1 and analysis["confidence"] > 0
            and not {"missing_card_metadata", "partial_card_metadata", "fallback_midrange"}
            .intersection(analysis["signals"])):
        return analysis["primary_archetype"]
    return None


def ensure_builtin_decks(repo: Repository) -> None:
    existing = _latest_decks_by_identity(repo.list_decks())
    service = DeckService(repo)
    updated = False
    for name in sorted(BUILTIN_DECKS.keys()):
        key = (name.strip().lower(), "builtin")
        row = existing.get(key)
        parsed = service.parser.parse(BUILTIN_DECKS[name])
        if parsed.errors:
            raise ValueError(f"Invalid built-in template {name}: {parsed.errors}")
        archetype = _admitted_builtin_archetype(repo, parsed.mainboard)
        if row is not None:
            row_updated = False
            if json.loads(row.mainboard_json) != parsed.mainboard or json.loads(row.sideboard_json) != parsed.sideboard:
                row.mainboard_json = json.dumps(parsed.mainboard)
                row.sideboard_json = json.dumps(parsed.sideboard)
                row_updated = True
            if archetype is not None and getattr(row, "archetype_guess", None) != archetype:
                row.archetype_guess = archetype
                row_updated = True
            if row_updated:
                repo.session.add(row)
                updated = True
            continue
        # Do not persist the generic importer's cache-only fallback as canonical evidence.
        repo.save_deck(name=name, source="builtin", mainboard=parsed.mainboard,
                       sideboard=parsed.sideboard, archetype_guess=archetype or "unknown")
    if updated:
        repo.session.commit()


def ensure_expansion_top_decks(repo: Repository) -> None:
    rows = repo.list_decks()
    existing = _latest_decks_by_identity(rows)
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
            archetype = _admitted_builtin_archetype(repo, expected)
            if (row.name != name or json.loads(row.mainboard_json) != expected
                    or json.loads(row.sideboard_json) != sideboard
                    or (archetype is not None and row.archetype_guess != archetype)):
                row.name = name
                row.mainboard_json = json.dumps(expected)
                row.sideboard_json = json.dumps(sideboard)
                if archetype is not None:
                    row.archetype_guess = archetype
                repo.session.add(row)
                updated = True
            continue
        service.import_expansion_top_deck(item["code"])
    if updated:
        repo.session.commit()
