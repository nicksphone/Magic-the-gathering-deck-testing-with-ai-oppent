"""A genuine owned failing child must retain its assertion and emit only metadata."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

import test_ci_backend_shards_e2e as e2e


class ToyFailureProjectionTests(unittest.TestCase):
    def test_failing_actual_owned_command_keeps_failure_and_redacts_streams(self):
        with tempfile.TemporaryDirectory(prefix='toy-failure-projection-') as directory:
            root = Path(directory)
            subject = e2e.ShardCliE2ETests('runTest')
            subject.root = root
            subject.repo = root / 'source'
            subject.repo.mkdir()
            subject.work_until = time.monotonic() + 30
            subject.records, subject.handles = [], []
            subject.env = {'PATH': os.defpath, 'HOME': str(root), 'LANG': 'C.UTF-8'}
            marker = e2e.SENTINEL
            code = ('import sys\n'
                    f'print({marker!r})\n'
                    f'print({marker!r}, file=sys.stderr)\n'
                    'raise SystemExit(7)\n')
            stream = io.StringIO()
            try:
                with contextlib.redirect_stderr(stream):
                    with self.assertRaises(AssertionError):
                        subject._command('reference', [sys.executable, '-I', '-B', '-c', code])
                self.assertEqual(len(subject.handles), 1)
                self.assertEqual(subject.handles[0].poll(), 7)
                lines = stream.getvalue().splitlines()
                self.assertEqual(len(lines), 1, 'Failure-only technical metadata is missing')
                prefix = 'CI_TOY_COMMAND_FAILURE '
                self.assertTrue(lines[0].startswith(prefix))
                self.assertNotIn(marker, lines[0])
                self.assertNotIn(str(root), lines[0])
                record = json.loads(lines[0][len(prefix):])
                self.assertEqual(set(record), {'schema', 'role', 'actual_exit',
                                               'expected_exit', 'stdout', 'stderr',
                                               'runner_closeout'})
                self.assertEqual(record['schema'], 1)
                self.assertEqual(record['role'], 'reference')
                self.assertEqual(record['actual_exit'], 7)
                self.assertEqual(record['expected_exit'], 0)
                self.assertIsNone(record['runner_closeout'])
                data = (marker + '\n').encode()
                for name in ('stdout', 'stderr'):
                    self.assertEqual(record[name], {'status': 'available', 'bytes': len(data),
                                                   'sha256': hashlib.sha256(data).hexdigest()})
            finally:
                for child in subject.handles:
                    if child.poll() is None:
                        child.terminate()
                        try:
                            child.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            child.kill()
                            child.wait(timeout=2)


if __name__ == '__main__':
    unittest.main()
