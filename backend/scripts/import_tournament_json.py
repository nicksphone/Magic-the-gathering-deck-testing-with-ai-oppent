from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlmodel import Session

from data_ingest.service import TournamentIngestService
from persistence.db import engine, init_db
from persistence.repository import Repository


def main() -> None:
    parser = argparse.ArgumentParser(description="Import tournament event/deck JSON payload")
    parser.add_argument("--input", required=True, help="Path to JSON file")
    args = parser.parse_args()

    path = Path(args.input)
    payload = json.loads(path.read_text(encoding="utf-8"))

    init_db()
    with Session(engine) as session:
        repo = Repository(session)
        out = TournamentIngestService(repo).ingest_event_payload(payload)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
