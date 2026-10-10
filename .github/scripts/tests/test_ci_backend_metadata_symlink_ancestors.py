"""Synthetic ancestor-symlink controls; the original 48 tests stay untouched."""
import sys


def deny_external_io(event, args):
    if event.startswith(('sqlite3.', 'socket.')):
        raise RuntimeError('SQL_SOCKET_DENIED')


sys.addaudithook(deny_external_io)

import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

import test_ci_backend_metadata as fixtures


class AncestorSymlinkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.MetadataTests.setUpClass()

    @classmethod
    def tearDownClass(cls):
        fixtures.MetadataTests.tearDownClass()

    def setUp(self):
        self.fixture = fixtures.MetadataTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.ledger()
        self.reporter = self.fixture.reporter()
        self.root = self.fixture.root
        self.owned = self.root / 'owned'
        self.owned.mkdir()
        self.actual = self.root / 'actual'
        (self.actual / 'subdir').mkdir(parents=True)
        self.link = self.owned / 'link'
        self.link.symlink_to(self.actual, target_is_directory=True)
        self.fixture.evidence.rename(self.actual / 'subdir/evidence')
        self.evidence = self.actual / 'subdir/evidence'

    def relative(self, path):
        previous = Path.cwd()
        os.chdir(self.owned)
        self.addCleanup(os.chdir, previous)
        return Path(path)

    def assert_input_rejected(self, evidence):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
            document, status = self.reporter.build_metadata(evidence, self.fixture.repo)
        self.assertEqual(status, 2)
        self.assertEqual(document['metadata_error_codes'], ['EVIDENCE_NOT_REGULAR'])
        self.assertFalse(document['rows_exported'])
        self.assertFalse(document['coverage']['all_collected_completed'])
        self.assertFalse(document['coverage']['ci_success_consistent'])
        self.assertIsNone(document['source_commit'])
        self.assertIsNone(document['pytest_exit_code'])
        self.assertEqual(document['phases'], [])
        self.assertEqual(stream.getvalue(), '')
        self.assertNotIn(fixtures.SECRET, json.dumps(document))

    def assert_output_rejected(self, output):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
            status = self.reporter.main([str(self.evidence), str(self.fixture.repo), str(output)])
        self.assertEqual(status, 2)
        self.assertEqual(stream.getvalue(), 'CI_BACKEND_METADATA_OUTPUT_ERROR\n')
        self.assertFalse(output.exists())
        self.assertEqual(list(self.actual.rglob('.backend-metadata-*')), [])

    def test_input_ancestor_preceding_nested_regular_parent_rejected(self):
        self.assert_input_rejected(self.link / 'subdir/evidence')

    def test_input_relative_ancestor_rejected(self):
        self.assert_input_rejected(self.relative('link/subdir/evidence'))

    def test_input_symlink_before_dotdot_not_erased(self):
        self.assert_input_rejected(self.link / '../actual/subdir/evidence')

    def test_input_dangling_ancestor_rejected_with_regular_error(self):
        broken = self.owned / 'broken'
        broken.symlink_to(self.root / 'absent', target_is_directory=True)
        self.assert_input_rejected(broken / 'subdir/evidence')

    def test_input_rejected_before_structured_read_git_or_audit(self):
        # These tripwires expose a too-late guard without reading a forbidden ledger.
        def forbidden(*args, **kwargs):
            raise RuntimeError(fixtures.SECRET)

        with patch.object(self.reporter, 'read_text', side_effect=forbidden), \
                patch.object(self.reporter, 'git', side_effect=forbidden), \
                patch.object(self.reporter, 'audit_evidence', side_effect=forbidden):
            self.assert_input_rejected(self.link / 'subdir/evidence')

    def test_output_ancestor_preceding_nested_regular_parent_rejected(self):
        self.assert_output_rejected(self.link / 'subdir/evidence/backend-metadata.json')

    def test_output_relative_ancestor_rejected(self):
        self.assert_output_rejected(self.relative('link/subdir/evidence/backend-metadata.json'))

    def test_output_symlink_before_dotdot_not_erased(self):
        # Both the lexical and kernel-resolved parents exist, so rejection cannot
        # be an incidental mkstemp failure after it normalizes its dir argument.
        (self.owned / 'actual/subdir/evidence').mkdir(parents=True)
        self.assert_output_rejected(self.link / '../actual/subdir/evidence/backend-metadata.json')

    def test_output_dangling_ancestor_rejected(self):
        broken = self.owned / 'broken'
        broken.symlink_to(self.root / 'absent', target_is_directory=True)
        self.assert_output_rejected(broken / 'subdir/backend-metadata.json')

    def test_output_rejected_before_tempfile_creation(self):
        def forbidden(*args, **kwargs):
            raise RuntimeError(fixtures.SECRET)

        with patch.object(self.reporter.tempfile, 'mkstemp', side_effect=forbidden) as create:
            self.assert_output_rejected(self.link / 'subdir/evidence/backend-metadata.json')
        create.assert_not_called()

    def test_regular_nested_paths_preserve_complete_failed_run(self):
        output = self.evidence / 'backend-metadata.json'
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
            status = self.reporter.main([str(self.evidence), str(self.fixture.repo), str(output)])
        self.assertEqual(status, 0)
        self.assertEqual(stream.getvalue(), 'CI_BACKEND_METADATA_WRITTEN\n')
        document = json.loads(output.read_text(encoding='utf-8'))
        self.assertEqual(document['pytest_exit_code'], 1)
        self.assertTrue(document['coverage']['all_collected_completed'])
        self.assertFalse(document['coverage']['ci_success_consistent'])
        self.assertEqual(document['coverage']['collected_count'], 2)
        self.assertEqual(len(document['phases']), 6)
        self.assertEqual(document['failures'], [{
            'nodeid_sha256': fixtures.sha(fixtures.NODE), 'phase': 'call',
            'public_test': 'test_public.TestKnown.test_failure'}])
        self.assertEqual(document['metadata_error_codes'], [])
        self.assertNotIn(fixtures.SECRET, output.read_text(encoding='utf-8'))

    def cli(self, evidence, output):
        # Native CLI with the denial hook installed before any reporter imports.
        code = (
            "import sys\n"
            "def deny(event, args):\n"
            "    if event.startswith(('sqlite3.', 'socket.')):\n"
            "        raise RuntimeError('SQL_SOCKET_DENIED')\n"
            "sys.addaudithook(deny)\n"
            "import runpy\n"
            "sys.argv = sys.argv[1:]\n"
            "runpy.run_path(sys.argv[0], run_name='__main__')\n")
        return subprocess.run(
            [sys.executable, '-I', '-c', code, str(fixtures.SCRIPTS / 'ci_backend_metadata.py'),
             str(evidence), str(self.fixture.repo), str(output)],
            env={'PATH': os.defpath, 'HOME': str(self.root)},
            capture_output=True, text=True, check=False)

    def test_native_cli_input_ancestor_exports_only_fixed_incomplete_metadata(self):
        output = self.owned / 'backend-metadata.json'
        result = self.cli(self.link / 'subdir/evidence', output)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, '')
        self.assertEqual(result.stderr, 'CI_BACKEND_METADATA_FAILED\n')
        document = json.loads(output.read_text(encoding='utf-8'))
        self.assertEqual(document['metadata_error_codes'], ['EVIDENCE_NOT_REGULAR'])
        self.assertFalse(document['rows_exported'])
        self.assertFalse(document['coverage']['all_collected_completed'])
        self.assertFalse(document['coverage']['ci_success_consistent'])
        self.assertNotIn(fixtures.SECRET, output.read_text(encoding='utf-8'))

    def test_native_cli_output_ancestor_creates_no_published_or_temporary_file(self):
        output = self.link / 'subdir/evidence/backend-metadata.json'
        result = self.cli(self.evidence, output)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, '')
        self.assertEqual(result.stderr, 'CI_BACKEND_METADATA_OUTPUT_ERROR\n')
        self.assertFalse(output.exists())
        self.assertEqual(list(self.actual.rglob('.backend-metadata-*')), [])


if __name__ == '__main__':
    unittest.main()
