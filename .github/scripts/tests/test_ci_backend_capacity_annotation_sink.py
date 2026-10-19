"""Optional-stderr regression protocols; no real pipes or SDK/child operations."""
import contextlib
import importlib.util
import io
from pathlib import Path
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / 'ci_backend_capacity.py'


class BrokenAnnotationSink:
    def __init__(self, phase):
        self.phase = phase
        self.failures = 0

    def write(self, text):
        if self.phase == 'write':
            self.failures += 1
            raise BrokenPipeError(32, 'synthetic annotation write failure')
        return len(text)

    def flush(self):
        self.failures += 1
        raise BrokenPipeError(32, 'synthetic annotation flush failure')


class BackendCapacityAnnotationSinkTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('capacity_sink_under_test', SCRIPT)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def assert_preserved_rejection(self, sink_factory):
        for branch in ('capacity', 'filesystem'):
            with self.subTest(branch=branch):
                error = (self.module.CapacityError('byte-floor') if branch == 'capacity'
                         else OSError(28, 'synthetic filesystem failure'))
                reason = 'byte-floor' if branch == 'capacity' else 'filesystem-observation'
                stdout, stderr = io.StringIO(), sink_factory()
                with patch.object(self.module, 'preflight', side_effect=error) as admit, \
                        patch.object(self.module.subprocess, 'run',
                            side_effect=AssertionError('Real SDK cleanup is forbidden')) as command, \
                        patch.object(self.module.sys, 'argv', ['capacity-sink-protocol']), \
                        patch.dict(self.module.os.environ, {'CAPACITY_SINK_PROTOCOL_ONLY': '1'}, clear=True), \
                        contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    try:
                        result = self.module.main()
                    except (BrokenPipeError, ValueError):
                        raise AssertionError(
                            'Optional stderr failure replaced legacy stdout and rejection exit2') from None
                    self.assertIs(type(result), int)
                    self.assertEqual(result, 2)
                    admit.assert_called_once_with(self.module.os.environ)
                    command.assert_not_called()
                self.assertEqual(stdout.getvalue(),
                                 'CI_BACKEND_CAPACITY_REJECTED reason=' + reason + '\n')
                if isinstance(stderr, BrokenAnnotationSink):
                    # No stderr retry and no recursive diagnostic on a broken sink.
                    self.assertEqual(stderr.failures, 1)

    def test_broken_stderr_write_preserves_exact_rejection_stdout_and_exit2(self):
        self.assert_preserved_rejection(lambda: BrokenAnnotationSink('write'))

    def test_broken_stderr_flush_preserves_exact_rejection_stdout_and_exit2(self):
        self.assert_preserved_rejection(lambda: BrokenAnnotationSink('flush'))

    def test_genuinely_closed_stderr_preserves_exact_rejection_stdout_and_exit2(self):
        def closed_stream():
            stream = io.StringIO()
            stream.close()
            return stream

        self.assert_preserved_rejection(closed_stream)


if __name__ == '__main__':
    unittest.main()
