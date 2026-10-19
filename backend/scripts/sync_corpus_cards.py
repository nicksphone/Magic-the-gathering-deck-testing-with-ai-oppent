from __future__ import annotations

try:
    from . import _bootstrap
except ImportError:
    import _bootstrap

import argparse
from copy import deepcopy
import json
from pathlib import Path

import httpx
from sqlmodel import Session, SQLModel, create_engine

from knowledge.ingest import KnowledgeIngestor
from knowledge import profiles as _profiles
from knowledge.profiles import MAX_CORPUS, derive_profile, merge_profile_payload
from card_data.sync import ScryfallSyncService
from persistence.db import engine, init_db
from persistence.repository import Repository
from scripts.oracle_corpus_report import collect_corpus

_BUILTIN_DERIVE_PROFILE = derive_profile


def profile_corpus(repo: Repository, names, *, corpus=None, archetype=None) -> dict:
    """Write estimates separately from preserved canonical facts and rulings."""
    requested = sorted({str(name).strip().casefold(): str(name).strip()
                        for name in names if str(name).strip()}.values(), key=str.casefold)
    lookup = repo.get_card_knowledge_by_names(requested)
    report = {"profiled": 0, "profiles_updated": 0, "errors": []}
    valid, seen = [], set()
    for name in requested:
        row = lookup.get(name.casefold())
        canonical = ScryfallSyncService.canonical_local_profile(row, name)
        if canonical is None:
            report["errors"].append({"name": name, "error": "Verified canonical knowledge is missing or invalid"})
        elif row.name.casefold() not in seen:
            seen.add(row.name.casefold())
            valid.append((row, canonical))
    context = deepcopy(corpus) if corpus is not None else [deepcopy(profile["card_data"]) for _, profile in valid]
    prepared_context = None
    for row, canonical in valid:
        try:
            if derive_profile is _BUILTIN_DERIVE_PROFILE:
                raw = _profiles._raw(deepcopy(canonical["card_data"]))
                if prepared_context is None:
                    prepared_context = _profiles._profile_context(context, archetype)
                derived = _profiles._derive_with_context(raw, deepcopy(prepared_context))
            else:
                # Preserve the existing injectable estimator's original call contract.
                derived = derive_profile(deepcopy(canonical["card_data"]), context, archetype=archetype)
            merged = merge_profile_payload(canonical, derived)
            answerable, windows = list(derived.answerable_by), list(derived.cast_windows)
            unchanged = (row.play_value == derived.play_value and row.threat_level == derived.threat_level
                         and row.etb_impact == derived.etb_impact and canonical == merged
                         and json.loads(row.answerable_by_json) == answerable
                         and json.loads(row.cast_windows_json) == windows)
            if not unchanged:
                repo.upsert_card_knowledge({
                    "name": row.name, "scryfall_id": row.scryfall_id, "oracle_source": row.oracle_source,
                    "play_value": derived.play_value, "threat_level": derived.threat_level,
                    "answerable_by": answerable, "cast_windows": windows,
                    "etb_impact": derived.etb_impact, "profiles": merged,
                })
                report["profiles_updated"] += 1
            report["profiled"] += 1
        except (ValueError, TypeError, KeyError) as exc:
            report["errors"].append({"name": row.name, "error": str(exc)})
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync canonical card knowledge and rulings; does not certify rules support")
    parser.add_argument("--name", action="append", default=[], help="Additional exact card name; repeatable")
    parser.add_argument("--query", help="Optional Scryfall search for additional cards")
    parser.add_argument("--limit", type=int, default=200, help="Maximum additional search cards")
    parser.add_argument("--force", action="store_true", help="Refresh previously verified knowledge")
    parser.add_argument("--profile", action="store_true", help="Derive heuristic tactical profiles after canonical corpus sync")
    parser.add_argument("--profile-deck", help="Use this stored deck's mainboard as profile context; requires --profile")
    parser.add_argument("--database", type=Path, help="Alternative SQLite file for isolated ingestion")
    parser.add_argument("--out", type=Path, help="Write JSON summary")
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be positive")
    if args.profile_deck and not args.profile:
        parser.error("--profile-deck requires --profile")
    if args.database:
        args.database.parent.mkdir(parents=True, exist_ok=True)
        selected_engine = create_engine(f"sqlite:///{args.database.resolve()}")
        SQLModel.metadata.create_all(selected_engine)
    else:
        init_db()
        selected_engine = engine
    report = {"synced": 0, "cached": 0, "errors": []}
    with Session(selected_engine) as session, httpx.Client(
        headers={"User-Agent": "MTGDeckTestingLab/0.1 (canonical knowledge sync)", "Accept": "application/json"}, timeout=30,
    ) as client:
        repo = Repository(session)
        names = {item["name"] for item in collect_corpus().values()}
        decks = repo.list_decks()
        for deck in decks:
            for board in (deck.mainboard_json, deck.sideboard_json):
                names.update(item["card_name"] for item in json.loads(board) if item.get("card_name"))
        names.update(args.name)
        ingestor = KnowledgeIngestor(repo, client)
        for name in sorted(names, key=str.casefold):
            try:
                status = ingestor.sync_name(name, args.force)
                report[status] += 1
                print(f"{status}: {name}", flush=True)
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                report["errors"].append({"name": name, "error": str(exc)})
                print(f"error: {name}: {exc}", flush=True)
        if args.query:
            try:
                extra = ingestor.sync_search(args.query, args.limit, args.force)
                report["synced"] += extra["synced"]
                report["cached"] += extra["cached"]
                report["errors"].extend(extra["errors"])
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                report["errors"].append({"query": args.query, "error": str(exc)})
        if args.profile:
            context, archetype = None, None
            if args.profile_deck:
                matches = [deck for deck in decks if deck.name == args.profile_deck]
                if len(matches) != 1:
                    report["errors"].append({"deck": args.profile_deck, "error": "Profiling requires one unambiguous stored deck"})
                else:
                    entries = json.loads(matches[0].mainboard_json)
                    # Match the derivation quantity bounds before analysis expands copies.
                    invalid = (not isinstance(entries, list) or not 1 <= len(entries) <= MAX_CORPUS
                               or any(not isinstance(entry, dict) or not isinstance(entry.get("card_name"), str)
                                      or type(entry.get("quantity")) is not int
                                      or not 0 <= entry["quantity"] <= 1000 for entry in entries)
                               or not any(entry["quantity"] > 0 for entry in entries))
                    if invalid:
                        report["errors"].append({"deck": args.profile_deck, "error": "Invalid or empty profiling deck context"})
                    else:
                        cards = repo.get_card_knowledge_by_names([entry["card_name"] for entry in entries])
                        context = []
                        for entry in entries:
                            canonical = ScryfallSyncService.canonical_local_profile(cards.get(entry["card_name"].casefold()), entry["card_name"])
                            if canonical is None:
                                report["errors"].append({"name": entry["card_name"], "error": "Profiling deck context lacks canonical knowledge"})
                            else:
                                context.append({"quantity": entry["quantity"], "card_metadata": canonical["card_data"]})
                        if not report["errors"]:
                            from ai.deck_analysis import guess_archetype
                            archetype = guess_archetype(context)
            if not report["errors"]:
                profiled = profile_corpus(repo, names, corpus=context, archetype=archetype)
                report.update({key: profiled[key] for key in ("profiled", "profiles_updated")})
                report["errors"].extend(profiled["errors"])
        report["knowledge_rows"] = len(repo.list_card_knowledge())
        report["requested_corpus_cards"] = len(names)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return int(bool(report["errors"]))


if __name__ == "__main__":
    raise SystemExit(main())
