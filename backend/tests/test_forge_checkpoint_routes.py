"""Synthetic checkpoint HTTP contracts, not native persistence or game proof."""
import threading
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from forge_routes import create_forge_router
from native_forge import ForgeError


CAPABILITY = "ab" * 32
SESSION_ID = "synthetic-session"
REQUEST_ID = "09090909-0909-4909-8909-090909090909"
PUBLIC_FIELDS = {"engine", "session_id", "sequence", "status", "actor_id", "state",
                 "question", "info", "last_answer", "result", "error"}


class SyntheticCheckpointManager:
    def __init__(self):
        self.calls = []
        self.threads = []
        self.error = None

    def _control(self, operation, session_id, capability, payload):
        self.calls.append((operation, session_id, capability, payload))
        self.threads.append(threading.get_ident())
        if session_id != SESSION_ID or capability != CAPABILITY:
            raise ForgeError(404, "session_not_found", "Native session not found")
        if self.error is not None:
            raise self.error
        return {"engine": "forge", "session_id": session_id, "sequence": 17,
                "status": "suspended" if operation == "checkpoint" else "restoring",
                "actor_id": 1, "state": None, "question": None, "info": {},
                "last_answer": None, "result": None, "error": None}

    def checkpoint(self, session_id, capability, payload):
        return self._control("checkpoint", session_id, capability, payload)

    def resume(self, session_id, capability, payload):
        return self._control("resume", session_id, capability, payload)


