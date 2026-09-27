from __future__ import annotations

try:
    from . import _bootstrap
except ImportError:
    import _bootstrap

import argparse
import json
from collections import Counter
from pathlib import Path

from sqlmodel import Session

from persistence.db import engine, init_db
from persistence.repository import Repository
from scripts.oracle_corpus_report import collect_corpus


def knowledge_report(repo: Repository, names: list[str]) -> dict:
    rows = repo.list_card_knowledge()
    lookup = {}
    totals = Counter()
    for row in rows:
        profile = json.loads(row.profiles_json)
        raw = profile.get("card_data", {})
        totals["rows"] += 1
        totals["canonical_payloads"] += int(row.oracle_source == "scryfall" and bool(raw.get("oracle_id")))
        totals["rulings_verified"] += int(bool(profile.get("rulings_verified")))
        aliases = [row.name, raw.get("name", "")]
        aliases.extend(face.get("name", "") for face in raw.get("card_faces", []))
        for alias in aliases:
            if alias:
                key = alias.casefold()
                previous = lookup.get(key)
                rank = (bool(profile.get("rulings_verified")), row.name.casefold() == key)
                previous_rank = (bool(previous[1].get("rulings_verified")), previous[0].name.casefold() == key) if previous else (-1, -1)
                if rank > previous_rank:
                    lookup[key] = (row, profile)
    cards = []
    for name in sorted(set(names), key=str.casefold):
        match = lookup.get(name.casefold())
        row, profile = match if match else (None, {})
        raw = profile.get("card_data", {})
        cards.append({
            "name": name,
            "canonical": bool(row and row.oracle_source == "scryfall" and raw.get("oracle_id")),
            "rulings_verified": bool(profile.get("rulings_verified")),
            "rulings_count": len(profile.get("rulings", [])),
            "face_count": len(raw.get("card_faces", [])),
        })
    return {"database": dict(totals), "requested_cards": len(cards), "missing_cards": [card["name"] for card in cards if not card["canonical"]], "rulings_pending": [card["name"] for card in cards if not card["rulings_verified"]], "cards": cards, "rules_support_certified": False}


def main() -> int:
    parser = argparse.ArgumentParser(description="Report canonical knowledge coverage, separately from rules support")
    parser.add_argument("--require-rulings", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    init_db()
    with Session(engine) as session:
        repo = Repository(session)
        names = [item["name"] for item in collect_corpus().values()]
        for deck in repo.list_decks():
            for board in (deck.mainboard_json, deck.sideboard_json):
                names.extend(item["card_name"] for item in json.loads(board) if item.get("card_name"))
        report = knowledge_report(repo, names)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return int(bool(report["missing_cards"]) or (args.require_rulings and bool(report["rulings_pending"])))


if __name__ == "__main__":
    raise SystemExit(main())
