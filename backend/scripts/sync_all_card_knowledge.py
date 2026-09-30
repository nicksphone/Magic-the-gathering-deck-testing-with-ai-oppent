from __future__ import annotations

try:
    from . import _bootstrap
except ImportError:
    import _bootstrap

import argparse
import gzip
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx
from sqlmodel import Session, SQLModel, create_engine

from card_data.http_utils import get_with_backoff
from knowledge.ingest import SCHEMA_VERSION
from knowledge.models import CardKnowledge
from card_data.tactical import canonical_tactical_tags
from persistence.db import engine, init_db
from persistence.repository import Repository

DATA_DIR = Path(__file__).resolve().parents[1] / "knowledge" / "data"


def read_cards(path: Path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as stream:
        if ".jsonl" in path.name:
            for line in stream:
                if line.strip():
                    yield json.loads(line)
        else:
            yield from json.load(stream)


def import_cards(repository: Repository, cards, provenance: dict, progress=None) -> dict:
    """Bulk metadata import. Never label missing rulings as verified."""
    existing = {row.name.casefold(): row for row in repository.list_card_knowledge()}
    by_oracle = {}
    for row in existing.values():
        profile = json.loads(row.profiles_json)
        if profile.get("oracle_id"):
            by_oracle[profile["oracle_id"]] = row
    report = {"cards": 0, "added": 0, "updated": 0, "unchanged": 0, "faces": 0, "rulings_pending": 0, "name_collisions": 0}
    seen_oracles = set()
    for raw in cards:
        if raw.get("object") != "card" or not all(raw.get(key) for key in ("id", "oracle_id", "name", "type_line")):
            raise ValueError("Incomplete canonical card in bulk file.")
        if raw["oracle_id"] in seen_oracles:
            continue
        seen_oracles.add(raw["oracle_id"])
        key = raw["name"].casefold()
        row = by_oracle.get(raw["oracle_id"])
        if row is None:
            row = existing.get(key)
            if row and json.loads(row.profiles_json).get("oracle_id") not in (None, raw["oracle_id"]):
                # Token variants can share a printed name. Disambiguate the
                # storage key while retaining the exact canonical payload name.
                row = None
                report["name_collisions"] += 1
                key = f"{raw['name']} [oracle:{raw['oracle_id']}]".casefold()
        profile = json.loads(row.profiles_json) if row else {}
        canonical_same = profile.get("card_data") == raw
        verified = bool(profile.get("rulings_verified")) and canonical_same
        profile.update({
            "schema_version": SCHEMA_VERSION,
            "oracle_id": raw["oracle_id"],
            "card_data": raw,
            "bulk_provenance": provenance,
            "rulings_verified": verified,
            "facts": {
                "mana_value": raw.get("cmc"),
                "color_identity": raw.get("color_identity", []),
                "keywords": raw.get("keywords", []),
                "layout": raw.get("layout"),
                "face_count": len(raw.get("card_faces", [])),
            },
        })
        profile.update(canonical_tactical_tags(raw))
        if not verified:
            # Preserve old rulings as historical data, not current verification.
            report["rulings_pending"] += 1
        encoded = json.dumps(profile, sort_keys=True)
        if row is not None and row.profiles_json == encoded and row.scryfall_id == raw["id"] and row.oracle_source == "scryfall":
            report["unchanged"] += 1
        else:
            if row is None:
                stored_name = raw["name"] if key == raw["name"].casefold() else f"{raw['name']} [oracle:{raw['oracle_id']}]"
                row = CardKnowledge(name=stored_name)
                existing[key] = row
                report["added"] += 1
            else:
                report["updated"] += 1
            row.scryfall_id = raw["id"]
            row.oracle_source = "scryfall"
            row.profiles_json = encoded
            row.updated_at = datetime.now(timezone.utc)
            repository.session.add(row)
        by_oracle[raw["oracle_id"]] = row
        report["cards"] += 1
        report["faces"] += len(raw.get("card_faces", []))
        if report["cards"] % 500 == 0:
            repository.session.commit()
            if progress:
                progress(report["cards"])
    repository.session.commit()
    return report


def download_bulk(client: httpx.Client, directory: Path) -> tuple[Path, dict]:
    response = get_with_backoff(client, "https://api.scryfall.com/bulk-data/oracle_cards", timeout=30)
    response.raise_for_status()
    metadata = response.json()
    if metadata.get("type") != "oracle_cards":
        raise ValueError("Expected the unique Oracle-card bulk dataset.")
    uri = metadata.get("jsonl_download_uri") or metadata.get("download_uri")
    parsed = urlparse(uri or "")
    if parsed.scheme != "https" or parsed.netloc not in {"data.scryfall.io", "data.scryfall.com"}:
        raise ValueError("Invalid Scryfall bulk download URL.")
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / Path(parsed.path).name
    if not target.exists():
        temporary = target.with_name(target.name + ".part")
        try:
            with client.stream("GET", uri, timeout=120) as download:
                download.raise_for_status()
                with temporary.open("wb") as out:
                    for chunk in download.iter_bytes():
                        out.write(chunk)
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    return target, {"source": "scryfall", "type": metadata["type"], "updated_at": metadata["updated_at"], "download_uri": uri}


def main() -> int:
    parser = argparse.ArgumentParser(description="Import all unique Scryfall Oracle cards into CardKnowledge")
    parser.add_argument("--database", type=Path, help="Alternative SQLite file")
    parser.add_argument("--out", type=Path, default=DATA_DIR / "all-cards-summary.json")
    args = parser.parse_args()
    if args.database:
        args.database.parent.mkdir(parents=True, exist_ok=True)
        selected_engine = create_engine(f"sqlite:///{args.database.resolve()}")
        SQLModel.metadata.create_all(selected_engine)
    else:
        init_db()
        selected_engine = engine
    with httpx.Client(headers={"User-Agent": "MTGDeckTestingLab/0.1 (canonical knowledge sync)", "Accept": "application/json"}, follow_redirects=False) as client:
        path, provenance = download_bulk(client, DATA_DIR)
    with Session(selected_engine) as session:
        repo = Repository(session)
        report = import_cards(repo, read_cards(path), provenance, lambda count: print(f"Imported {count} cards", flush=True))
        report["total_knowledge_rows"] = len(repo.list_card_knowledge())
        report["provenance"] = provenance
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