class ForgeCheckpointRouteTests(unittest.TestCase):
    def setUp(self):
        self.manager = SyntheticCheckpointManager()
        self.loop_threads = []
        app = FastAPI()

        @app.middleware("http")
        async def identify_loop(request, call_next):
            self.loop_threads.append(threading.get_ident())
            return await call_next(request)

        app.include_router(create_forge_router(lambda: self.manager))
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.headers = {"Authorization": "Bearer " + CAPABILITY}
        self.payloads = {
            "checkpoint": {"sequence": 16, "request_id": REQUEST_ID, "action_id": "save-one"},
            "resume": {"sequence": 16, "action_id": "resume-one"},
        }

    def post(self, operation, payload, *, headers=None, session_id=SESSION_ID):
        return self.client.post(f"/forge/sessions/{session_id}/{operation}", json=payload,
                                headers=self.headers if headers is None else headers)

    def assert_rejected(self, operation, payload, status=422, **kwargs):
        before = len(self.manager.calls)
        response = self.post(operation, payload, **kwargs)
        self.assertEqual(response.status_code, status, response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(len(self.manager.calls), before)
        self.assertNotIn(CAPABILITY, response.text)
        return response

    def test_checkpoint_forwards_exact_payload_and_public_eleven_fields(self):
        payload = self.payloads["checkpoint"]
        response = self.post("checkpoint", payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.manager.calls, [("checkpoint", SESSION_ID, CAPABILITY, payload)])
        self.assertEqual(response.json(), {
            "engine": "forge", "session_id": SESSION_ID, "sequence": 17, "status": "suspended",
            "actor_id": 1, "state": None, "question": None, "info": {},
            "last_answer": None, "result": None, "error": None})
        self.assertEqual(set(response.json()), PUBLIC_FIELDS)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertNotIn(CAPABILITY, response.text)

    def test_resume_forwards_exact_payload_and_public_eleven_fields(self):
        payload = self.payloads["resume"]
        response = self.post("resume", payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.manager.calls, [("resume", SESSION_ID, CAPABILITY, payload)])
        self.assertEqual(response.json(), {
            "engine": "forge", "session_id": SESSION_ID, "sequence": 17, "status": "restoring",
            "actor_id": 1, "state": None, "question": None, "info": {},
            "last_answer": None, "result": None, "error": None})
        self.assertEqual(set(response.json()), PUBLIC_FIELDS)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertNotIn(CAPABILITY, response.text)

    def test_blocking_manager_calls_are_off_the_async_event_loop(self):
        for operation, payload in self.payloads.items():
            with self.subTest(operation=operation):
                response = self.post(operation, payload)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertNotEqual(self.manager.threads[-1], self.loop_threads[-1])

    def test_all_control_fields_are_required(self):
        for operation, payload in self.payloads.items():
            for missing in payload:
                with self.subTest(operation=operation, missing=missing):
                    self.assert_rejected(operation, {k: v for k, v in payload.items() if k != missing})

    def test_checkpoint_rejects_unknown_fields_without_echoing_private_values(self):
        for key in ("tokens", "actor_id", "capability", "state", "argv", "sessions_dir", "build_id"):
            with self.subTest(key=key):
                response = self.assert_rejected("checkpoint", {
                    **self.payloads["checkpoint"], key: "PRIVATE_CONTROL_SENTINEL"})
                self.assertNotIn("PRIVATE_CONTROL_SENTINEL", response.text)

    def test_resume_rejects_checkpoint_and_private_fields(self):
        for key in ("request_id", "tokens", "checkpoint", "actor_id", "capability", "argv", "build_id"):
            with self.subTest(key=key):
                response = self.assert_rejected("resume", {
                    **self.payloads["resume"], key: "PRIVATE_CONTROL_SENTINEL"})
                self.assertNotIn("PRIVATE_CONTROL_SENTINEL", response.text)

    def test_sequence_is_a_strict_bounded_integer(self):
        for operation, payload in self.payloads.items():
            for value in (None, True, False, "16", 16.0, -1, 2**63, [], {}):
                with self.subTest(operation=operation, value=value):
                    self.assert_rejected(operation, {**payload, "sequence": value})

    def test_sequence_endpoints_are_forwarded_without_coercion(self):
        for operation, payload in self.payloads.items():
            for value in (0, 2**63 - 1):
                with self.subTest(operation=operation, value=value):
                    expected = {**payload, "sequence": value}
                    response = self.post(operation, expected)
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertEqual(self.manager.calls[-1], (operation, SESSION_ID, CAPABILITY, expected))

    def test_action_id_rejects_missing_type_empty_and_oversized_values(self):
        for operation, payload in self.payloads.items():
            for value in (None, True, 7, [], {}, "", "x" * 101):
                with self.subTest(operation=operation, value=value):
                    self.assert_rejected(operation, {**payload, "action_id": value})

    def test_action_id_length_boundaries_are_forwarded(self):
        for operation, payload in self.payloads.items():
            for value in ("x", "x" * 100):
                with self.subTest(operation=operation, size=len(value)):
                    expected = {**payload, "action_id": value}
                    response = self.post(operation, expected)
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertEqual(self.manager.calls[-1], (operation, SESSION_ID, CAPABILITY, expected))

    def test_checkpoint_request_id_requires_an_existing_native_token_shape(self):
        for value in (None, True, 7, [], {}, "", "not-native", REQUEST_ID + "x", " " + REQUEST_ID):
            with self.subTest(value=value):
                self.assert_rejected("checkpoint", {**self.payloads["checkpoint"], "request_id": value})

    def test_non_object_and_malformed_json_bodies_fail_closed(self):
        for operation in self.payloads:
            for value in (None, [], "PRIVATE_CONTROL_SENTINEL", 1):
                with self.subTest(operation=operation, value=value):
                    response = self.assert_rejected(operation, value)
                    self.assertNotIn("PRIVATE_CONTROL_SENTINEL", response.text)
            response = self.client.post(f"/forge/sessions/{SESSION_ID}/{operation}",
                                        content='{"sequence":', headers={
                                            **self.headers, "Content-Type": "application/json"})
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(self.manager.calls, [])

    def test_missing_and_malformed_capability_never_reaches_manager(self):
        for operation, payload in self.payloads.items():
            for header in (None, "Basic " + CAPABILITY, "Bearer short", "Bearer " + "A" * 64):
                with self.subTest(operation=operation, header=header):
                    headers = {} if header is None else {"Authorization": header}
                    response = self.assert_rejected(operation, payload, 401, headers=headers)
                    self.assertEqual(response.headers["www-authenticate"], "Bearer")

    def test_manager_ownership_failures_preserve_the_same_not_found_response(self):
        for operation, payload in self.payloads.items():
            for sid, cap in ((SESSION_ID, "cd" * 32), ("unowned-session", CAPABILITY)):
                with self.subTest(operation=operation, sid=sid):
                    response = self.post(operation, payload, session_id=sid,
                                         headers={"Authorization": "Bearer " + cap})
                    self.assertEqual(response.status_code, 404)
                    self.assertEqual(response.json(), {"detail": {
                        "code": "session_not_found", "message": "Native session not found"}})
                    self.assertEqual(response.headers["cache-control"], "no-store")
                    self.assertEqual(self.manager.calls[-1], (operation, sid, cap, payload))
                    self.assertNotIn(cap, response.text)

    def test_manager_errors_use_the_existing_private_http_translation(self):
        for operation, payload in self.payloads.items():
            for status, code, message in ((409, "session_busy", "Native session is busy"),
                                          (503, "save_unavailable", "Native save unavailable")):
                with self.subTest(operation=operation, status=status):
                    self.manager.error = ForgeError(status, code, message)
                    response = self.post(operation, payload)
                    self.assertEqual(response.status_code, status)
                    self.assertEqual(response.json(), {"detail": {"code": code, "message": message}})
                    self.assertEqual(response.headers["cache-control"], "no-store")
                    self.assertEqual(self.manager.calls[-1], (operation, SESSION_ID, CAPABILITY, payload))


if __name__ == "__main__":
    unittest.main()
