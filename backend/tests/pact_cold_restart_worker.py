"""Owned SQLite app-process boundary; public hashes only on stdout.

Pact creation and payment use real ASGI HTTP. This is not a TCP/browser restart.
"""
import hashlib
import json
import os
from pathlib import Path
import sys


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main():
    phase, database, seat_text, option, expected_text = sys.argv[1:]
    seat = int(seat_text)
    expected = json.loads(expected_text)
    assert phase in {"seed", "resolve", "retry"} and option in {"pay", "decline"}
    assert os.environ["MTG_DATABASE_PATH"] == str(Path(database).resolve())
    import main as app
    from ai.agent import AIAgent
    from fastapi.testclient import TestClient
    from rules_engine.engine import RulesEngine
    from sqlmodel import Session
    from persistence.repository import Repository
    from tests.battle_payment_browser_fixture import midgame
    from tests.temporary_characteristics_http_fixture import owned_database

    def stored(mid):
        with Session(app.engine) as session:
            row = Repository(session).get_active_match(mid)
            return {"state_sha256": digest(row.state_json), "controller_sha256": digest(row.controller_json)}

    with owned_database(app.engine):
        client = TestClient(app.app)
        try:
            if phase == "seed":
                state, ids = midgame(seat)
                controller = app.MatchController(state=state, rules=RulesEngine(),
                    controllers={1: "human", 2: "human"}, ai={1: AIAgent(), 2: AIAgent()},
                    mode="human_vs_human", deck_ids=(None, None), mainboards=state.starting_decks,
                    sideboards={1: [], 2: []}, game_number=1, current_game_recorded=False,
                    match_complete=False, best_of=3)
                app.ACTIVE_MATCHES[state.id] = controller
                with Session(app.engine) as session:
                    app._persist_active_match(Repository(session), controller)
                mid = state.id
            else:
                mid = expected["match_id"]
                assert mid not in app.ACTIVE_MATCHES
                assert stored(mid) == {key: expected[key] for key in ("state_sha256", "controller_sha256")}
                response = client.get(f"/matches/{mid}")
                assert response.status_code == 200, response.text
                assert digest(response.json()) == expected["view_sha256"]
                assert stored(mid) == {key: expected[key] for key in ("state_sha256", "controller_sha256")}
                controller = app.ACTIVE_MATCHES[mid]
            path = f"/matches/{mid}/action"

            def get():
                response = client.get(f"/matches/{mid}")
                assert response.status_code == 200, response.text
                return response.json()

            def send(actor, action, *, key=None, revision=None):
                before = controller.revision
                response = client.post(path, json={"player_id": actor, "action": action}, headers={
                    "X-Match-Revision": str(before if revision is None else revision),
                    "Idempotency-Key": key or f"create-{before}"})
                assert response.status_code == 200, response.text
                return response.json()

            if phase == "seed":
                send(seat, {"type": "cast_spell", "card_id": ids["pacts"][0]})
                for _ in range(160):
                    pending = controller.state.pending_mechanic_choice
                    if pending and pending["kind"] == "deferred_upkeep_payment":
                        break
                    if pending:
                        assert pending["kind"] == "search_library"
                        cid = next(cid for cid in pending["options"] if controller.state.cards[cid].name == "Grizzly Bears")
                        send(seat, {"type": "choose_mechanic", "card_ids": [cid]})
                    else:
                        moves = controller.rules.legal_moves(controller.state, controller.state.priority_player)
                        action = {"type": "block", "blocks": {}} if any(m["type"] == "block" for m in moves) else {"type": "pass_priority"}
                        send(controller.state.priority_player, action)
                else:
                    raise AssertionError("Real HTTP transitions missed Pact upkeep")
                view = get()
                assert view["active_player"] == seat and view["step"] == "upkeep"
                assert view["pending_mechanic_choice"]["player_id"] == seat
                assert view["pending_mechanic_choice"]["options"] == ["pay", "decline"]
                assert view["winner"] is None
                assert not any(card["tapped"] for card in view["players"][str(seat)]["battlefield"] if card["name"] == "Forest")
                result = {"match_id": mid, "revision": view["revision"], "view_sha256": digest(view), **stored(mid)}
            else:
                revision = expected["revision"] if phase == "resolve" else expected["pending_revision"]
                action = {"type": "choose_mechanic", "card_ids": [option]}
                if phase == "resolve":
                    menu = client.get(f"/matches/{mid}/legal-moves")
                    assert menu.status_code == 200
                    assert menu.json()["revision"] == revision and menu.json()["player_id"] == seat
                    choice = next(m for m in menu.json()["moves"] if m["type"] == "choose_mechanic")
                    assert choice["kind"] == "deferred_upkeep_payment" and option in choice["options"]
                view = send(seat, action, key="resolve-pact-once", revision=revision)
                assert view["revision"] == revision + 1
                assert view["pending_mechanic_choice"] is None
                assert view["winner"] == (None if option == "pay" else 3-seat)
                paid = sum("pays {2}{G}{G} for the delayed upkeep ability." in line for line in view["log"])
                assert paid == int(option == "pay")
                tapped = sum(card["tapped"] for card in view["players"][str(seat)]["battlefield"] if card["name"] == "Forest")
                assert tapped == (4 if option == "pay" else 0)
                assert get() == view
                stable = stored(mid)
                retry = send(seat, action, key="resolve-pact-once", revision=revision)
                assert retry == view and stored(mid) == stable
                stale = client.post(path, json={"player_id": seat, "action": action}, headers={
                    "X-Match-Revision": str(revision), "Idempotency-Key": "different-payment-intent"})
                assert stale.status_code == 409 and stale.json()["detail"]["code"] == "stale_revision"
                assert stored(mid) == stable
                result = {"match_id": mid, "revision": view["revision"], "pending_revision": revision,
                    "view_sha256": digest(view), **stable, "paid_count": paid, "tapped_forests": tapped,
                    "retry_status": 200, "stale_status": 409}
                if phase == "retry":
                    assert result == expected
            print(json.dumps(result))
        finally:
            client.close()
    app.engine.dispose()


if __name__ == "__main__":
    main()
