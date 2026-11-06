"""Real child-process TRANSPORT tests. No native games, HTTP, main or database."""
import copy
import fcntl
import importlib.util
import json
import os
import queue
from pathlib import Path
import signal
import stat
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
import time
import unittest
from unittest import mock


MODULE = Path(__file__).resolve().parents[1] / "native_forge.py"
CHILD = Path(__file__).with_name("native_forge_transport_child.py")
NF = None
if MODULE.exists():
    spec = importlib.util.spec_from_file_location("native_forge", MODULE)
    NF = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = NF
    spec.loader.exec_module(NF)

CAP = "a" * 64
OTHER_CAP = "b" * 64
KEYS = {"engine", "session_id", "sequence", "status", "actor_id", "state", "question",
        "info", "last_answer", "result", "error"}


def payload():
    return {"deck_a": [{"quantity": 30, "card_name": "SYNTHETIC A"},
                       {"quantity": 30, "card_name": "SYNTHETIC A"}],
            "deck_b": [{"quantity": 60, "card_name": "SYNTHETIC B"}],
            "name_a": "SYNTHETIC ALPHA", "name_b": "SYNTHETIC BETA", "human_seat": 0,
            "seed": 123}


class SyntheticForgeProcessOwnerTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(NF, "Task 1 process owner has not been implemented")
        self.root = Path(tempfile.mkdtemp(prefix="forge-transport-"))
        self.managers = []
        self.addCleanup(self.close_managers)

    def close_managers(self):
        for manager in self.managers:
            manager.close_all()

    def manager(self, mode="nested"):
        config_path = self.root / ("config-" + str(len(self.managers)) + ".json")
        config_path.write_text(json.dumps({
            "argv": [sys.executable, "-u", str(CHILD), mode, "{session}"],
            "cwd": str(self.root), "sessions_dir": str(self.root / ("sessions-" + str(len(self.managers)))),
            "build_id": "c" * 64}))
        manager = NF.ForgeManager(NF.RuntimeConfig.from_file(config_path))
        self.managers.append(manager)
        return manager

    def wait(self, manager, sid, predicate, timeout=4):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            snapshot = manager.get(sid, CAP)
            self.assertEqual(set(snapshot), KEYS)
            if predicate(snapshot):
                return snapshot
            time.sleep(.01)
        self.fail("Transport snapshot did not reach expected state: " + repr(snapshot))

    def start(self, mode="nested", value=None):
        manager = self.manager(mode)
        snapshot = manager.create(payload() if value is None else value, CAP, "start-1")
        sid = snapshot["session_id"]
        snapshot = self.wait(manager, sid, lambda row: row["question"] is not None
                             or row["status"] in {"failed", "aborted", "completed"})
        return manager, sid, snapshot

    def directory(self, sid):
        return next(self.root.glob("sessions-*/" + sid))

    def answer_payload(self, snapshot, action="action-1"):
        return {"request_id": snapshot["question"]["request_id"],
                "tokens": [snapshot["question"]["choices"][0]["token"]],
                "sequence": snapshot["sequence"], "action_id": action}

    def received(self, sid):
        path = self.directory(sid) / "RECEIVED.private.jsonl"
        return path.read_text().splitlines() if path.exists() else []

    def expect_error(self, operation, status=None):
        with self.assertRaises(NF.ForgeError) as caught:
            operation()
        self.assertIsInstance(caught.exception.code, str)
        self.assertIsInstance(caught.exception.message, str)
        if status is not None:
            self.assertEqual(caught.exception.status_code, status)
        return caught.exception

    def test_error_abi(self):
        error = NF.ForgeError(409, "stale", "Read current question")
        self.assertEqual((error.status_code, error.code, error.message),
                         (409, "stale", "Read current question"))

    def test_disabled_environment_has_no_filesystem_side_effects(self):
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(Path, "mkdir") as mkdir:
            manager = NF.ForgeManager.from_environment()
            self.assertFalse(manager.available)
            self.expect_error(lambda: manager.create(payload(), CAP, "key"), 503)
            manager.close_all()
            mkdir.assert_not_called()

    def test_environment_loads_only_operator_config(self):
        manager = self.manager("hold")
        with mock.patch.dict(os.environ, {"MTG_FORGE_RUNTIME_CONFIG": str(self.root / "config-0.json")}):
            loaded = NF.ForgeManager.from_environment()
            self.managers.append(loaded)
            self.assertTrue(loaded.available)
        self.assertTrue(manager.available)

    def test_runtime_config_validation(self):
        self.manager("hold")
        base = json.loads((self.root / "config-0.json").read_text())
        for change in ({"argv": ["python", "{session}"]}, {"argv": "shell command"},
                       {"argv": [sys.executable, "nul\x00", "{session}"]},
                       {"argv": [sys.executable, "{browser}"]}, {"cwd": "relative"},
                       {"sessions_dir": "relative"}, {"build_id": "BAD"}, {"extra": True}):
            with self.subTest(change=change):
                path = self.root / "bad-config.json"
                path.write_text(json.dumps({**base, **change}))
                self.expect_error(lambda: NF.RuntimeConfig.from_file(path))

    def test_runtime_config_rejects_duplicate_keys(self):
        path = self.root / "duplicate.json"
        path.write_text('{"argv":[],"argv":[]}')
        self.expect_error(lambda: NF.RuntimeConfig.from_file(path))

    def test_symlink_session_root_rejected(self):
        self.manager("hold")
        config = json.loads((self.root / "config-0.json").read_text())
        target = self.root / "target"
        target.mkdir(mode=0o700)
        link = self.root / "link"
        link.symlink_to(target, target_is_directory=True)
        config["sessions_dir"] = str(link)
        path = self.root / "symlink.json"
        path.write_text(json.dumps(config))
        self.expect_error(lambda: NF.RuntimeConfig.from_file(path))

    def test_snapshot_exact_shape_detached_and_no_capability(self):
        manager, sid, snapshot = self.start("hold")
        self.assertEqual(snapshot["engine"], "forge")
        self.assertEqual(snapshot["actor_id"], 17)
        self.assertIsNone(snapshot["last_answer"])
        self.assertIsNone(snapshot["result"])
        snapshot["state"]["players"].clear()
        self.assertEqual(len(manager.get(sid, CAP)["state"]["players"]), 2)
        self.assertNotIn(CAP, json.dumps(manager.get(sid, CAP)))

    def test_capabilities_gate_get_answer_close(self):
        manager, sid, snapshot = self.start("hold")
        for operation in (lambda: manager.get(sid, OTHER_CAP),
                          lambda: manager.answer(sid, OTHER_CAP, self.answer_payload(snapshot)),
                          lambda: manager.close(sid, OTHER_CAP)):
            self.expect_error(operation)
        self.assertIsNotNone(manager.get(sid, CAP)["question"])
        self.assertEqual(self.received(sid), [])

    def test_invalid_capability_rejected_before_start(self):
        manager = self.manager()
        for cap in ("A" * 64, "a" * 63, "", None, True):
            with self.subTest(cap=cap):
                self.expect_error(lambda: manager.create(payload(), cap, "start"))
        self.assertFalse(list(self.root.glob("sessions-*/*")))

    def test_start_idempotency_and_conflict(self):
        manager, sid, _ = self.start("hold")
        self.assertEqual(manager.create(payload(), CAP, "start-1")["session_id"], sid)
        changed = payload()
        changed["seed"] += 1
        self.expect_error(lambda: manager.create(changed, CAP, "start-1"), 409)
        self.assertEqual(len(list(self.root.glob("sessions-*/*"))), 1)

    def test_start_keys_and_action_keys_are_bounded(self):
        manager = self.manager("hold")
        for key in ("", "x" * 101, "bad\nkey", None):
            with self.subTest(key=key):
                self.expect_error(lambda: manager.create(payload(), CAP, key))

    def test_two_live_workers_limit_and_close_releases_slot(self):
        manager, sid, _ = self.start("hold")
        second = manager.create(payload(), CAP, "second")
        self.expect_error(lambda: manager.create(payload(), CAP, "third"), 503)
        manager.close(sid, CAP)
        third = manager.create(payload(), CAP, "third")
        self.assertNotEqual(third["session_id"], second["session_id"])

    def test_terminal_cache_evicts_only_closed_sessions(self):
        with mock.patch.object(NF, "_MAX_RECORDS", 2):
            manager, old, _ = self.start("hold")
            manager.close(old, CAP)
            active = manager.create(payload(), CAP, "active")["session_id"]
            newer = manager.create(payload(), CAP, "newer")["session_id"]
            self.expect_error(lambda: manager.get(old, CAP), 404)
            self.assertEqual(manager.create(payload(), CAP, "active")["session_id"], active)
            self.assertEqual(manager.create(payload(), CAP, "newer")["session_id"], newer)

    def test_cache_never_evicts_active_start_receipt(self):
        with mock.patch.object(NF, "_MAX_RECORDS", 1):
            manager, sid, _ = self.start("hold")
            self.expect_error(lambda: manager.create(payload(), CAP, "other"), 503)
            self.assertEqual(manager.create(payload(), CAP, "start-1")["session_id"], sid)

    def test_capacity_counts_actual_process_even_after_reader_closed_flag(self):
        manager, sid, _ = self.start("hold")
        manager.close(sid, CAP)
        manager.create(payload(), CAP, "second")
        process = manager._sessions[sid].process
        with mock.patch.object(process, "poll", return_value=None):
            self.expect_error(lambda: manager.create(payload(), CAP, "third"), 503)

    def test_concurrent_start_retries_create_one_child(self):
        manager = self.manager("hold")
        with ThreadPoolExecutor(max_workers=2) as pool:
            snapshots = list(pool.map(lambda _: manager.create(payload(), CAP, "same"), range(2)))
        self.assertEqual(snapshots[0]["session_id"], snapshots[1]["session_id"])
        self.assertEqual(len(list(self.root.glob("sessions-*/*"))), 1)

    def test_private_files_and_native_spec_exact_gson_names(self):
        manager, sid, _ = self.start("hold")
        directory = self.directory(sid)
        spec = json.loads((directory / "SPEC.json").read_text())
        self.assertEqual(spec, {"human_seat": 0, "open_decklists": True, "flat_monte_carlo": False,
                                "seed": 123, "decks": [
                                    {"file": "a.dck", "name": "SYNTHETIC ALPHA", "main": {"SYNTHETIC A": 60}},
                                    {"file": "b.dck", "name": "SYNTHETIC BETA", "main": {"SYNTHETIC B": 60}}]})
        self.assertEqual((directory / "decks" / "a.dck").read_text(),
                         "[metadata]\nName=SYNTHETIC ALPHA\n[Main]\n60 SYNTHETIC A\n")
        manager.close(sid, CAP)
        for path in [directory.parent, directory, *directory.rglob("*")]:
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700 if path.is_dir() else 0o600)

    def test_absent_seed_generates_native_integer_seed(self):
        value = payload()
        del value["seed"]
        _, sid, _ = self.start("hold", value)
        spec = json.loads((self.directory(sid) / "SPEC.json").read_text())
        self.assertIs(type(spec["seed"]), int)
        self.assertLess(spec["seed"], 2**63)

    def test_invalid_decks_and_browser_fields_rejected_before_process(self):
        manager = self.manager("hold")
        cases = []
        for field, value in (("deck_a", [{"quantity": 59, "card_name": "X"}]),
                             ("deck_b", [{"quantity": True, "card_name": "X"}]),
                             ("human_seat", True), ("seed", True), ("seed", -1),
                             ("argv", ["/bin/sh"]), ("actor_id", 17), ("state", {})):
            cases.append({**payload(), field: value})
        for index, value in enumerate(cases):
            with self.subTest(index=index):
                self.expect_error(lambda: manager.create(value, CAP, str(index)))
        self.assertFalse(list(self.root.glob("sessions-*/*")))

    def test_deck_name_line_and_section_injection_rejected(self):
        manager = self.manager("hold")
        for index, name in enumerate(("bad\n[Sideboard]\n1 Card", "[Main]", "bad\rname", "bad\x00name")):
            for field in ("name_a", "card_name"):
                value = payload()
                if field == "card_name":
                    value["deck_b"][0][field] = name
                else:
                    value[field] = name
                with self.subTest(name=name, field=field):
                    self.expect_error(lambda: manager.create(value, CAP, str(index) + field))

    def test_invalid_unicode_request_text_rejected_safely(self):
        manager = self.manager("hold")
        value = payload()
        value["name_a"] = "\ud800"
        self.expect_error(lambda: manager.create(value, CAP, "unicode"), 422)
        self.expect_error(lambda: manager.create(payload(), CAP, "\ud800"), 422)

    def test_saved_deck_name_200_boundary(self):
        value = payload()
        value["name_a"] = "A" * 200
        value["name_b"] = "B" * 200
        manager, sid, _ = self.start("hold", value)
        saved = json.loads((self.directory(sid) / "SPEC.json").read_text())
        self.assertEqual([row["name"] for row in saved["decks"]], ["A" * 200, "B" * 200])
        for field in ("name_a", "name_b"):
            changed = copy.deepcopy(value)
            changed[field] += "X"
            self.expect_error(lambda: manager.create(changed, CAP, field), 422)

    def test_card_name_200_boundary(self):
        value = payload()
        value["deck_b"][0]["card_name"] = "C" * 200
        manager, sid, _ = self.start("hold", value)
        saved = json.loads((self.directory(sid) / "SPEC.json").read_text())
        self.assertEqual(saved["decks"][1]["main"], {"C" * 200: 60})
        value["deck_b"][0]["card_name"] += "X"
        self.expect_error(lambda: manager.create(value, CAP, "too-long-card"), 422)

    def test_projection_strips_private_worker_fields(self):
        manager, sid, _ = self.start("projection")
        serialized = json.dumps(manager.get(sid, CAP))
        for word in ("PRIVATE", "native_state", "journals", "provenance", "replay_offer"):
            self.assertNotIn(word, serialized)

    def test_authorized_library_reveal_is_preserved_with_nested_allowlists(self):
        _, _, snapshot = self.start("reveal")
        library = snapshot["state"]["players"][1]["zones"]["Library"]
        self.assertEqual(library["count"], 60)
        self.assertEqual(library["visible_cards"][0]["face"]["name"], "SYNTHETIC AUTHORIZED REVEAL")
        self.assertNotIn("private", json.dumps(snapshot))

    def test_surrogate_worker_text_fails_closed(self):
        manager, sid, _ = self.start("surrogate")
        self.wait(manager, sid, lambda row: row["status"] == "failed")

    def test_views_do_not_mix_new_state_with_existing_question(self):
        manager, sid, snapshot = self.start("defer")
        time.sleep(.08)
        stable = manager.get(sid, CAP)
        self.assertEqual(stable["state"]["turn"], 1)
        self.assertEqual(stable["sequence"], snapshot["sequence"])
        manager.answer(sid, CAP, self.answer_payload(stable))
        next_snapshot = self.wait(manager, sid, lambda row: row["question"] is not None)
        self.assertEqual(next_snapshot["state"]["turn"], 2)

    def test_get_never_writes_stdin(self):
        manager, sid, _ = self.start("hold")
        for _ in range(5):
            manager.get(sid, CAP)
        self.assertEqual(self.received(sid), [])

    def test_sequence_request_token_and_bounds_gate_answer(self):
        manager, sid, snapshot = self.start("hold")
        good = self.answer_payload(snapshot)
        for index, change in enumerate(({"sequence": snapshot["sequence"] - 1}, {"sequence": True},
                                        {"request_id": "00000000-0000-0000-0000-000000000099"},
                                        {"tokens": []}, {"tokens": [good["tokens"][0]] * 2},
                                        {"tokens": ["00000000-0000-0000-0000-000000000099"]},
                                        {"actor_id": 17}, {"action_id": "x" * 101})):
            with self.subTest(change=change):
                self.expect_error(lambda: manager.answer(sid, CAP, {**good, "action_id": str(index), **change}))
        self.assertEqual(self.received(sid), [])
        self.assertIsNotNone(manager.get(sid, CAP)["question"])

    def test_answer_order_is_sent_exactly_without_client_metadata(self):
        manager, sid, snapshot = self.start("selection")
        answer = self.answer_payload(snapshot)
        answer["tokens"] = [row["token"] for row in reversed(snapshot["question"]["choices"])]
        manager.answer(sid, CAP, answer)
        self.wait(manager, sid, lambda row: row["last_answer"]["status"] == "processed")
        self.assertEqual(json.loads(self.received(sid)[0]),
                         {"request_id": answer["request_id"], "tokens": answer["tokens"]})

    def test_action_idempotency_does_not_repeat_pipe_write(self):
        manager, sid, snapshot = self.start("hold")
        answer = self.answer_payload(snapshot)
        manager.answer(sid, CAP, answer)
        duplicate = manager.answer(sid, CAP, copy.deepcopy(answer))
        self.assertEqual(duplicate["last_answer"], {"action_id": "action-1", "request_id": answer["request_id"],
                                                   "status": "submitted", "reason": None})
        time.sleep(.05)
        self.assertEqual(len(self.received(sid)), 1)
        self.expect_error(lambda: manager.answer(sid, CAP, {**answer, "tokens": []}), 409)

    def test_concurrent_answer_retries_write_once(self):
        manager, sid, snapshot = self.start("hold")
        answer = self.answer_payload(snapshot)
        with ThreadPoolExecutor(max_workers=2) as pool:
            rows = list(pool.map(lambda _: manager.answer(sid, CAP, answer), range(2)))
        self.assertEqual(rows[0]["last_answer"], rows[1]["last_answer"])
        time.sleep(.05)
        self.assertEqual(len(self.received(sid)), 1)

    def test_receipt_cache_is_bounded_before_another_write(self):
        with mock.patch.object(NF, "_MAX_ACTIONS", 1):
            manager, sid, snapshot = self.start("selection")
            answer = self.answer_payload(snapshot)
            answer["tokens"] = [row["token"] for row in snapshot["question"]["choices"]]
            manager.answer(sid, CAP, answer)
            newer = self.wait(manager, sid, lambda row: row["question"] is not None)
            self.expect_error(lambda: manager.answer(sid, CAP, self.answer_payload(newer, "second")))
            self.assertEqual(len(self.received(sid)), 1)

    def test_nested_receipts_started_is_processing_not_acceptance(self):
        manager, sid, first = self.start()
        answer = self.answer_payload(first)
        manager.answer(sid, CAP, answer)
        nested = self.wait(manager, sid, lambda row: row["question"] is not None)
        self.assertEqual(nested["last_answer"]["status"], "processing")
        self.assertIsNone(nested["last_answer"]["reason"])
        second = self.answer_payload(nested, "action-2")
        manager.answer(sid, CAP, second)
        third = self.wait(manager, sid, lambda row: row["question"] is not None)
        self.assertEqual(third["last_answer"]["action_id"], "action-2")
        self.assertEqual(third["last_answer"]["status"], "processed")
        replay_parent = manager.answer(sid, CAP, answer)
        self.assertEqual(replay_parent["last_answer"]["status"], "processing")
        self.assertEqual(replay_parent["question"], third["question"])
        (self.directory(sid) / "RELEASE_PARENT").touch(mode=0o600)
        time.sleep(.08)
        parent = manager.answer(sid, CAP, answer)
        self.assertEqual(parent["last_answer"]["status"], "processed")
        self.assertEqual(manager.get(sid, CAP)["last_answer"]["action_id"], "action-2")
        self.assertEqual(len(self.received(sid)), 2)

    def test_stale_native_rejection_preserves_newer_question(self):
        manager, sid, snapshot = self.start("reject")
        manager.answer(sid, CAP, self.answer_payload(snapshot))
        newer = self.wait(manager, sid, lambda row: row["last_answer"] is not None
                          and row["last_answer"]["status"] == "rejected")
        self.assertNotEqual(newer["question"]["request_id"], snapshot["question"]["request_id"])

    def test_partial_lines_are_reassembled(self):
        _, _, snapshot = self.start("partial")
        self.assertEqual(snapshot["question"]["kind"], "confirm")

    def test_private_checkpoint_frames_are_ignored(self):
        manager, sid, snapshot = self.start("private-checkpoint")
        time.sleep(.05)
        self.assertEqual(manager.get(sid, CAP), snapshot)

    def test_malformed_frames_fail_closed_and_reap(self):
        for mode in ("bad-json", "bad-utf8", "duplicate-json", "unknown", "partial-eof",
                     "foreign-question", "foreign-view", "duplicate-token", "oversize"):
            with self.subTest(mode=mode):
                manager, sid, _ = self.start(mode)
                snapshot = self.wait(manager, sid, lambda row: row["status"] == "failed")
                self.assertIsNone(snapshot["question"])
                self.assertIsNone(snapshot["result"])
                self.assertNotIn("PRIVATE", json.dumps(snapshot["error"]))
                manager.close(sid, CAP)

    def test_invalid_started_and_completion_domains_fail(self):
        for mode in ("bad-start", "bad-completion"):
            with self.subTest(mode=mode):
                manager, sid, snapshot = self.start(mode)
                manager.answer(sid, CAP, self.answer_payload(snapshot))
                self.wait(manager, sid, lambda row: row["status"] == "failed")

    def test_unexpected_eof_is_failure_not_result(self):
        manager, sid, _ = self.start("eof")
        snapshot = self.wait(manager, sid, lambda row: row["status"] == "failed")
        self.assertIsNone(snapshot["result"])

    def test_abort_is_not_game_completion(self):
        manager, sid, _ = self.start("aborted")
        snapshot = self.wait(manager, sid, lambda row: row["status"] == "aborted")
        self.assertIsNone(snapshot["result"])

    def test_native_error_is_sanitized(self):
        manager, sid, _ = self.start("error")
        snapshot = self.wait(manager, sid, lambda row: row["status"] == "failed")
        self.assertNotIn("PRIVATE", json.dumps(snapshot))

    def test_completion_requires_result_and_clean_exit(self):
        manager, sid, snapshot = self.start("finish")
        manager.answer(sid, CAP, self.answer_payload(snapshot))
        done = self.wait(manager, sid, lambda row: row["status"] == "completed")
        self.assertEqual(done["result"], {"outcomes": ["SYNTHETIC TRANSPORT ONLY"],
                                         "turns": 3, "draw": False, "win_condition": "SYNTHETIC"})
        self.assertIsNone(done["question"])
        self.assertEqual(manager.close(sid, CAP)["status"], "completed")

    def test_result_with_nonzero_exit_is_failure(self):
        manager, sid, snapshot = self.start("result-nonzero")
        manager.answer(sid, CAP, self.answer_payload(snapshot))
        done = self.wait(manager, sid, lambda row: row["status"] == "failed")
        self.assertIsNone(done["result"])

    def test_result_without_exit_is_bounded_failure(self):
        with mock.patch.object(NF, "_EXIT_GRACE", .12):
            manager, sid, snapshot = self.start("result-hang")
            manager.answer(sid, CAP, self.answer_payload(snapshot))
            done = self.wait(manager, sid, lambda row: row["status"] == "failed")
            self.assertIsNone(done["result"])

    def test_idle_bound_reaps_silent_process(self):
        with mock.patch.object(NF, "_IDLE_TIMEOUT", .12):
            manager = self.manager("silent")
            sid = manager.create(payload(), CAP, "silent")["session_id"]
            done = self.wait(manager, sid, lambda row: row["status"] == "failed")
            self.assertEqual(done["error"]["code"], "native_idle_timeout")

    def test_human_session_timeout_defaults(self):
        self.assertEqual(NF._WALL_TIMEOUT, 7200)
        self.assertEqual(NF._IDLE_TIMEOUT, 600)

    def test_answer_activity_resets_idle_deadline_without_get_extending_it(self):
        with mock.patch.object(NF, "_IDLE_TIMEOUT", .4):
            manager, sid, snapshot = self.start("hold")
            time.sleep(.25)
            manager.answer(sid, CAP, self.answer_payload(snapshot))
            time.sleep(.2)
            self.assertEqual(manager.get(sid, CAP)["status"], "running")
            self.wait(manager, sid, lambda row: row["status"] == "failed")

    def test_wall_bound_reaps_worker(self):
        with mock.patch.object(NF, "_WALL_TIMEOUT", .12):
            manager, sid, _ = self.start("hold")
            done = self.wait(manager, sid, lambda row: row["status"] == "failed")
            self.assertEqual(done["error"]["code"], "native_wall_timeout")

    def test_stderr_transcript_is_bounded(self):
        with mock.patch.object(NF, "_TRANSCRIPT_LIMIT", 32768):
            manager, sid, _ = self.start("stderr-flood")
            done = self.wait(manager, sid, lambda row: row["status"] == "failed")
            self.assertEqual(done["error"]["code"], "native_output_limit")

    def test_frame_count_is_bounded(self):
        with mock.patch.object(NF, "_FRAME_COUNT_LIMIT", 5):
            manager, sid, _ = self.start("frame-flood")
            self.wait(manager, sid, lambda row: row["status"] == "failed")

    def test_partial_launch_failure_closes_every_open_private_file(self):
        manager = self.manager("hold")
        opened = []
        real_open = NF._private_file

        def fail_second_log(path):
            if path.name == "stderr.private.log":
                raise OSError("PRIVATE SYNTHETIC filesystem error")
            handle = real_open(path)
            opened.append(handle)
            return handle

        with mock.patch.object(NF, "_private_file", side_effect=fail_second_log):
            snapshot = manager.create(payload(), CAP, "failure")
        self.assertEqual(snapshot["status"], "failed")
        self.assertTrue(all(handle.closed for handle in opened))

    def test_reader_start_failure_reaps_launched_process(self):
        manager = self.manager("hold")
        children = []
        real_popen = NF.subprocess.Popen

        def observe_child(*args, **kwargs):
            child = real_popen(*args, **kwargs)
            children.append(child)

            def reap_even_if_owner_fails():
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait(timeout=2)
                for pipe in (child.stdin, child.stdout, child.stderr):
                    pipe.close()

            self.addCleanup(reap_even_if_owner_fails)
            return child

        with mock.patch.object(NF.subprocess, "Popen", side_effect=observe_child), mock.patch.object(
                NF.threading.Thread, "start", side_effect=RuntimeError("SYNTHETIC start failure")):
            snapshot = manager.create(payload(), CAP, "reader-failure")
        self.assertEqual(snapshot["status"], "failed")
        # A child must not launch when its lifetime-owning reader could not start.
        self.assertEqual(children, [])

    def test_launch_failure_is_visible_after_bounded_reader_handshake(self):
        manager = self.manager("hold")
        with mock.patch.object(NF.subprocess, "Popen", side_effect=OSError("PRIVATE SYNTHETIC launch")):
            snapshot = manager.create(payload(), CAP, "launch-failure")
        session = manager._sessions[snapshot["session_id"]]
        self.assertEqual(snapshot["status"], "failed")
        self.assertEqual(snapshot["error"]["code"], "native_launch_failed")
        self.assertTrue(session.closed.is_set())
        self.assertFalse(session.reader.is_alive())
        self.assertTrue(all(handle.closed for handle in session.files))

    def test_close_before_delayed_popen_return_reaps_late_child(self):
        manager = self.manager("hold")
        release = threading.Event()
        entered = threading.Event()
        children = []
        real_popen = NF.subprocess.Popen

        def delayed_popen(*args, **kwargs):
            entered.set()
            self.assertTrue(release.wait(timeout=3))
            child = real_popen(*args, **kwargs)
            children.append(child)
            return child

        try:
            with mock.patch.object(NF, "_LAUNCH_TIMEOUT", .05), mock.patch.object(
                    NF.subprocess, "Popen", side_effect=delayed_popen):
                snapshot = manager.create(payload(), CAP, "delayed-launch")
                self.assertTrue(entered.is_set())
                self.assertEqual(snapshot["error"]["code"], "native_launch_timeout")
                sid = snapshot["session_id"]
                session = manager._sessions[sid]
                self.assertIsNone(session.process)
                with ThreadPoolExecutor(max_workers=1) as pool:
                    closing = pool.submit(manager.close, sid, CAP)
                    self.assertTrue(session.stopping.is_set())
                    release.set()
                    self.assertEqual(closing.result(timeout=3)["status"], "failed")
                self.assertEqual(len(children), 1)
                self.assertIsNotNone(children[0].poll())
                self.assertTrue(all(pipe.closed for pipe in (children[0].stdin, children[0].stdout, children[0].stderr)))
                self.assertFalse(session.reader.is_alive())
                self.assertTrue(session.closed.is_set())
        finally:
            release.set()

    def test_close_before_launcher_run_skips_popen(self):
        manager = self.manager("hold")
        release = threading.Event()
        run = NF._Session._run

        def delayed_run(session):
            self.assertTrue(release.wait(timeout=3))
            run(session)

        try:
            with mock.patch.object(NF, "_LAUNCH_TIMEOUT", .05), mock.patch.object(
                    NF._Session, "_run", delayed_run), mock.patch.object(NF.subprocess, "Popen") as launch:
                snapshot = manager.create(payload(), CAP, "not-yet-launched")
                sid = snapshot["session_id"]
                self.assertEqual(snapshot["error"]["code"], "native_launch_timeout")
                with ThreadPoolExecutor(max_workers=1) as pool:
                    closing = pool.submit(manager.close, sid, CAP)
                    release.set()
                    closing.result(timeout=3)
                launch.assert_not_called()
                self.assertTrue(manager._sessions[sid].closed.is_set())
                self.assertTrue(all(handle.closed for handle in manager._sessions[sid].files))
        finally:
            release.set()

    def test_close_sends_eof_reaps_group_and_joins_reader(self):
        manager, sid, snapshot = self.start("group")
        directory = self.directory(sid)
        deadline = time.monotonic() + 3
        while not (directory / "DESCENDANT.pid").exists() and time.monotonic() < deadline:
            time.sleep(.01)
        pid = int((directory / "TRANSPORT.pid").read_text())
        descendant = int((directory / "DESCENDANT.pid").read_text())
        self.assertEqual(os.getpgid(pid), pid)
        manager.answer(sid, CAP, self.answer_payload(snapshot))
        closed = manager.close(sid, CAP)
        self.assertEqual(closed["status"], "aborted")
        self.assertEqual(closed["last_answer"]["status"], "uncertain")
        self.assertIsNone(closed["question"])
        self.assertEqual(manager.close(sid, CAP), closed)
        for process_id in (pid, descendant):
            with self.assertRaises(ProcessLookupError):
                os.kill(process_id, 0)

    def test_close_all_disables_creation_and_reaps_owned_children(self):
        manager, sid, _ = self.start("hold")
        manager.close_all()
        self.assertFalse(manager.available)
        self.assertEqual(manager.get(sid, CAP)["status"], "aborted")
        self.expect_error(lambda: manager.create(payload(), CAP, "later"), 503)

    def test_close_all_attempts_other_children_if_one_close_fails(self):
        manager, sid, _ = self.start("hold")
        other = manager.create(payload(), CAP, "second")["session_id"]
        with mock.patch.object(manager._sessions[sid], "close", side_effect=NF.ForgeError(
                503, "native_close_timeout", "Native shutdown pending")):
            self.expect_error(manager.close_all, 503)
            self.assertEqual(manager.get(other, CAP)["status"], "aborted")

    def test_uncertain_pipe_write_is_never_retried(self):
        manager, sid, snapshot = self.start("hold")
        answer = self.answer_payload(snapshot)
        real_write = os.write

        def fail_pipe(fd, data):
            if bytes(data).startswith(b'{"request_id"'):
                raise BrokenPipeError()
            return real_write(fd, data)

        with mock.patch.object(os, "write", side_effect=fail_pipe):
            receipt = manager.answer(sid, CAP, answer)
        self.assertEqual(receipt["last_answer"]["status"], "uncertain")
        self.assertEqual(manager.answer(sid, CAP, answer)["last_answer"]["status"], "uncertain")
        self.assertEqual(self.received(sid), [])

    def test_high_fd_stdin_delivers_answer_to_genuine_transport_child(self):
        manager, sid, snapshot = self.start("finish")
        session = manager._sessions[sid]
        with session.lock:
            original = session.process.stdin
            high_fd = fcntl.fcntl(original.fileno(), fcntl.F_DUPFD_CLOEXEC, 1024)
            try:
                replacement = os.fdopen(high_fd, "wb", buffering=0)
            except BaseException:
                os.close(high_fd)
                raise
            session.process.stdin = replacement
            original.close()
            self.assertGreaterEqual(replacement.fileno(), 1024)
        answer = self.answer_payload(snapshot)
        manager.answer(sid, CAP, answer)
        done = self.wait(manager, sid, lambda row: row["status"] in {"completed", "failed"})
        self.assertEqual(done["status"], "completed")
        self.assertEqual(done["last_answer"]["status"], "processed")
        self.assertEqual([json.loads(line) for line in self.received(sid)],
                         [{"request_id": answer["request_id"], "tokens": answer["tokens"]}])

    def test_request_thread_exit_preserves_parent_death_guarded_transport(self):
        manager = self.manager("parent-death")
        published = queue.Queue()
        release = threading.Event()

        def request_thread():
            published.put(manager.create(payload(), CAP, "transient-request"))
            release.wait(timeout=4)

        request = threading.Thread(target=request_thread, name="synthetic-transient-request")
        request.start()
        try:
            sid = published.get(timeout=3)["session_id"]
            snapshot = self.wait(manager, sid, lambda row: row["question"] is not None)
            process = manager._sessions[sid].process
            self.assertIsNone(process.poll())
            release.set()
            request.join(timeout=2)
            self.assertFalse(request.is_alive())
            time.sleep(.15)
            self.assertIsNone(process.poll(), "Parent-death child died with transient request thread")
            manager.answer(sid, CAP, self.answer_payload(snapshot))
            done = self.wait(manager, sid, lambda row: row["status"] in {"completed", "failed"})
            self.assertEqual(done["status"], "completed")
            self.assertEqual(done["last_answer"]["status"], "processed")
            manager.close(sid, CAP)
            self.assertFalse(manager._sessions[sid].reader.is_alive())
            self.assertTrue(all(pipe.closed for pipe in (process.stdin, process.stdout, process.stderr)))
        finally:
            release.set()
            request.join(timeout=2)

    def test_real_short_writes_after_kernel_pipe_backpressure_preserve_answer(self):
        manager, sid, snapshot = self.start("finish")
        process = manager._sessions[sid].process
        fd = process.stdin.fileno()
        real_write = os.write
        written_sizes = []

        def write_short_chunk(target, data):
            if target != fd:
                return real_write(target, data)
            written = real_write(target, data[:7])
            written_sizes.append(written)
            return written

        os.kill(process.pid, signal.SIGSTOP)
        _, stopped = os.waitpid(process.pid, os.WUNTRACED)
        self.assertTrue(os.WIFSTOPPED(stopped))
        try:
            capacity = fcntl.fcntl(fd, fcntl.F_SETPIPE_SZ, 4096)
            self.assertLessEqual(capacity, 8192)
            # Real JSON whitespace fills the kernel pipe without faking delivery
            # or creating an extra response. The child remains stopped until full.
            self.assertEqual(real_write(fd, b" " * capacity), capacity)
            with self.assertRaises(BlockingIOError):
                real_write(fd, b" ")
            resume = threading.Timer(.05, os.kill, args=(process.pid, signal.SIGCONT))
            resume.start()
            try:
                answer = self.answer_payload(snapshot)
                with mock.patch.object(os, "write", side_effect=write_short_chunk):
                    manager.answer(sid, CAP, answer)
            finally:
                resume.join()
        finally:
            if process.poll() is None:
                os.kill(process.pid, signal.SIGCONT)
        done = self.wait(manager, sid, lambda row: row["status"] in {"completed", "failed"})
        self.assertEqual(done["status"], "completed")
        self.assertEqual(done["last_answer"]["status"], "processed")
        self.assertGreater(len(written_sizes), 1)
        self.assertTrue(all(0 < size <= 7 for size in written_sizes))
        self.assertEqual([json.loads(line) for line in self.received(sid)],
                         [{"request_id": answer["request_id"], "tokens": answer["tokens"]}])


if __name__ == "__main__":
    unittest.main()
