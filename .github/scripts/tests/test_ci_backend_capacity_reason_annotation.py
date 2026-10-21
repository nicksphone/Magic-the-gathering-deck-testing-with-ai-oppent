"""Diagnostic-only protocol tests; actual main, mocked preflight, no SDK cleanup."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / 'ci_backend_capacity.py'
PREFIX = '::error title=Backend capacity rejection::'
# Independently declared public reasons from the cd1 producer, not its future helper.
REASONS = (
    'runner-path', 'sdk-path', 'protected-overlap', 'hosted-backend-context',
    'runner-image', 'workspace-binding', 'sdk-identity', 'sdk-cleanup-timeout',
    'sdk-cleanup', 'sdk-remains', 'byte-floor', 'arguments',
    'filesystem-observation',
)


class BackendCapacityReasonAnnotationTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('capacity_reason_under_test', SCRIPT)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def invoke(self, error=None, argv=(), preflight=None):
        events = []

        class Stream(io.StringIO):
            def __init__(self, channel):
                super().__init__()
                self.channel = channel

            def write(self, text):
                events.append((self.channel, text))
                return super().write(text)

        stdout, stderr = Stream('stdout'), Stream('stderr')
        with patch.object(self.module, 'preflight', side_effect=preflight or error) as admit, \
                patch.object(self.module.subprocess, 'run',
                    side_effect=AssertionError('Real SDK cleanup is forbidden')) as command, \
                patch.object(self.module.sys, 'argv', ['capacity-protocol', *argv]), \
                patch.dict(self.module.os.environ, {'CAPACITY_PROTOCOL_ONLY': '1'}, clear=True), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = self.module.main()
            self.assertEqual(admit.call_count, 0 if argv else 1)
            if not argv:
                admit.assert_called_once_with(self.module.os.environ)
            command.assert_not_called()
        return result, stdout.getvalue(), stderr.getvalue(), events

    def assert_rejection(self, outcome, reason, prior_stdout=''):
        result, stdout, stderr, events = outcome
        self.assertIs(type(result), int)
        self.assertEqual(result, 2)
        # Preserve the entire historical stdout, including its final legacy line.
        self.assertEqual(stdout, prior_stdout + 'CI_BACKEND_CAPACITY_REJECTED reason=' + reason + '\n')
        self.assertTrue(stderr.isascii())
        self.assertLessEqual(len(stderr.encode('utf-8')), 256)
        self.assertEqual(stderr.count('\n'), 1)
        self.assertTrue(stderr.startswith(PREFIX))
        self.assertTrue(stderr.endswith('\n'))
        pairs = json.loads(stderr[len(PREFIX):-1], object_pairs_hook=list)
        self.assertIs(type(pairs), list)
        self.assertEqual(len(pairs), 3)
        self.assertEqual({key for key, value in pairs}, {'schema', 'reason', 'exit_code'})
        payload = dict(pairs)
        self.assertIs(type(payload['schema']), int)
        self.assertIs(type(payload['exit_code']), int)
        self.assertIs(type(payload['reason']), str)
        self.assertEqual(payload, {'schema': 1, 'reason': reason, 'exit_code': 2})
        annotation = next(index for index, (channel, text) in enumerate(events)
                          if channel == 'stderr' and PREFIX in text)
        legacy = next(index for index, (channel, text) in enumerate(events)
                      if channel == 'stdout' and text.startswith('CI_BACKEND_CAPACITY_REJECTED'))
        self.assertLess(annotation, legacy)

    def test_each_existing_finite_reason_is_reported_once_before_legacy_stdout(self):
        for reason in REASONS:
            with self.subTest(reason=reason):
                self.assert_rejection(self.invoke(self.module.CapacityError(reason)), reason)

    def test_unknown_capacity_error_text_is_hardened_to_fixed_unknown_on_both_streams(self):
        for message in (
            '', None, 123, 'sdk-cleanup-timeout ', 'SDK-CLEANUP',
            'PRIVATE_SENTINEL /private/input?token=secret',
            'byte-floor\n::error title=Forged::PRIVATE_SENTINEL',
            'sdk-cleanup\r\nPRIVATE_SENTINEL', '\u2603', 'x' * 4096,
        ):
            with self.subTest(case_type=type(message).__name__):
                outcome = self.invoke(self.module.CapacityError(message))
                self.assert_rejection(outcome, 'unknown')
                self.assertNotIn('PRIVATE_SENTINEL', outcome[1] + outcome[2])

    def test_oserror_details_never_leave_main_and_use_filesystem_observation(self):
        for error in (
            OSError(28, 'PRIVATE_SENTINEL no space', '/private/input'),
            PermissionError(13, 'PRIVATE_SENTINEL denied', '/private/input'),
            FileNotFoundError(2, 'PRIVATE_SENTINEL absent', '/private/input'),
        ):
            with self.subTest(error_type=type(error).__name__):
                outcome = self.invoke(error)
                self.assert_rejection(outcome, 'filesystem-observation')
                self.assertNotIn('PRIVATE_SENTINEL', outcome[1] + outcome[2])
                self.assertNotIn('/private/input', outcome[1] + outcome[2])

    def test_argument_rejection_preserves_exact_legacy_stdout_without_preflight(self):
        outcome = self.invoke(argv=('/unapproved-root',))
        self.assert_rejection(outcome, 'arguments')
        self.assertNotIn('/unapproved-root', outcome[1] + outcome[2])

    def test_rejection_preserves_preflight_measurement_output_already_emitted(self):
        prior = 'CI_BACKEND_CAPACITY {"phase":"before","floor_bytes":21474836480}\n'

        def reject_after_measurement(env):
            print(prior, end='', flush=True)
            raise self.module.CapacityError('byte-floor')

        self.assert_rejection(self.invoke(preflight=reject_after_measurement),
                              'byte-floor', prior_stdout=prior)

    def test_success_preserves_preflight_output_without_any_annotation(self):
        def ready(env):
            self.assertEqual(dict(env), {'CAPACITY_PROTOCOL_ONLY': '1'})
            print('CI_BACKEND_CAPACITY_READY cleanup=fixed-unused-sdks', flush=True)

        result, stdout, stderr, events = self.invoke(preflight=ready)
        self.assertEqual(result, 0)
        self.assertEqual(stdout, 'CI_BACKEND_CAPACITY_READY cleanup=fixed-unused-sdks\n')
        self.assertEqual(stderr, '')
        self.assertTrue(all(channel == 'stdout' for channel, text in events))

    def test_unrelated_programming_error_is_not_relabelled_as_capacity_rejection(self):
        with self.assertRaisesRegex(RuntimeError, '^protocol-programming-error$'):
            self.invoke(RuntimeError('protocol-programming-error'))


if __name__ == '__main__':
    unittest.main()
