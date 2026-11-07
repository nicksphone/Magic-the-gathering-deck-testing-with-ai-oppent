"""Synthetic HTTP boundary checks, not native games or a main/SQLite lifespan."""
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from forge_routes import create_forge_router


CAPABILITY = "ab" * 32
REQUEST_ID = "09090909-0909-4909-8909-090909090909"
TOKEN = "08080808-0808-4808-8808-080808080808"


class SyntheticManager:
    available = True

    def __init__(self):
        self.calls = []

    def create(self, payload, capability, key):
        self.calls.append(("create", payload, capability, key))
        return {"engine": "forge", "session_id": "synthetic-session", "sequence": 0}

    def get(self, session_id, capability):
        self.calls.append(("get", session_id, capability))
        return {"engine": "forge", "session_id": session_id, "sequence": 0}

    def answer(self, session_id, capability, payload):
        self.calls.append(("answer", session_id, capability, payload))
        return {"engine": "forge", "session_id": session_id, "sequence": 1}

    def close(self, session_id, capability):
        self.calls.append(("close", session_id, capability))
        return {"engine": "forge", "session_id": session_id, "sequence": 2}


class ForgeRouteTests(unittest.TestCase):
    def setUp(self):
        self.manager = SyntheticManager()
        app = FastAPI()
        app.include_router(create_forge_router(lambda: self.manager))
        self.client = TestClient(app)
        self.headers = {"Authorization": "Bearer " + CAPABILITY, "Idempotency-Key": "synthetic-start"}
        self.start = {"deck_a": [{"card_name": "Island", "quantity": 60}],
                      "deck_b": [{"card_name": "Forest", "quantity": 60}],
                      "name_a": "Synthetic A", "name_b": "Synthetic B", "human_seat": 0}
        self.answer = {"request_id": REQUEST_ID, "tokens": [TOKEN], "sequence": 0, "action_id": "action-one"}

    def tearDown(self):
        self.client.close()

    def test_status_has_no_runtime_paths_or_keys(self):
        response = self.client.get("/forge/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"available": True})
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(self.manager.calls, [])

    def test_start_forwards_only_validated_setup_and_capability(self):
        response = self.client.post("/forge/sessions", json=self.start, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        operation, payload, capability, key = self.manager.calls[0]
        self.assertEqual((operation, capability, key), ("create", CAPABILITY, "synthetic-start"))
        self.assertEqual(payload["human_seat"], 0)
        self.assertEqual(payload["deck_a"], self.start["deck_a"])
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertNotIn(CAPABILITY, response.text)

    def test_get_and_close_use_header_not_client_actor(self):
        for method in (self.client.get, self.client.delete):
            response = method("/forge/sessions/synthetic-session", headers=self.headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["cache-control"], "no-store")
            self.assertEqual(self.manager.calls[-1][1:], ("synthetic-session", CAPABILITY))

    def test_answer_preserves_ordered_native_tokens(self):
        response = self.client.post("/forge/sessions/synthetic-session/answer", json=self.answer, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.manager.calls[0], ("answer", "synthetic-session", CAPABILITY, self.answer))
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_missing_or_malformed_capability_never_calls_manager(self):
        for header in (None, "Basic " + CAPABILITY, "Bearer short", "Bearer " + "A" * 64):
            with self.subTest(header_type=str(header)[:6]):
                headers = {} if header is None else {"Authorization": header}
                response = self.client.get("/forge/sessions/synthetic-session", headers=headers)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(self.manager.calls, [])

    def test_start_requires_bounded_idempotency_key(self):
        for key in (None, "", "x" * 101):
            headers = {"Authorization": self.headers["Authorization"]}
            if key is not None:
                headers["Idempotency-Key"] = key
            response = self.client.post("/forge/sessions", json=self.start, headers=headers)
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(self.manager.calls, [])

    def test_unknown_engine_and_actor_setup_fields_reject(self):
        for key, value in (("argv", ["/bin/sh"]), ("actor_id", 1), ("sessions_dir", "/tmp"), ("sideboard", [])):
            response = self.client.post("/forge/sessions", json={**self.start, key: value}, headers=self.headers)
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(self.manager.calls, [])

    def test_strict_setup_numbers_reject_boolean_and_string(self):
        for value in (False, True, "0", 2):
            response = self.client.post("/forge/sessions", json={**self.start, "human_seat": value}, headers=self.headers)
            self.assertEqual(response.status_code, 422)
        for value in (True, "60", 0, 251):
            payload = {**self.start, "deck_a": [{"card_name": "Island", "quantity": value}]}
            response = self.client.post("/forge/sessions", json=payload, headers=self.headers)
            self.assertEqual(response.status_code, 422)
        self.assertEqual(self.manager.calls, [])

    def test_saved_deck_name_length_matches_existing_import_boundary(self):
        for size, expected in ((200, 200), (201, 422)):
            response = self.client.post("/forge/sessions", json={**self.start, "name_a": "A" * size}, headers=self.headers)
            self.assertEqual(response.status_code, expected)

    def test_answer_never_accepts_client_state_actor_or_process_fields(self):
        for key, value in (("actor_id", 1), ("state", {}), ("checkpoint_request_id", REQUEST_ID), ("argv", [])):
            response = self.client.post("/forge/sessions/synthetic-session/answer", json={**self.answer, key: value}, headers=self.headers)
            self.assertEqual(response.status_code, 422)
        self.assertEqual(self.manager.calls, [])

    def test_answer_shape_and_bounded_fields(self):
        for key, value in (("tokens", ["not-native-token"]), ("tokens", [TOKEN] * 257),
                           ("request_id", "bad"), ("sequence", True), ("sequence", -1),
                           ("sequence", "0"), ("action_id", ""), ("action_id", "x" * 101)):
            response = self.client.post("/forge/sessions/synthetic-session/answer", json={**self.answer, key: value}, headers=self.headers)
            self.assertEqual(response.status_code, 422)
        self.assertEqual(self.manager.calls, [])

    def test_internal_runtime_error_is_not_echoed(self):
        from native_forge import ForgeError

        def unavailable(*_args):
            raise ForgeError(503, "forge_unavailable", "Forge runtime unavailable")

        self.manager.create = unavailable
        response = self.client.post("/forge/sessions", json=self.start, headers=self.headers)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"detail": {"code": "forge_unavailable", "message": "Forge runtime unavailable"}})
        self.assertEqual(response.headers["cache-control"], "no-store")


if __name__ == "__main__":
    unittest.main()
