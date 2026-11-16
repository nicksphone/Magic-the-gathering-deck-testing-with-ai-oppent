"""Cold Battle retry worker; stdout contains only the public check summary."""
import json
import os
from pathlib import Path
import sys


def main():
    database, match_id, seat, battle, attacker = sys.argv[1:]
    database = str(Path(database).resolve())
    assert os.environ["MTG_DATABASE_PATH"] == database
    import main as app
    from fastapi.testclient import TestClient
    from sqlmodel import Session
    from persistence.repository import Repository
    from tests.temporary_characteristics_http_fixture import owned_database

    def stored_game():
        with Session(app.engine) as session:
            row = Repository(session).get_active_match(match_id)
            return row.state_json, row.controller_json

    with owned_database(app.engine):
        before = stored_game()
        client = TestClient(app.app)
        try:
            current = client.get(f"/matches/{match_id}")
            assert current.status_code == 200 and current.json()["revision"] == 1
            body = {"player_id": int(seat), "action": {
                "type": "attack", "attackers": [attacker],
                "attack_targets": {attacker: "battle:" + battle},
            }}
            path = f"/matches/{match_id}/action"
            retry = client.post(path, json=body, headers={
                "Idempotency-Key": "before-restart", "X-Match-Revision": "0",
            })
            assert retry.status_code == 200 and retry.json()["revision"] == 1
            assert current.json() == retry.json()
            stale = client.post(path, json=body, headers={
                "Idempotency-Key": "different-intent", "X-Match-Revision": "0",
            })
            assert stale.status_code == 409
            assert stale.json()["detail"]["code"] == "stale_revision"
            assert stored_game() == before
            print(json.dumps({"revision": 1, "retry_status": retry.status_code,
                              "stale_status": stale.status_code,
                              "stored_game_unchanged": True}))
        finally:
            client.close()
    app.engine.dispose()


if __name__ == "__main__":
    main()
