from __future__ import annotations

try:
    from . import _bootstrap
except ImportError:
    import _bootstrap

import argparse
import json
from pathlib import Path

import httpx
from sqlmodel import Session, SQLModel, create_engine

from knowledge.ingest import KnowledgeIngestor
from persistence.db import engine, init_db
from persistence.repository import Repository
from scripts.oracle_corpus_report import collect_corpus


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync canonical card knowledge and rulings; does not certify rules support")
    parser.add_argument("--name", action="append", default=[], help="Additional exact card name; repeatable")
    parser.add_argument("--query", help="Optional Scryfall search for additional cards")
    parser.add_argument("--limit", type=int, default=200, help="Maximum additional search cards")
    parser.add_argument("--force", action="store_true", help="Refresh previously verified knowledge")
    parser.add_argument("--database", type=Path, help="Alternative SQLite file for isolated ingestion")
    parser.add_argument("--out", type=Path, help="Write JSON summary")
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be positive")
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
        for deck in repo.list_decks():
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
