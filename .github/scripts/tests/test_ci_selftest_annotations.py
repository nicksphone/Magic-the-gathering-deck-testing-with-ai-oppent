"""Public byte-stream and real Bash pipeline protocols, not backend/game tests."""
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest


SCRIPTS = Path(__file__).resolve().parents[1]
ROOT = SCRIPTS.parents[1]
PARENT = 'test_public_protocol.PublicTests.test_case'
SENTINEL = 'PUBLIC_SYNTHETIC_SUBTEST_VALUE_NOT_AN_ANNOTATION'


def header(parent=PARENT, status='FAIL', suffix=''):
    return f'{status}: {parent.rsplit(".", 1)[1]} ({parent}){suffix}\n'.encode()


def annotation(parent=PARENT, status='FAIL'):
    digest = hashlib.sha256(parent.encode('ascii')).hexdigest()
    return f'::error::{status} {digest}\n'.encode('ascii')


class SelftestAnnotationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            'selftest_annotations_protocol', SCRIPTS / 'ci_selftest_annotations.py')
        cls.helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.helper)

    def forward(self, data):
        output, notices = io.BytesIO(), io.BytesIO()
        status = self.helper.forward(io.BytesIO(data), output, notices)
        self.assertEqual(output.getvalue(), data)
        for row in notices.getvalue().splitlines():
            self.assertRegex(row, rb'^::error::(?:FAIL|ERROR) [0-9a-f]{64}$')
        return status, notices.getvalue()

    def test_complete_failure_headers_only_preserve_every_input_byte(self):
        data = (b'test_case (test_public_protocol.PublicTests.test_case) ... FAIL\n'
                b'ordinary stdout\x00\xff\n' + header() +
                b'Traceback (most recent call last):\n' + SENTINEL.encode() + b'\n' +
                header(status='ERROR') + header().replace(b'\n', b'\r\n') +
                b'ERROR: test_missing (unittest.loader._FailedTest.test_missing)\n' +
                b'FAILED (failures=1, errors=1)\n')
        status, notices = self.forward(data)
        self.assertEqual(status, 0)
        self.assertEqual(notices, annotation() + annotation(status='ERROR') +
                         annotation('unittest.loader._FailedTest.test_missing', 'ERROR'))
        self.assertNotIn(SENTINEL.encode(), notices)
        self.assertNotIn(PARENT.encode(), notices)

    def test_subtest_values_messages_paths_and_workflow_commands_are_not_exported(self):
        suffixes = [f' (value={SENTINEL!r})', f' [{SENTINEL}]',
                    f' [{SENTINEL}] (path="/private/{SENTINEL}")',
                    ' (value="::error::untrusted %0A /private/path")']
        data = b''.join(header(suffix=suffix) for suffix in suffixes)
        status, notices = self.forward(data)
        self.assertEqual((status, notices), (0, annotation()))

    def test_malformed_unanchored_and_non_parent_rows_never_annotate(self):
        rows = [header().replace(b'test_case (', b'test_other ('),
                b'prefix ' + header(), header().replace(b'FAIL:', b'SKIP:'),
                header().replace(b'test_public_protocol.', b'/private/test_public_protocol.'),
                header().replace(b'PublicTests.', b'PublicTests-'),
                header().replace(b'test_public_protocol', b'test_\xff'),
                header().rstrip(b'\n') + b' trailing message\n',
                b'ERROR: setUpClass (test_public_protocol.PublicTests)\n',
                b'FAIL: test_missing (unittest.loader._FailedTest.test_missing)\n',
                b'ERROR: test_other (unittest.loader._FailedTest.test_missing)\n',
                b'ERROR: test_missing (unittest.loader._FailedTests.test_missing)\n',
                b'ERROR: test_missing (unittest.loader._FailedTest.test_missing.extra)\n',
                b'ERROR: test_missing (private/unittest.loader._FailedTest.test_missing)\n',
                b'ERROR: test_missing (unittest.loader._FailedTest.test_missing) (value=secret)\n',
                b'ERROR: test_missing (unittest.loader._FailedTest.test_missing) [secret]\n',
                b'ERROR: test_missing (unittest.loader._FailedTest.test_missing) ::error::secret\n',
                b'ERROR: test_missing (unittest.loader._FailedTest.test_missing%0A::error::secret)\n',
                b'ERROR: test_missing (unittest.loader._FailedTest.test_missing)\x00\n',
                b'ERROR: test_missing (unittest.loader._FailedTest.test_missing)',
                header(suffix=' (unclosed'), header(suffix=' (bad=\x00)'),
                header(suffix=' [bad=\x1b]'), header().rstrip(b'\n')]
        for row in rows:
            with self.subTest(vector=rows.index(row)):
                self.assertEqual(self.forward(row), (0, b''))

    def test_fragmented_binary_readline_has_bounded_partial_line_state(self):
        class Fragmented(io.BytesIO):
            def readline(reader, size=-1):
                self.assertGreater(size, 0)
                self.assertLessEqual(size, self.helper.CHUNK_BYTES)
                return super(Fragmented, reader).readline(min(size, 7))

        data = b'prefix\n' + header(suffix=' (value=7)') + header(status='ERROR')
        output, notices = io.BytesIO(), io.BytesIO()
        self.assertEqual(self.helper.forward(Fragmented(data), output, notices), 0)
        self.assertEqual(output.getvalue(), data)
        self.assertEqual(notices.getvalue(), annotation() + annotation(status='ERROR'))

    def test_overlong_rows_cannot_reparse_a_tail_or_eof_as_a_header(self):
        row = header().rstrip(b'\n') + b' ' * self.helper.LINE_BYTES
        data = row + header() + header(status='ERROR') + header().rstrip(b'\n')
        self.assertEqual(self.forward(data), (0, annotation(status='ERROR')))
        prefix = header().rstrip(b'\n') + b' ('
        exact = prefix + b'x' * (self.helper.LINE_BYTES - len(prefix) - 2) + b')\n'
        self.assertEqual(self.forward(exact), (0, annotation()))
        self.assertEqual(self.forward(exact[:-1] + b'x\n'), (0, b''))

    def test_duplicate_bound_is_finite_and_overflow_fails_closed_without_truncating_raw(self):
        parents = [f'test_public_protocol.PublicTests.test_case_{i}' for i in range(513)]
        data = header(parents[0]) * 600 + b''.join(header(parent) for parent in parents)
        status, notices = self.forward(data)
        self.assertEqual(status, 2)
        self.assertEqual(len(notices.splitlines()), 512)
        self.assertEqual(notices, b''.join(annotation(parent) for parent in parents[:512]))

    def test_stream_io_errors_fail_closed_without_exception_messages(self):
        class Broken(io.BytesIO):
            def write(self, data):
                raise OSError(SENTINEL)

        class Short(io.BytesIO):
            def write(self, data):
                return 0

        for output, notices in ((Broken(), io.BytesIO()), (io.BytesIO(), Broken()),
                                (Short(), io.BytesIO()), (io.BytesIO(), Short())):
            with self.subTest(output_broken=isinstance(output, Broken)):
                self.assertEqual(self.helper.forward(io.BytesIO(header()), output, notices), 2)
                self.assertNotIn(SENTINEL.encode(), notices.getvalue())

    def workflow_pipeline(self):
        workflow = (ROOT / '.github/workflows/ci.yml').read_text()
        step = workflow.split('      - name: Backend metadata reporter tests\n', 1)[1]
        step = step.split('      - name:', 1)[0]
        script = textwrap.dedent(step.split('        run: |\n', 1)[1])
        match = re.fullmatch(
            r'remaining=\$\(python \.github/scripts/ci_backend_shards\.py remaining\)\n'
            r'timeout --signal=TERM --kill-after=15s "\$\{remaining\}s" '
            r"bash --noprofile --norc -c '\n(?P<body>.*)\n'\n", script, re.DOTALL)
        self.assertIsNotNone(match, 'The existing remaining timeout must wrap the entire pipeline')
        return match['body']

    def test_workflow_keeps_original_unittest_argv_and_immediate_pipe_status(self):
        lines = [line.strip() for line in self.workflow_pipeline().splitlines()]
        self.assertEqual(lines, [
            'set +e',
            'python -m unittest discover -s .github/scripts/tests -v 2>&1 |',
            'python -u .github/scripts/ci_selftest_annotations.py',
            'statuses=("${PIPESTATUS[@]}")',
            'if ((statuses[0] != 0)); then exit "${statuses[0]}"; fi',
            'exit "${statuses[1]}"'])

    def test_real_fixed_bash_pipeline_preserves_unit_failure_and_genuine_helper_overflow(self):
        pipeline = self.workflow_pipeline()
        producer = '''\
            python() {
              case "$*" in
                '-m unittest discover -s .github/scripts/tests -v')
                  printf '%s' "$PUBLIC_UNIT_TEXT" >&2
                  return "$PUBLIC_UNIT_EXIT" ;;
                '-u .github/scripts/ci_selftest_annotations.py')
                  command "$PUBLIC_PYTHON" -I -B "$@" ;;
                *) return 97 ;;
              esac
            }
            '''
        overflow = b''.join(header(f'test_public_protocol.PublicTests.test_case_{i}')
                            for i in range(513))
        with tempfile.TemporaryDirectory(prefix='ci-annotation-protocol-') as directory:
            for unit_status, data in ((0, header()), (1, header()), (23, header()),
                                      (124, header()), (0, overflow), (23, overflow)):
                with self.subTest(unit_status=unit_status, overflow=data == overflow):
                    environment = {'PATH': os.defpath, 'HOME': directory, 'LANG': 'C.UTF-8',
                                   'PUBLIC_UNIT_TEXT': data.decode('ascii'),
                                   'PUBLIC_UNIT_EXIT': str(unit_status),
                                   'PUBLIC_PYTHON': sys.executable}
                    result = subprocess.run(
                        ['bash', '--noprofile', '--norc', '-c', textwrap.dedent(producer) + pipeline],
                        cwd=ROOT, env=environment, capture_output=True, timeout=10)
                    expected = unit_status or (2 if data == overflow else 0)
                    self.assertEqual(result.returncode, expected)
                    self.assertEqual(result.stdout, data)
                    self.assertEqual(len(result.stderr.splitlines()), 512 if data == overflow else 1)
                    for row in result.stderr.splitlines():
                        self.assertRegex(row, rb'^::error::FAIL [0-9a-f]{64}$')


if __name__ == '__main__':
    unittest.main()
