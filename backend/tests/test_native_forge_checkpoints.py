"""SYNTHETIC real-child save/replay transport, not native gameplay qualification."""
import copy
from pathlib import Path
import sys
import tempfile
import time
import threading
import unittest
from unittest import mock
from concurrent.futures import ThreadPoolExecutor

from test_native_forge import NF, CAP, OTHER_CAP, payload, KEYS

CHILD = Path(__file__).with_name("native_forge_checkpoint_child.py")


class AppCheckpointTransportTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(callable(getattr(NF.ForgeManager, "checkpoint", None)), "checkpoint API missing")
        self.root = Path(tempfile.mkdtemp(prefix="forge-save-transport-"))
        self.managers = []
        self.addCleanup(self.cleanup)

    def cleanup(self):
        for manager in self.managers:
            manager.close_all()

    def manager(self, mode="normal", build="c" * 64):
        config = NF.RuntimeConfig((sys.executable, "-u", str(CHILD), mode, "{session}"),
                                  self.root, self.root / "sessions", build)
        manager = NF.ForgeManager(config)
        self.managers.append(manager)
        return manager

    def wait(self, manager, sid, condition, seconds=5):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            value = manager.get(sid, CAP)
            self.assertEqual(set(value), KEYS)
            if condition(value):
                return value
            time.sleep(.01)
        self.fail(repr(value))

    def start(self, mode="normal"):
        manager = self.manager(mode)
        value = manager.create(payload(), CAP, "start")
        sid = value["session_id"]
        return manager, sid, self.wait(manager, sid, lambda x: x["question"] is not None)

    def answer(self, manager, sid, value, action="answer"):
        request = {"sequence": value["sequence"], "request_id": value["question"]["request_id"],
                   "tokens": [value["question"]["choices"][0]["token"]], "action_id": action}
        manager.answer(sid, CAP, request)
        return request

    def save(self, manager, sid, value, action="save"):
        request = {"sequence": value["sequence"], "request_id": value["question"]["request_id"], "action_id": action}
        return manager.checkpoint(sid, CAP, request), request

    def test_save_reaps_child_and_survives_manager_shutdown(self):
        manager, sid, value = self.start()
        saved, request = self.save(manager, sid, value)
        self.assertEqual(saved["status"], "suspended")
        self.assertIsNone(saved["question"])
        self.assertEqual(saved["info"], {})
        self.assertTrue(manager._sessions[sid].closed.is_set())
        self.assertIsNotNone(manager._sessions[sid].process.poll())
        self.assertEqual(manager.checkpoint(sid, CAP, request), saved)
        manager.close_all()
        fresh = self.manager()
        with mock.patch.object(NF.subprocess, "Popen", side_effect=AssertionError("GET must not spawn")):
            read = fresh.get(sid, CAP)
        self.assertEqual(read["status"], "suspended")
        self.assertGreater(read["sequence"], saved["sequence"])

    def test_cold_resume_replays_history_fresh_tokens_old_action_idempotence(self):
        manager, sid, first = self.start()
        accepted = self.answer(manager, sid, first)
        frontier = self.wait(manager, sid, lambda x: x["question"] is not None and x["state"]["turn"] == 2)
        old_question = frontier["question"]
        saved, _ = self.save(manager, sid, frontier)
        manager.close_all()
        fresh = self.manager()
        current = fresh.get(sid, CAP)
        request = {"sequence": current["sequence"], "action_id": "resume"}
        restoring = fresh.resume(sid, CAP, request)
        self.assertIn(restoring["status"], {"restoring", "running"})
        resumed = self.wait(fresh, sid, lambda x: x["question"] is not None)
        self.assertEqual(resumed["state"], frontier["state"])
        self.assertNotEqual(resumed["question"]["request_id"], old_question["request_id"])
        self.assertGreater(resumed["sequence"], saved["sequence"])
        self.assertEqual(fresh.answer(sid, CAP, accepted)["last_answer"]["status"], "processed")
        self.assertEqual(fresh.resume(sid, CAP, request)["question"], resumed["question"])
        self.answer(fresh, sid, resumed, "second")
        next_choice = self.wait(fresh, sid, lambda x: x["question"] is not None and x["state"]["turn"] == 3)
        self.answer(fresh, sid, next_choice, "third")
        self.wait(fresh, sid, lambda x: x["status"] == "completed")
        fresh.close_all()
        self.assertEqual(self.manager().get(sid, CAP)["status"], "completed")

    def test_wrong_capability_and_build_reject_before_spawn(self):
        manager, sid, value = self.start()
        self.save(manager, sid, value)
        manager.close_all()
        fresh = self.manager(build="d" * 64)
        with mock.patch.object(NF.subprocess, "Popen", side_effect=AssertionError("must not spawn")):
            with self.assertRaises(NF.ForgeError) as wrong:
                fresh.get(sid, OTHER_CAP)
            self.assertEqual(wrong.exception.status_code, 404)
            with self.assertRaises(NF.ForgeError) as build:
                fresh.get(sid, CAP)
            self.assertEqual(build.exception.code, "build_mismatch")

    def test_explicit_delete_abandons_save(self):
        manager, sid, value = self.start()
        self.save(manager, sid, value)
        self.assertEqual(manager.close(sid, CAP)["status"], "aborted")
        manager.close_all()
        fresh = self.manager()
        value = fresh.get(sid, CAP)
        self.assertEqual(value["status"], "aborted")
        with self.assertRaises(NF.ForgeError):
            fresh.resume(sid, CAP, {"sequence": value["sequence"], "action_id": "no-resurrection"})

    def test_capture_busy_failure_and_hash_mismatch_preserve_pending_question(self):
        for mode in ("busy", "io-fail", "bad-hash"):
            with self.subTest(mode=mode):
                # Separate roots ensure this is three independent live sessions.
                self.root = Path(tempfile.mkdtemp(prefix="forge-save-failure-"))
                manager, sid, value = self.start(mode)
                with self.assertRaises(NF.ForgeError):
                    self.save(manager, sid, value)
                after = manager.get(sid, CAP)
                self.assertEqual(after["question"], value["question"])
                self.assertEqual(after["status"], "running")
                manager.close_all()

    def test_replay_mismatch_never_exposes_choice_or_overwrites_saved_frontier(self):
        manager, sid, value = self.start("mismatch")
        self.answer(manager, sid, value)
        value = self.wait(manager, sid, lambda x: x["question"] is not None and x["state"]["turn"] == 2)
        self.save(manager, sid, value)
        manager.close_all()
        fresh = self.manager("mismatch")
        value = fresh.get(sid, CAP)
        fresh.resume(sid, CAP, {"sequence": value["sequence"], "action_id": "resume-bad"})
        failed = self.wait(fresh, sid, lambda x: x["status"] == "failed")
        self.assertIsNone(failed["question"])
        fresh.close_all()
        self.assertEqual(self.manager("mismatch").get(sid, CAP)["status"], "suspended")

    def test_invalid_controls_do_not_mutate_or_send(self):
        manager, sid, value = self.start()
        for delta in ({"sequence": True}, {"sequence": value["sequence"] - 1},
                      {"request_id": "not-current"}, {"extra": None}):
            request = {"sequence": value["sequence"], "request_id": value["question"]["request_id"], "action_id": "invalid"}
            request.update(delta)
            with self.assertRaises(NF.ForgeError):
                manager.checkpoint(sid, CAP, request)
            self.assertEqual(manager.get(sid, CAP), value)

    def test_nested_incomplete_start_resumes_without_waiting_for_outer_completion(self):
        manager, sid, value = self.start("nested")
        old_answer = self.answer(manager, sid, value)
        value = self.wait(manager, sid, lambda x: x["question"] is not None and x["state"]["turn"] == 2)
        self.assertEqual(value["last_answer"]["status"], "processing")
        self.save(manager, sid, value)
        manager.close_all()
        fresh = self.manager("nested")
        value = fresh.get(sid, CAP)
        fresh.resume(sid, CAP, {"sequence": value["sequence"], "action_id": "nested-resume"})
        value = self.wait(fresh, sid, lambda x: x["question"] is not None)
        self.assertEqual(value["state"]["turn"], 2)
        self.answer(fresh, sid, value, "nested-second")
        self.wait(fresh, sid, lambda x: x["question"] is not None and x["state"]["turn"] == 3)
        self.assertEqual(fresh.answer(sid, CAP, old_answer)["last_answer"]["status"], "processed")

    def test_host_shutdown_during_resumed_play_preserves_last_saved_point(self):
        manager, sid, value = self.start()
        self.save(manager, sid, value)
        value = manager.get(sid, CAP)
        manager.resume(sid, CAP, {"sequence": value["sequence"], "action_id": "resume"})
        value = self.wait(manager, sid, lambda x: x["question"] is not None)
        self.answer(manager, sid, value)
        self.wait(manager, sid, lambda x: x["question"] is not None and x["state"]["turn"] == 2)
        manager.close_all()
        self.assertEqual(self.manager().get(sid, CAP)["status"], "suspended")

    def test_capture_fences_answers_until_worker_has_stopped(self):
        manager, sid, value = self.start("slow-capture")
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(self.save, manager, sid, value)
            until = time.monotonic() + 3
            while not (manager._sessions[sid].directory / "CAPTURE.pending").exists():
                self.assertLess(time.monotonic(), until)
                time.sleep(.005)
            with self.assertRaises(NF.ForgeError):
                self.answer(manager, sid, value)
            saved, _ = pending.result(timeout=4)
        self.assertEqual(saved["status"], "suspended")
        self.assertEqual(manager._sessions[sid].actions, {})

    def test_failed_publication_preserves_previous_save_and_live_question(self):
        manager, sid, value = self.start()
        self.save(manager, sid, value)
        current = manager.get(sid, CAP)
        manager.resume(sid, CAP, {"sequence": current["sequence"], "action_id": "resume"})
        current = self.wait(manager, sid, lambda x: x["question"] is not None)
        self.answer(manager, sid, current)
        current = self.wait(manager, sid, lambda x: x["question"] is not None and x["state"]["turn"] == 2)
        before = manager._saves.load(sid, NF._capability_hash(CAP))
        with mock.patch.object(manager._saves, "publish", side_effect=OSError("SYNTHETIC disk failure")):
            with self.assertRaises(NF.ForgeError):
                self.save(manager, sid, current, "second-save")
        self.assertEqual(manager._saves.load(sid, NF._capability_hash(CAP)), before)
        self.assertEqual(manager.get(sid, CAP)["question"], current["question"])

    def test_second_owner_cannot_start_or_resume_worker(self):
        manager, sid, value = self.start()
        second = self.manager()
        with self.assertRaises(NF.ForgeError) as error:
            second.create(payload(), CAP, "another")
        self.assertEqual(error.exception.code, "runtime_owned")
        self.assertEqual(manager.get(sid, CAP), value)

    def test_close_incomplete_invocation_reaps_and_durably_abandons(self):
        manager, sid, value = self.start("nested")
        self.save(manager, sid, value)
        value = manager.get(sid, CAP)
        manager.resume(sid, CAP, {"sequence": value["sequence"], "action_id": "resume"})
        value = self.wait(manager, sid, lambda x: x["question"] is not None)
        self.answer(manager, sid, value)
        self.wait(manager, sid, lambda x: x["question"] is not None and x["state"]["turn"] == 2)
        self.assertEqual(manager.close(sid, CAP)["status"], "aborted")
        self.assertTrue(manager._sessions[sid].closed.is_set())
        manager.close_all()
        self.assertEqual(self.manager("nested").get(sid, CAP)["status"], "aborted")

    def test_explicit_close_during_save_cannot_be_overwritten_as_suspended(self):
        manager, sid, value = self.start()
        session = manager._sessions[sid]
        stopped, release = threading.Event(), threading.Event()
        reap = session._reap
        def pause_after_reap():
            reap()
            if threading.current_thread().name.startswith("capturer"):
                stopped.set()
                self.assertTrue(release.wait(3))
        with mock.patch.object(session, "_reap", side_effect=pause_after_reap):
            with ThreadPoolExecutor(max_workers=1, thread_name_prefix="capturer") as pool:
                pending = pool.submit(self.save, manager, sid, value)
                try:
                    self.assertTrue(stopped.wait(3))
                    self.assertEqual(manager.close(sid, CAP)["status"], "aborted")
                finally:
                    release.set()
                try:
                    pending.result(timeout=4)
                except NF.ForgeError:
                    pass
        self.assertEqual(manager.get(sid, CAP)["status"], "aborted")
        manager.close_all()
        self.assertEqual(self.manager().get(sid, CAP)["status"], "aborted")

    def test_explicit_close_after_failed_replay_abandons_durable_save(self):
        manager, sid, value = self.start("mismatch")
        self.answer(manager, sid, value)
        value = self.wait(manager, sid, lambda x: x["question"] is not None and x["state"]["turn"] == 2)
        self.save(manager, sid, value)
        value = manager.get(sid, CAP)
        manager.resume(sid, CAP, {"sequence": value["sequence"], "action_id": "resume"})
        self.wait(manager, sid, lambda x: x["status"] == "failed")
        self.assertEqual(manager.close(sid, CAP)["status"], "aborted")
        manager.close_all()
        self.assertEqual(self.manager("mismatch").get(sid, CAP)["status"], "aborted")

    def test_answers_cannot_reuse_control_action_identifiers(self):
        manager, sid, value = self.start()
        self.save(manager, sid, value)
        value = manager.get(sid, CAP)
        manager.resume(sid, CAP, {"sequence": value["sequence"], "action_id": "resume-key"})
        value = self.wait(manager, sid, lambda x: x["question"] is not None)
        with self.assertRaises(NF.ForgeError) as error:
            self.answer(manager, sid, value, "resume-key")
        self.assertEqual(error.exception.code, "action_conflict")
        self.assertEqual(manager.get(sid, CAP), value)

    def test_failed_abandonment_publication_still_reaps_worker(self):
        manager, sid, value = self.start()
        self.save(manager, sid, value)
        value = manager.get(sid, CAP)
        manager.resume(sid, CAP, {"sequence": value["sequence"], "action_id": "resume"})
        self.wait(manager, sid, lambda x: x["question"] is not None)
        with mock.patch.object(manager._saves, "update", side_effect=OSError("SYNTHETIC disk failure")):
            with self.assertRaises(NF.ForgeError):
                manager.close(sid, CAP)
        self.assertTrue(manager._sessions[sid].closed.is_set())
        self.assertIsNotNone(manager._sessions[sid].process.poll())

    def test_cold_start_key_retry_returns_saved_session_without_spawning(self):
        manager, sid, value = self.start()
        self.save(manager, sid, value)
        manager.close_all()
        fresh = self.manager()
        with mock.patch.object(NF.subprocess, "Popen", side_effect=AssertionError("start retry must not spawn")):
            retry = fresh.create(payload(), CAP, "start")
        self.assertEqual(retry["session_id"], sid)
        self.assertEqual(retry["status"], "suspended")
        changed = payload()
        changed["seed"] += 1
        with self.assertRaises(NF.ForgeError) as error:
            fresh.create(changed, CAP, "start")
        self.assertEqual(error.exception.code, "start_conflict")

    def test_resume_precommit_io_failure_restores_state_and_allows_same_request(self):
        manager, sid, value = self.start()
        saved, _ = self.save(manager, sid, value)
        request = {"sequence": saved["sequence"], "action_id": "resume-io"}
        with mock.patch.object(manager._saves, "update", side_effect=NF.SaveError()):
            with self.assertRaises(NF.ForgeError):
                manager.resume(sid, CAP, request)
        self.assertEqual(manager.get(sid, CAP), saved)
        manager.resume(sid, CAP, request)
        self.wait(manager, sid, lambda x: x["question"] is not None)

    def test_committed_resume_io_failure_reconciles_before_same_key_or_cold_retry(self):
        for cold in (False, True):
            with self.subTest(cold=cold):
                self.root = Path(tempfile.mkdtemp(prefix="forge-resume-committed-"))
                manager, sid, value = self.start()
                saved, _ = self.save(manager, sid, value)
                request = {"sequence": saved["sequence"], "action_id": "resume-committed"}
                update = manager._saves.update
                def committed_then_fail(*args):
                    update(*args)
                    raise NF.SaveError(committed=True)
                with mock.patch.object(manager._saves, "update", side_effect=committed_then_fail):
                    with self.assertRaises(NF.ForgeError):
                        manager.resume(sid, CAP, request)
                self.assertIsNotNone(manager._sessions[sid].process.poll())
                if cold:
                    manager.close_all()
                    manager = self.manager()
                manager.resume(sid, CAP, request)
                self.wait(manager, sid, lambda x: x["question"] is not None)
                manager.close_all()

    def test_failed_epoch_reservation_does_not_leak_runtime_lease(self):
        manager = self.manager()
        def fail_after_acquire():
            manager._saves.acquire()
            raise NF.SaveError()
        with mock.patch.object(manager._saves, "reserve_epoch", side_effect=fail_after_acquire):
            with self.assertRaises(NF.ForgeError):
                manager.create(payload(), CAP, "failed-reservation")
        self.assertIsNone(manager._saves.lease)

    def test_save_waits_for_observed_detached_descendant_to_end(self):
        manager, sid, value = self.start("detached-exit")
        path = manager._sessions[sid].directory
        pid = int((path / "DETACHED.pid").read_text())
        saved, _ = self.save(manager, sid, value)
        self.assertEqual(saved["status"], "suspended")
        self.assertFalse(Path(f"/proc/{pid}").exists(), "save returned before observed descendant closure")

    def test_natural_completion_reaps_observed_descendant_without_explicit_close(self):
        manager, sid, value = self.start("detached-exit")
        session = manager._sessions[sid]
        pid = int((session.directory / "DETACHED.pid").read_text())
        for turn in range(1, 4):
            self.answer(manager, sid, value, f"natural-{turn}")
            value = self.wait(manager, sid, lambda x: x["question"] is not None or x["status"] == "completed")
        self.assertEqual(value["status"], "completed")
        self.assertTrue(session.closed.wait(1))
        self.assertFalse(Path(f"/proc/{pid}").exists(), "natural completion bypassed descendant finalization")

    def test_ambiguous_replay_descriptor_is_never_dispatched(self):
        manager, sid, value = self.start("ambiguous")
        self.answer(manager, sid, value)
        value = self.wait(manager, sid, lambda x: x["question"] is not None and x["state"]["turn"] == 2)
        self.save(manager, sid, value)
        manager.close_all()
        fresh = self.manager("ambiguous")
        value = fresh.get(sid, CAP)
        fresh.resume(sid, CAP, {"sequence": value["sequence"], "action_id": "ambiguous-resume"})
        failed = self.wait(fresh, sid, lambda x: x["status"] == "failed")
        self.assertIsNone(failed["question"])
        self.assertEqual(fresh._sessions[sid].starts, 0)

    def test_lost_save_response_cold_retry_is_read_only_and_idempotent(self):
        manager, sid, value = self.start()
        _, original = self.save(manager, sid, value)
        manager.close_all()
        fresh = self.manager()
        with mock.patch.object(NF.subprocess, "Popen", side_effect=AssertionError("duplicate save must not spawn")):
            first = fresh.checkpoint(sid, CAP, original)
            second = fresh.checkpoint(sid, CAP, original)
        self.assertEqual(first, second)
        self.assertEqual(first["status"], "suspended")


if __name__ == "__main__":
    unittest.main()
