# SPDX-License-Identifier: GPL-3.0-or-later
"""SYNTHETIC transport tests, not Java policy or native-game resume evidence."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "checkpoint_store.py"
MODULE_SPEC = importlib.util.spec_from_file_location("checkpoint_causal_store", MODULE_PATH)
STORE = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(STORE)
ARGV = ["/SYNTHETIC/java", "-cp", "/SYNTHETIC/classes",
        "forge.evaluation.CausalCompletionVerifier", "--checkpoint-prefix"]


def synthetic_checkpoint():
    """Closed four-invocation domain with deliberately non-ID-sorted arrivals."""
    starts = [{"start_id": i, "parent_start": -1, "kind": "SYNTHETIC",
               "ticket": {"selected": [i]}, "parent_edge": {"synthetic": True}}
              for i in range(4)]
    completions = [{"start_id": i, "kind": "SYNTHETIC", "ticket": {"selected": [i]},
                    "result": {"synthetic": i}, "producer": {
                        "synthetic": True, "epoch": 1, "nested": {"flag": True}}}
                   for i in (2, 0, 3, 1)]
    return {
        "schema": 1,
        "spec": {"human_seat": 0, "seed": 123, "open_decklists": True,
                 "decks": [{"file": "a.dck"}, {"file": "b.dck"}]},
        "decks": {"a.dck": "SYNTHETIC A\r\n", "b.dck": "SYNTHETIC B\n"},
        "starts": 4, "completions": 4,
        "pending_offer": {"kind": "SYNTHETIC", "actor": 17, "min": 1, "max": 1,
                          "choices": [101, 102], "turn": 2, "phase": "SYNTHETIC",
                          "info": {"selection": {"chosen": [101], "revision": 5}}},
        "actor_view": {"actor_id": 17, "selection": {"chosen": [101]},
                       "metadata": {"flag": True}},
        "native_state": {"players": [{"id": 17, "life": 20}], "stack": [],
                         "turn": 2, "phase": "SYNTHETIC", "rng_delta": 41},
        "journals": {"starts": starts, "completions": completions,
                     "native": [{"synthetic": True, "rng_delta": 40}, {"ordinal": 2}],
                     "paid-pending": [{"synthetic": True}, {"ordinal": 2}], "final": []},
    }


def encoded(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


class SyntheticCausalCheckpointTransportTests(unittest.TestCase):
    def setUp(self):
        self.saved = synthetic_checkpoint()
        self.current = copy.deepcopy(self.saved)
        rows = self.current["journals"]["completions"]
        self.current["journals"]["completions"] = [rows[2], rows[0], rows[3], rows[1]]
        self.payload = encoded({"reference": self.saved["journals"],
                                "actual": self.current["journals"]})
        self.proof = {
            "contract": "CAUSAL_CHECKPOINT_PREFIX", "reference_comparison": True,
            "strict_global_completion_order": False,
            "displaced_pairs": [{"arrived_before": 3, "reference_predecessor": 2},
                                {"arrived_before": 3, "reference_predecessor": 0},
                                {"arrived_before": 1, "reference_predecessor": 0}],
            "completed_ids_in_arrival_order": [3, 2, 1, 0],
            "final_rows": 0, "game_complete": False,
            "input_sha256": hashlib.sha256(self.payload).hexdigest(),
        }
        self.runner = mock.patch("subprocess.run").start()
        self.addCleanup(mock.patch.stopall)
        self.runner.return_value = subprocess.CompletedProcess(
            ARGV, 0, stdout=encoded(self.proof), stderr=b"SYNTHETIC PRIVATE STDERR")

    def verify(self, argv=ARGV):
        return STORE.verify_frontier(self.saved, self.current, causal_verifier=argv)

    def reject_before_launch(self):
        with self.assertRaises(STORE.CheckpointError):
            self.verify()
        self.runner.assert_not_called()

    def reject_proof(self, proof):
        self.runner.return_value.stdout = encoded(proof)
        with self.assertRaises(STORE.CheckpointError):
            self.verify()
        self.runner.assert_called_once()

    def test_default_exact_returns_none_without_launch(self):
        self.assertIsNone(STORE.verify_frontier(self.saved, copy.deepcopy(self.saved)))
        self.runner.assert_not_called()

    def test_default_arrival_difference_remains_strict(self):
        with self.assertRaises(STORE.CheckpointError):
            STORE.verify_frontier(self.saved, self.current)
        self.runner.assert_not_called()

    def test_explicit_none_remains_strict(self):
        with self.assertRaises(STORE.CheckpointError):
            self.verify(None)
        self.runner.assert_not_called()

    def test_exact_with_verifier_returns_none_without_launch(self):
        self.current = copy.deepcopy(self.saved)
        self.assertIsNone(self.verify())
        self.runner.assert_not_called()

    def test_exact_open_callback_retains_strict_path_without_launch(self):
        self.saved["completions"] = 3
        self.saved["journals"]["completions"].pop()
        self.current = copy.deepcopy(self.saved)
        self.assertIsNone(self.verify())
        self.runner.assert_not_called()

    def test_synthetic_transport_returns_bound_proof_without_mutating_inputs(self):
        before = copy.deepcopy((self.saved, self.current, ARGV))
        self.assertEqual(self.verify(), self.proof)
        self.assertEqual((self.saved, self.current, ARGV), before)
        self.runner.assert_called_once_with(
            ARGV, input=self.payload, capture_output=True, timeout=10,
            env={"LANG": "C.UTF-8"}, check=False)

    def test_operator_tuple_argv_is_accepted(self):
        self.assertEqual(self.verify(tuple(ARGV)), self.proof)

    def test_bad_native_state_rejected_before_launch(self):
        self.current["native_state"]["players"][0]["life"] -= 1
        self.reject_before_launch()

    def test_bad_rng_rejected_before_launch(self):
        self.current["native_state"]["rng_delta"] += 1
        self.reject_before_launch()

    def test_bad_actor_view_rejected_before_launch(self):
        self.current["actor_view"]["selection"]["chosen"] = [102]
        self.reject_before_launch()

    def test_bad_pending_selection_rejected_before_launch(self):
        self.current["pending_offer"]["info"]["selection"]["chosen"] = [102]
        self.reject_before_launch()

    def test_bad_pending_actor_rejected_before_launch(self):
        self.current["pending_offer"]["actor"] = 18
        self.reject_before_launch()

    def test_bad_producer_whole_row_rejected_before_launch(self):
        self.current["journals"]["completions"][0]["producer"]["extra"] = "SYNTHETIC"
        self.reject_before_launch()

    def test_removed_producer_field_rejected_before_launch(self):
        del self.current["journals"]["completions"][0]["producer"]["epoch"]
        self.reject_before_launch()

    def test_nested_producer_bool_int_substitution_rejected_before_launch(self):
        self.current["journals"]["completions"][0]["producer"]["nested"]["flag"] = 1
        self.reject_before_launch()

    def test_changed_completion_result_rejected_before_launch(self):
        self.current["journals"]["completions"][0]["result"]["synthetic"] = 99
        self.reject_before_launch()

    def test_changed_completion_ticket_rejected_before_launch(self):
        self.current["journals"]["completions"][0]["ticket"]["selected"] = [99]
        self.reject_before_launch()

    def test_changed_matching_start_and_completion_ticket_rejected_before_launch(self):
        self.current["journals"]["starts"][3]["ticket"]["selected"] = [99]
        self.current["journals"]["completions"][0]["ticket"]["selected"] = [99]
        self.reject_before_launch()

    def test_changed_parent_edge_rejected_before_launch(self):
        self.current["journals"]["starts"][0]["parent_edge"]["synthetic"] = 1
        self.reject_before_launch()

    def test_start_vector_order_rejected_before_launch(self):
        self.current["journals"]["starts"].reverse()
        self.reject_before_launch()

    def test_native_journal_order_rejected_before_launch(self):
        self.current["journals"]["native"].reverse()
        self.reject_before_launch()

    def test_paid_pending_journal_order_rejected_before_launch(self):
        self.current["journals"]["paid-pending"].reverse()
        self.reject_before_launch()

    def test_changed_final_stream_rejected_before_launch(self):
        self.current["journals"]["final"].append({"synthetic": True})
        self.reject_before_launch()

    def test_changed_spec_rejected_before_launch(self):
        self.current["spec"]["seed"] += 1
        self.reject_before_launch()

    def test_changed_deck_bytes_rejected_before_launch(self):
        self.current["decks"]["a.dck"] += "\n"
        self.reject_before_launch()

    def test_typed_top_level_nested_value_rejected_before_launch(self):
        self.current["spec"]["open_decklists"] = 1
        self.reject_before_launch()

    def test_invalid_count_rejected_before_launch(self):
        self.current["completions"] = True
        self.reject_before_launch()

    def test_changed_valid_counts_rejected_before_launch(self):
        self.current["completions"] = 3
        self.current["journals"]["completions"].pop()
        self.reject_before_launch()

    def test_both_open_domains_rejected_before_launch(self):
        for checkpoint in (self.saved, self.current):
            checkpoint["completions"] = 3
            checkpoint["journals"]["completions"] = [
                row for row in checkpoint["journals"]["completions"] if row["start_id"] != 1]
        self.reject_before_launch()

    def test_duplicate_completion_ids_rejected_before_launch(self):
        self.current["journals"]["completions"][1] = copy.deepcopy(
            self.current["journals"]["completions"][0])
        self.reject_before_launch()

    def test_unknown_completion_id_rejected_before_launch(self):
        self.current["journals"]["completions"][0]["start_id"] = 4
        self.reject_before_launch()

    def test_invalid_saved_snapshot_rejected_before_launch(self):
        self.saved["schema"] = True
        self.reject_before_launch()

    def test_invalid_current_snapshot_even_if_equal_rejected_before_launch(self):
        self.saved["schema"] = True
        self.current = copy.deepcopy(self.saved)
        self.reject_before_launch()

    def test_saved_operator_command_is_not_configuration(self):
        for checkpoint in (self.saved, self.current):
            checkpoint["spec"]["causal_verifier"] = ARGV
        with self.assertRaises(STORE.CheckpointError):
            STORE.verify_frontier(self.saved, self.current)
        self.runner.assert_not_called()

    def test_malformed_operator_argv_rejected_before_launch(self):
        bad = [[], (), " ".join(ARGV), iter(ARGV), {"argv": ARGV}, True, 3,
               [""], [None, *ARGV[1:]], [ARGV[0], "", *ARGV[1:]],
               [ARGV[0], b"bytes", *ARGV[1:]], [ARGV[0], "nul\x00arg", *ARGV[1:]],
               ["/SYNTHETIC/ja\x00va", *ARGV[1:]]]
        for argv in bad:
            with self.subTest(argv=repr(argv)), self.assertRaises(STORE.CheckpointError):
                self.verify(argv)
        self.runner.assert_not_called()

    def test_relative_executable_rejected_before_launch(self):
        with self.assertRaises(STORE.CheckpointError):
            self.verify(["java", *ARGV[1:]])
        self.runner.assert_not_called()

    def test_wrapper_executable_rejected_before_launch(self):
        for executable in ("/usr/bin/timeout", "/bin/sh"):
            with self.subTest(executable=executable):
                self.runner.reset_mock()
                with self.assertRaises(STORE.CheckpointError):
                    self.verify([executable, *ARGV[1:]])
                self.runner.assert_not_called()

    def test_wrong_cli_suffix_rejected_before_launch(self):
        for argv in ([*ARGV[:-1], "--full-game"], [*ARGV, "--extra"],
                     [ARGV[0], "untrusted.OtherClass", ARGV[-1]], [ARGV[0]]):
            with self.subTest(argv=argv), self.assertRaises(STORE.CheckpointError):
                self.verify(argv)
        self.runner.assert_not_called()

    def test_wrong_input_digest_rejected(self):
        self.proof["input_sha256"] = "0" * 64
        self.reject_proof(self.proof)

    def test_noncanonical_input_digest_rejected(self):
        for value in (self.proof["input_sha256"].upper(), "a" * 63, True, None):
            with self.subTest(value=value):
                self.runner.reset_mock()
                self.reject_proof(dict(self.proof, input_sha256=value))

    def test_wrong_arrival_domain_or_order_rejected(self):
        for value in ([0, 1, 2, 3], [3, 2, 1], [3, 2, 1, 1], [3, 2, 1, 9],
                      [3, 2, True, 0], [3, 2, 1, 0.0], "3,2,1,0"):
            with self.subTest(value=value):
                self.runner.reset_mock()
                self.reject_proof(dict(self.proof, completed_ids_in_arrival_order=value))

    def test_wrong_contract_rejected(self):
        self.proof["contract"] = "CAUSAL_FULL_GAME"
        self.reject_proof(self.proof)

    def test_wrong_reference_comparison_flag_rejected(self):
        for value in (False, 1, "true", None):
            with self.subTest(value=value):
                self.runner.reset_mock()
                self.reject_proof(dict(self.proof, reference_comparison=value))

    def test_wrong_strict_order_flag_rejected(self):
        for value in (True, 0, "false", None):
            with self.subTest(value=value):
                self.runner.reset_mock()
                self.reject_proof(dict(self.proof, strict_global_completion_order=value))

    def test_nonzero_or_noninteger_final_rows_rejected(self):
        for value in (1, -1, False, 0.0, "0", None):
            with self.subTest(value=value):
                self.runner.reset_mock()
                self.reject_proof(dict(self.proof, final_rows=value))

    def test_game_complete_flag_rejected_unless_boolean_false(self):
        for value in (True, 0, "false", None):
            with self.subTest(value=value):
                self.runner.reset_mock()
                self.reject_proof(dict(self.proof, game_complete=value))

    def test_wrong_or_reordered_displaced_pairs_rejected(self):
        pairs = self.proof["displaced_pairs"]
        for value in ([], pairs[:-1], list(reversed(pairs)), [*pairs, pairs[0]],
                      [{"arrived_before": 2, "reference_predecessor": 3}, *pairs[1:]],
                      [{"arrived_before": 3, "reference_predecessor": False}, *pairs[1:]],
                      [dict(pairs[0], extra=True), *pairs[1:]], "SYNTHETIC"):
            with self.subTest(value=value):
                self.runner.reset_mock()
                self.reject_proof(dict(self.proof, displaced_pairs=value))

    def test_missing_or_extra_proof_key_rejected(self):
        for key in self.proof:
            value = dict(self.proof)
            del value[key]
            with self.subTest(missing=key):
                self.runner.reset_mock()
                self.reject_proof(value)
        self.runner.reset_mock()
        self.reject_proof(dict(self.proof, extra=True))

    def test_nonobject_proof_rejected(self):
        for value in ([], None, True, 0, "SYNTHETIC"):
            with self.subTest(value=value):
                self.runner.reset_mock()
                self.reject_proof(value)

    def test_duplicate_proof_keys_rejected(self):
        self.runner.return_value.stdout = encoded(self.proof)[:-1] + b',"final_rows":0}'
        with self.assertRaises(STORE.CheckpointError):
            self.verify()

    def test_duplicate_nested_proof_keys_rejected(self):
        raw = encoded(self.proof)
        self.runner.return_value.stdout = raw.replace(
            b'"arrived_before":3', b'"arrived_before":3,"arrived_before":3', 1)
        with self.assertRaises(STORE.CheckpointError):
            self.verify()

    def test_malformed_or_extra_json_rejected(self):
        for raw in (b"", b"SYNTHETIC PRIVATE PAYLOAD", b"\xff", b"{", b"NaN",
                    encoded(self.proof) + b"\n{}", b"[" * 2000 + b"]" * 2000):
            with self.subTest(raw=raw[:32]):
                self.runner.return_value.stdout = raw
                with self.assertRaises(STORE.CheckpointError):
                    self.verify()

    def test_nonbytes_stdout_rejected(self):
        for value in (encoded(self.proof).decode("utf-8"), None, bytearray(encoded(self.proof))):
            with self.subTest(type=type(value)):
                self.runner.return_value.stdout = value
                with self.assertRaises(STORE.CheckpointError):
                    self.verify()

    def test_oversized_stdout_rejected(self):
        self.runner.return_value.stdout = encoded(self.proof).ljust(262145, b" ")
        with self.assertRaises(STORE.CheckpointError):
            self.verify()

    def test_stdout_limit_is_inclusive(self):
        self.runner.return_value.stdout = encoded(self.proof).ljust(262144, b" ")
        self.assertEqual(self.verify(), self.proof)

    def test_nonzero_exit_rejected_without_private_stderr(self):
        self.runner.return_value.returncode = 7
        with self.assertRaises(STORE.CheckpointError) as caught:
            self.verify()
        self.assertNotIn("SYNTHETIC PRIVATE", str(caught.exception))

    def test_timeout_converted_without_private_payload(self):
        self.runner.side_effect = subprocess.TimeoutExpired(
            ARGV, 10, output=self.payload, stderr=b"SYNTHETIC PRIVATE STDERR")
        with self.assertRaises(STORE.CheckpointError) as caught:
            self.verify()
        self.assertNotIn("SYNTHETIC", str(caught.exception))
        self.assertTrue(caught.exception.__suppress_context__)

    def test_oserror_converted_without_private_payload(self):
        self.runner.side_effect = OSError("SYNTHETIC PRIVATE EXECUTABLE DETAILS")
        with self.assertRaises(STORE.CheckpointError) as caught:
            self.verify()
        self.assertNotIn("SYNTHETIC", str(caught.exception))
        self.assertTrue(caught.exception.__suppress_context__)


if __name__ == "__main__":
    unittest.main()
