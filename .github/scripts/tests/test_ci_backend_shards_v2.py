"""NEW mocked V2 boundary controls, not native descendant/hosted proof."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / 'ci_backend_shards.py'
EXPECTED = dict(pid=101, parent=100, start=12345, pgrp=101, session=101)


class V2BoundaryContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('v2_shard_subject', SCRIPT)
        cls.subject = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.subject)

    def watcher(self, leader, group, deadline=10.0):
        clock, signals = [0.0], []
        def pause(seconds): clock[0] += seconds
        result = self.subject.watch_deadline(deepcopy(EXPECTED), deadline,
            lambda: leader(signals), lambda: clock[0], pause,
            lambda pgrp, kind: signals.append((pgrp, kind)), group_probe=group)
        return result, clock[0], signals

    def test_presence_query_only_esrch_is_absent(self):
        for error, wanted in ((ProcessLookupError(), 'ABSENT'),
                              (PermissionError(), 'UNKNOWN'), (OSError(), 'UNKNOWN')):
            with self.subTest(error=type(error).__name__):
                with patch.object(self.subject.os, 'killpg', side_effect=error) as operation:
                    self.assertEqual(self.subject.group_status(101), wanted)
                    operation.assert_called_once_with(101, 0)
        with patch.object(self.subject.os, 'killpg') as operation:
            self.assertEqual(self.subject.group_status(101), 'PRESENT')
            operation.assert_called_once_with(101, 0)

    def test_stream_detached_survivor_never_qualifies_leader_exit(self):
        # Fake stream detachment is irrelevant: group presence independently vetoes.
        result, elapsed, signals = self.watcher(lambda signals: None, lambda: 'PRESENT')
        self.assertEqual(result['status'], 'UNKNOWN_GROUP_PRESENT')
        self.assertLessEqual(elapsed, 2.2)
        self.assertEqual(signals, [])

    def test_after_int_leader_exit_cannot_hide_survivor_or_authorize_kill(self):
        result, elapsed, signals = self.watcher(
            lambda signals: None if signals else deepcopy(EXPECTED), lambda: 'PRESENT', deadline=0.0)
        self.assertEqual(signals, [(101, 'INT')])
        self.assertEqual(result['status'], 'UNKNOWN_GROUP_PRESENT')
        self.assertLessEqual(elapsed, 2.2)

    def test_absent_group_is_distinct_from_leader_wait_or_reap(self):
        result, elapsed, signals = self.watcher(lambda signals: None, lambda: 'ABSENT')
        self.assertEqual(result['status'], 'GROUP_ABSENT')
        self.assertNotIn('actual_wait', result)
        self.assertEqual(signals, [])

    def test_present_group_can_only_drain_naturally_after_leader_loss(self):
        observations = iter(['PRESENT', 'ABSENT', 'ABSENT'])
        result, elapsed, signals = self.watcher(lambda signals: None, lambda: next(observations))
        self.assertEqual(result['status'], 'GROUP_ABSENT')
        self.assertEqual(signals, [])
        self.assertLessEqual(elapsed, 2.2)

    def test_unknown_or_reused_group_never_gets_a_signal_or_success(self):
        for actual in ('UNKNOWN', 'PRESENT'):
            with self.subTest(group=actual):
                result, elapsed, signals = self.watcher(lambda signals: None, lambda: actual)
                self.assertTrue(result['status'].startswith('UNKNOWN'))
                self.assertEqual(signals, [])
        result, elapsed, signals = self.watcher(
            lambda signals: dict(EXPECTED, start=99999), lambda: 'PRESENT', deadline=0.0)
        self.assertEqual(result['status'], 'UNKNOWN_IDENTITY')
        self.assertEqual(signals, [])

    def test_cli_cannot_certify_absence_before_actual_registration(self):
        saved = []
        with patch.object(self.subject, 'proc_identity', return_value=None), \
             patch.object(self.subject, 'save', side_effect=lambda *args: saved.append(args)), \
             patch.object(self.subject, 'group_status') as groups, \
             patch.object(self.subject.os, 'killpg') as signals:
            with self.assertRaises(self.subject.ContractError):
                self.subject.main(['watch', '101', '100', '100.0', 'fake-output'])
        self.assertEqual(saved[0][1]['status'], 'UNKNOWN_UNREGISTERED')
        groups.assert_not_called()
        signals.assert_not_called()

    def test_real_cli_supplies_group_probe_and_requires_group_absent(self):
        def observed(*args, **kwargs):
            self.assertTrue(callable(kwargs['group_probe']))
            return dict(status='UNKNOWN_GROUP_PRESENT', signals=[])
        with patch.object(self.subject, 'proc_identity', return_value=deepcopy(EXPECTED)), \
             patch.object(self.subject, 'save'), \
             patch.object(self.subject, 'watch_deadline', side_effect=observed):
            with self.assertRaises(self.subject.ContractError):
                self.subject.main(['watch', '101', '100', '100.0', 'fake-output'])

    def test_unmodified_fda_callback_interface_performs_no_os_query(self):
        with patch.object(self.subject.os, 'killpg', side_effect=AssertionError('PHYSICAL_CALL')):
            result = self.subject.watch_deadline(deepcopy(EXPECTED), 10.0, lambda: None,
                lambda: 0.0, lambda seconds: self.fail('unexpected wait'),
                lambda group, kind: self.fail('unexpected signal'))
        self.assertEqual(result['status'], 'LEADER_ABSENT')
        self.assertNotEqual(result['status'], 'GROUP_ABSENT')

    def diagnostic(self):
        # Complete key set from the original empty sanitizer schema, not a pass.
        return dict(schema_version=1, source_commit=None, pytest_exit_code=None,
                    coverage={}, collected_node_sha256=[], discovered_node_sha256=[],
                    deselected_node_sha256=[], deselection_row_count=None,
                    phases=[], subtests=[], failures=[], collection_errors=[], sessions=[],
                    unresolved_failure_count=None, rows_exported=False,
                    skips_and_xfails_are_not_passes=True, metadata_error_codes=[])

    def test_bounded_diagnostic_keeps_partial_failure_nonfinal_without_rewrite(self):
        value = self.diagnostic(); original = json.dumps(value, sort_keys=True)
        with patch.object(self.subject, 'regular_read', return_value=value) as reader:
            self.subject.bound_diagnostic_file(Path('/owned/backend-metadata.json'))
        reader.assert_called_once_with(Path('/owned/backend-metadata.json'), self.subject.WORKER_BYTES)
        self.assertEqual(json.dumps(value, sort_keys=True), original)
        self.assertIsNone(value['pytest_exit_code'])
        self.assertIs(value['rows_exported'], False)

    def test_diagnostic_unknown_keys_bool_schema_and_raw_filename_reject(self):
        for mode in ('unknown', 'bool', 'raw'):
            with self.subTest(mode=mode):
                value = self.diagnostic()
                path = Path('/owned/backend-metadata.json')
                if mode == 'unknown': value['raw_private_payload'] = 'PRIVATE_SENTINEL'
                elif mode == 'bool': value['schema_version'] = True
                else: path = Path('/owned/reporter.log')
                with patch.object(self.subject, 'regular_read', return_value=value):
                    with self.assertRaises(self.subject.ContractError):
                        self.subject.bound_diagnostic_file(path)


if __name__ == '__main__':
    unittest.main()
