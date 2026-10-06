"""Fault injection must preserve stored rows, not equate them with the cache."""
import json
from uuid import uuid4

from sqlmodel import Session

import main
from persistence.db import engine
from persistence.repository import Repository
from tests.test_api_input_contracts import game, snapshot
from tests.test_match_recovery import test_start_receipt_storage_failure_leaves_no_match_or_receipt as verify_failed_start


def test_failed_start_preserves_corrupt_discovery_row_and_cache(game, monkeypatch):
    client, original = game
    raw = json.loads(snapshot(original)[0])
    identifier = f"corrupt-summary-{uuid4()}"
    raw["id"] = identifier
    raw["cards"][next(iter(raw["cards"]))]["counters"] = None
    encoded = json.dumps(raw)
    config = json.dumps(main._controller_snapshot(original))
    with Session(engine) as session:
        Repository(session).save_active_match(identifier, encoded, config)

    assert identifier in {row["id"] for row in client.get("/matches").json()}
    assert client.get(f"/matches/{identifier}").status_code == 404
    assert identifier not in main.ACTIVE_MATCHES
    verify_failed_start(game, monkeypatch)
    assert identifier not in main.ACTIVE_MATCHES
    with Session(engine) as session:
        saved = Repository(session).get_active_match(identifier)
        assert saved.state_json == encoded
        assert saved.controller_json == config
