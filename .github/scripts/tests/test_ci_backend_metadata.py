"""Synthetic-only reporter qualification; no backend imports or private inputs."""
import sys


def deny_external_io(event, args):
    if event.startswith(('sqlite3.', 'socket.')):
        raise RuntimeError('SQL_SOCKET_DENIED')


sys.addaudithook(deny_external_io)

import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1]
SECRET = 'SYNTHETIC_ONLY_DO_NOT_EXPORT_71c29'
NODE = f'tests/test_public.py::TestKnown::test_failure[{SECRET}]'
SECOND = 'tests/test_public.py::test_success'


def sha(node):
    return hashlib.sha256(node.encode('utf-8')).hexdigest()


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = tempfile.TemporaryDirectory(prefix='metadata-public-')
        cls.repo = Path(cls.workspace.name) / 'source'
        (cls.repo / 'backend/tests').mkdir(parents=True)
        (cls.repo / 'backend/tests/test_public.py').write_text(
            'class TestKnown:\n    def test_failure(self):\n        pass\n'
            f'\ndef test_success():\n    print({SECRET!r})\n'
            '\nasync def test_async():\n    pass\n', encoding='utf-8')
        cls.git_env = {'PATH': os.defpath, 'HOME': cls.workspace.name,
                       'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null',
                       'GIT_AUTHOR_NAME': 'Synthetic', 'GIT_AUTHOR_EMAIL': 'synthetic@example.invalid',
                       'GIT_COMMITTER_NAME': 'Synthetic', 'GIT_COMMITTER_EMAIL': 'synthetic@example.invalid'}
        cls.git('init', '-q')
        cls.git('add', 'backend/tests/test_public.py')
        cls.git('-c', 'commit.gpgsign=false', 'commit', '-qm', 'public synthetic definitions')
        cls.commit = cls.git('rev-parse', 'HEAD').strip()
        cls.auditor = load('ci_backend_evidence')

    @classmethod
    def tearDownClass(cls):
        cls.workspace.cleanup()

    @classmethod
    def git(cls, *args):
        return subprocess.run(['git', '-C', str(cls.repo), *args], env=cls.git_env,
                              check=True, capture_output=True, text=True).stdout

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='metadata-ledger-')
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.evidence = self.root / 'evidence'
        self.evidence.mkdir()

    def reporter(self):
        self.assertTrue((SCRIPTS / 'ci_backend_metadata.py').is_file(),
                        'Metadata reporter is not implemented')
        return load('ci_backend_metadata')

    def rows(self, filename, rows):
        (self.evidence / filename).write_text(
            ''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')

    def ledger(self, nodes=None, phases=None, exitcode=1, discovered=None,
               deselected=(), collection_errors=(), sessions=None):
        nodes = [NODE, SECOND] if nodes is None else nodes
        if phases is None:
            phases = [{'nodeid': node, 'phase': phase,
                       'outcome': 'failed' if node == NODE and phase == 'call' else 'passed',
                       'duration_seconds': 0.25}
                      for node in nodes for phase in ('setup', 'call', 'teardown')]
        (self.evidence / 'collected.json').write_text(json.dumps({'nodeids': nodes}), encoding='utf-8')
        self.rows('discovered.jsonl', [{'nodeid': node} for node in
                                     (nodes if discovered is None else discovered)])
        self.rows('phases.jsonl', phases)
        self.rows('deselected.jsonl', deselected)
        self.rows('collection-errors.jsonl', collection_errors)
        self.rows('session.jsonl', [{'event': 'start'}, {'event': 'finish', 'exitstatus': exitcode}]
                  if sessions is None else sessions)
        (self.evidence / 'pytest-exit-code.txt').write_text(f'{exitcode}\n', encoding='utf-8')
        (self.evidence / 'source-head.txt').write_text(self.commit + '\n', encoding='utf-8')
        self.audit(exitcode)
        return phases

    def audit(self, exitcode=1):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            self.auditor.audit(self.evidence, exitcode)
        (self.evidence / 'coverage.json').write_text(stream.getvalue(), encoding='utf-8')

    def export(self):
        reporter = self.reporter()
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
            result = reporter.build_metadata(self.evidence, self.repo)
        self.assertEqual(stream.getvalue(), '', 'Raw auditor output escaped')
        document, status = result
        encoded = json.dumps(document, sort_keys=True)
        self.assertNotIn(SECRET, encoded)
        self.assertEqual(json.loads(encoded), document)
        return document, status

    def test_synthetic_secrets_never_escape_complete_failed_run(self):
        phases = self.ledger()
        for row in phases:
            row.update(wasxfail=SECRET, excerpt=SECRET, env=SECRET, path=SECRET,
                       game_payload={'private': SECRET})
        self.rows('phases.jsonl', phases)
        (self.evidence / 'failures.jsonl').write_text(SECRET, encoding='utf-8')
        (self.evidence / 'pytest.log').write_text(SECRET, encoding='utf-8')
        original_open = io.open

        def public_open(path, *args, **kwargs):
            if str(path).endswith(('failures.jsonl', 'pytest.log')):
                self.fail('Reporter opened forbidden raw evidence')
            return original_open(path, *args, **kwargs)

        with patch('io.open', side_effect=public_open):
            document, status = self.export()
        self.assertEqual(status, 0)
        self.assertEqual(document['pytest_exit_code'], 1)
        self.assertTrue(document['coverage']['all_collected_completed'])
        self.assertFalse(document['coverage']['ci_success_consistent'])
        self.assertEqual(document['collected_node_sha256'], [sha(NODE), sha(SECOND)])
        self.assertEqual(document['discovered_node_sha256'], [sha(NODE), sha(SECOND)])
        self.assertEqual(document['phases'], [
            {'nodeid_sha256': sha(row['nodeid']), 'phase': row['phase'],
             'outcome': row['outcome'], 'xfail_marker': True} for row in phases])
        self.assertEqual(document['failures'], [
            {'nodeid_sha256': sha(NODE), 'phase': 'call',
             'public_test': 'test_public.TestKnown.test_failure'}])
        self.assertEqual(document['metadata_error_codes'], [])

    def test_passing_run_retains_actual_phase_counts(self):
        self.ledger(nodes=[SECOND], exitcode=0)
        document, status = self.export()
        self.assertEqual(status, 0)
        self.assertEqual(document['coverage']['phase_counts'],
                         {'setup/passed': 1, 'call/passed': 1, 'teardown/passed': 1})
        self.assertTrue(document['coverage']['ci_success_consistent'])
        self.assertEqual(document['failures'], [])

    def test_setup_failure_does_not_require_call(self):
        self.ledger(nodes=[NODE], phases=[
            {'nodeid': NODE, 'phase': 'setup', 'outcome': 'failed'},
            {'nodeid': NODE, 'phase': 'teardown', 'outcome': 'passed'}])
        document, status = self.export()
        self.assertEqual(status, 0)
        self.assertTrue(document['coverage']['all_collected_completed'])
        self.assertEqual(document['failures'][0]['phase'], 'setup')

    def test_skips_and_xfails_are_not_relabelled_passes(self):
        self.ledger(nodes=[NODE], exitcode=0, phases=[
            {'nodeid': NODE, 'phase': 'setup', 'outcome': 'passed'},
            {'nodeid': NODE, 'phase': 'call', 'outcome': 'skipped', 'wasxfail': SECRET},
            {'nodeid': NODE, 'phase': 'teardown', 'outcome': 'passed'}])
        document, status = self.export()
        self.assertEqual(status, 0)
        self.assertEqual(document['phases'][1]['outcome'], 'skipped')
        self.assertTrue(document['phases'][1]['xfail_marker'])
        self.assertEqual(document['coverage']['phase_counts']['call/skipped'], 1)
        self.assertTrue(document['skips_and_xfails_are_not_passes'])

    def test_duplicate_phases_and_failures_are_never_deduplicated(self):
        phases = self.ledger()
        phases.append(dict(phases[1]))
        self.rows('phases.jsonl', phases)
        self.audit()
        document, status = self.export()
        self.assertEqual(status, 2)
        self.assertEqual(len(document['phases']), 7)
        self.assertEqual(len(document['failures']), 2)
        self.assertEqual(document['coverage']['duplicate_phases'],
                         [{'nodeid_sha256': sha(NODE), 'phase': 'call'}])
        self.assertIn('COVERAGE_INCOMPLETE', document['metadata_error_codes'])

    def test_duplicate_collection_rows_remain_visible(self):
        self.ledger(nodes=[SECOND, SECOND], exitcode=0)
        document, status = self.export()
        self.assertEqual(status, 2)
        self.assertEqual(document['collected_node_sha256'], [sha(SECOND), sha(SECOND)])
        self.assertEqual(document['coverage']['collected_count'], 2)
        self.assertEqual(document['coverage']['unique_count'], 1)
        self.assertEqual(len(document['phases']), 6)

    def test_missing_phases_and_unexpected_nodes_are_hashed_not_hidden(self):
        phases = self.ledger()
        phases.pop(2)
        unknown = f'/synthetic/{SECRET}/unknown.py::test_unknown'
        phases.append({'nodeid': unknown, 'phase': 'call', 'outcome': 'failed'})
        self.rows('phases.jsonl', phases)
        self.audit()
        document, status = self.export()
        self.assertEqual(status, 2)
        self.assertEqual(document['coverage']['missing_phases'],
                         [{'nodeid_sha256': sha(NODE), 'phase': 'teardown'}])
        self.assertEqual(document['coverage']['unexpected_node_sha256'], [sha(unknown)])
        self.assertIsNone(document['failures'][-1]['public_test'])
        self.assertEqual(len(document['phases']), 6)

    def test_discovery_mismatch_is_incomplete(self):
        self.ledger(discovered=[SECOND])
        document, status = self.export()
        self.assertEqual(status, 2)
        self.assertFalse(document['coverage']['all_collected_completed'])
        self.assertEqual(document['discovered_node_sha256'], [sha(SECOND)])

    def test_deselection_rows_including_empty_rows_are_counted(self):
        self.ledger(deselected=[{'nodeids': [NODE, NODE]}, {'nodeids': []}])
        document, status = self.export()
        self.assertEqual(status, 2)
        self.assertEqual(document['deselected_node_sha256'], [sha(NODE), sha(NODE)])
        self.assertEqual(document['deselection_row_count'], 2)

    def test_collection_errors_preserve_repeated_hashes(self):
        node = f'tests/{SECRET}.py'
        self.ledger(collection_errors=[{'nodeid': node}, {'nodeid': node}])
        document, status = self.export()
        self.assertEqual(status, 2)
        self.assertEqual(document['collection_errors'], [
            {'nodeid_sha256': sha(node), 'phase': 'collection', 'public_test': None}] * 2)

    def test_empty_collection_and_interrupted_session_fail_closed(self):
        for nodes, sessions in [([], None), ([NODE], [{'event': 'start'}])]:
            with self.subTest(nodes=len(nodes)):
                self.ledger(nodes=nodes, sessions=sessions)
                document, status = self.export()
                self.assertEqual(status, 2)
                self.assertFalse(document['coverage']['all_collected_completed'])

    def test_exit_zero_with_failed_phase_cannot_be_success(self):
        self.ledger(exitcode=0)
        document, status = self.export()
        self.assertEqual(status, 2)
        self.assertTrue(document['coverage']['all_collected_completed'])
        self.assertFalse(document['coverage']['ci_success_consistent'])
        self.assertIn('SUCCESS_INCONSISTENT', document['metadata_error_codes'])

    def test_stale_coverage_cannot_be_accepted(self):
        self.ledger()
        coverage = json.loads((self.evidence / 'coverage.json').read_text())
        coverage['collected_count'] = 900
        (self.evidence / 'coverage.json').write_text(json.dumps(coverage))
        document, status = self.export()
        self.assertEqual(status, 2)
        self.assertIn('COVERAGE_MISMATCH', document['metadata_error_codes'])
        self.assertFalse(document['coverage']['ci_success_consistent'])

    def test_coverage_boolean_is_not_accepted_as_integer_count(self):
        self.ledger(nodes=[SECOND], exitcode=0)
        coverage = json.loads((self.evidence / 'coverage.json').read_text())
        coverage['collected_count'] = True
        (self.evidence / 'coverage.json').write_text(json.dumps(coverage))
        document, status = self.export()
        self.assertEqual(status, 2)
        self.assertIn('COVERAGE_MISMATCH', document['metadata_error_codes'])

    def test_import_stdout_is_captured_before_existing_audit_load(self):
        self.ledger()
        reporter = self.reporter()
        original = reporter.importlib.util.spec_from_file_location

        def noisy_spec(*args, **kwargs):
            spec = original(*args, **kwargs)
            execute = spec.loader.exec_module

            def noisy_execute(module):
                print(SECRET)
                execute(module)

            spec.loader.exec_module = noisy_execute
            return spec

        stream = io.StringIO()
        with patch.object(reporter.importlib.util, 'spec_from_file_location', side_effect=noisy_spec):
            with contextlib.redirect_stdout(stream):
                document, status = reporter.build_metadata(self.evidence, self.repo)
        self.assertEqual(status, 0)
        self.assertNotIn(SECRET, stream.getvalue() + json.dumps(document))

    def test_only_fixed_error_codes_can_cross_boundary(self):
        self.ledger()
        reporter = self.reporter()
        with patch.object(reporter, 'git', side_effect=reporter.MetadataError(SECRET)):
            document, status = reporter.build_metadata(self.evidence, self.repo)
        self.assertEqual(status, 2)
        self.assertNotIn(SECRET, json.dumps(document))
        self.assertEqual(document['metadata_error_codes'], ['METADATA_INTERNAL_ERROR'])

    def test_teardown_failures_preserve_ordered_public_identifiers(self):
        self.ledger(nodes=[SECOND], phases=[
            {'nodeid': SECOND, 'phase': 'setup', 'outcome': 'passed'},
            {'nodeid': SECOND, 'phase': 'call', 'outcome': 'failed'},
            {'nodeid': SECOND, 'phase': 'teardown', 'outcome': 'failed'}])
        document, status = self.export()
        self.assertEqual(status, 0)
        self.assertEqual(document['failures'], [
            {'nodeid_sha256': sha(SECOND), 'phase': phase, 'public_test': 'test_public.test_success'}
            for phase in ('call', 'teardown')])

    def test_nonstrict_xpass_marker_keeps_original_native_outcome(self):
        self.ledger(nodes=[SECOND], exitcode=0, phases=[
            {'nodeid': SECOND, 'phase': 'setup', 'outcome': 'passed'},
            {'nodeid': SECOND, 'phase': 'call', 'outcome': 'passed', 'wasxfail': SECRET},
            {'nodeid': SECOND, 'phase': 'teardown', 'outcome': 'passed'}])
        document, status = self.export()
        self.assertEqual(status, 0)
        self.assertEqual(document['phases'][1], {'nodeid_sha256': sha(SECOND), 'phase': 'call',
                                               'outcome': 'passed', 'xfail_marker': True})

    def test_setup_skip_requires_teardown_but_no_call(self):
        self.ledger(nodes=[SECOND], exitcode=0, phases=[
            {'nodeid': SECOND, 'phase': 'setup', 'outcome': 'skipped'},
            {'nodeid': SECOND, 'phase': 'teardown', 'outcome': 'passed'}])
        document, status = self.export()
        self.assertEqual(status, 0)
        self.assertEqual(len(document['phases']), 2)
        self.assertEqual(document['coverage']['phase_counts'], {'setup/skipped': 1, 'teardown/passed': 1})

    def test_malformed_structured_inputs_have_fixed_errors(self):
        cases = [('phases.jsonl', SECRET), ('coverage.json', SECRET),
                 ('collected.json', json.dumps({'nodeids': [42]})),
                 ('phases.jsonl', json.dumps({'nodeid': NODE, 'phase': SECRET, 'outcome': 'failed'}) + '\n'),
                 ('phases.jsonl', json.dumps({'nodeid': NODE, 'phase': 'call', 'outcome': SECRET}) + '\n'),
                 ('session.jsonl', json.dumps({'event': 'finish', 'exitstatus': True}) + '\n'),
                 ('discovered.jsonl', json.dumps({'nodeid': {'secret': SECRET}}) + '\n'),
                 ('deselected.jsonl', json.dumps({'nodeids': SECRET}) + '\n'),
                 ('collection-errors.jsonl', json.dumps({'nodeid': None}) + '\n')]
        for filename, text in cases:
            with self.subTest(filename=filename, text=text[:10]):
                self.ledger()
                (self.evidence / filename).write_text(text, encoding='utf-8')
                document, status = self.export()
                self.assertEqual(status, 2)
                self.assertFalse(document['coverage']['ci_success_consistent'])
                self.assertTrue(document['metadata_error_codes'])
                self.assertFalse(document['rows_exported'])

    def test_invalid_exit_codes_and_source_ids_have_no_raw_errors(self):
        for filename, text in [('pytest-exit-code.txt', SECRET),
                               ('pytest-exit-code.txt', '-1'),
                               ('pytest-exit-code.txt', '99'),
                               ('source-head.txt', SECRET),
                               ('source-head.txt', '0' * 40)]:
            with self.subTest(filename=filename, text=text[:10]):
                self.ledger()
                (self.evidence / filename).write_text(text)
                document, status = self.export()
                self.assertEqual(status, 2)
                self.assertFalse(document['coverage']['ci_success_consistent'])

    def test_missing_mandatory_evidence_and_symlinks_fail_closed(self):
        for filename in ('collected.json', 'coverage.json', 'session.jsonl',
                         'pytest-exit-code.txt', 'source-head.txt'):
            with self.subTest(filename=filename):
                self.ledger()
                target = self.evidence / filename
                original = target.read_bytes()
                target.unlink()
                document, status = self.export()
                self.assertEqual(status, 2)
                target.symlink_to(self.root / SECRET)
                document, status = self.export()
                self.assertEqual(status, 2)
                target.unlink()
                target.write_bytes(original)

    def test_absent_optional_ledgers_do_not_default_to_complete(self):
        self.ledger()
        (self.evidence / 'phases.jsonl').unlink()
        (self.evidence / 'discovered.jsonl').unlink()
        self.audit()
        document, status = self.export()
        self.assertEqual(status, 2)
        self.assertEqual(document['phases'], [])
        self.assertFalse(document['coverage']['all_collected_completed'])

    def test_untracked_and_worktree_only_definitions_cannot_resolve(self):
        path = self.repo / 'backend/tests/test_public.py'
        original = path.read_bytes()
        self.addCleanup(path.write_bytes, original)
        path.write_text('def test_worktree_only():\n    pass\n')
        untracked = self.repo / 'backend/tests/test_untracked.py'
        untracked.write_text('def test_untracked():\n    pass\n')
        self.addCleanup(untracked.unlink)
        nodes = [NODE, 'tests/test_public.py::test_worktree_only',
                 'tests/test_untracked.py::test_untracked',
                 f'tests/test_public.py::test_injected_{SECRET}',
                 'tests/test_public.py::test_async']
        self.ledger(nodes=nodes, phases=[{'nodeid': node, 'phase': phase,
                                       'outcome': 'failed' if phase == 'call' else 'passed'}
                                      for node in nodes for phase in ('setup', 'call', 'teardown')])
        document, status = self.export()
        self.assertEqual(status, 0)
        self.assertEqual([row['public_test'] for row in document['failures']],
                         ['test_public.TestKnown.test_failure', None, None, None,
                          'test_public.test_async'])
        self.assertEqual(document['unresolved_failure_count'], 3)

    def test_hash_uses_entire_original_unicode_parameter_text(self):
        nodes = [NODE, 'tests/test_public.py::test_success[synthetic-\u2603::tail]\nline']
        self.ledger(nodes=nodes)
        document, status = self.export()
        self.assertEqual(status, 0)
        self.assertEqual(document['collected_node_sha256'], [sha(node) for node in nodes])
        self.assertNotEqual(sha(nodes[1]), sha(SECOND))

    def test_io_exception_text_never_escapes(self):
        self.ledger()
        reporter = self.reporter()
        with patch.object(Path, 'read_text', side_effect=OSError(SECRET)):
            document, status = reporter.build_metadata(self.evidence, self.repo)
        self.assertEqual(status, 2)
        self.assertNotIn(SECRET, json.dumps(document))
        self.assertIn('EVIDENCE_IO_ERROR', document['metadata_error_codes'])

    def test_cli_writes_only_json_and_retains_failed_backend_exit_code(self):
        self.ledger()
        reporter = self.reporter()
        output = self.root / 'metadata.json'
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
            status = reporter.main([str(self.evidence), str(self.repo), str(output)])
        self.assertEqual(status, 0)
        document = json.loads(output.read_text())
        self.assertEqual(document['pytest_exit_code'], 1)
        self.assertFalse(document['coverage']['ci_success_consistent'])
        self.assertNotIn(SECRET, stream.getvalue() + output.read_text())
        self.assertEqual(list(self.root.glob('*.tmp')), [])

    def test_cli_error_artifact_is_explicitly_incomplete(self):
        self.ledger()
        (self.evidence / 'coverage.json').write_text(SECRET)
        reporter = self.reporter()
        output = self.root / 'metadata.json'
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            status = reporter.main([str(self.evidence), str(self.repo), str(output)])
        self.assertEqual(status, 2)
        document = json.loads(output.read_text())
        self.assertFalse(document['coverage']['all_collected_completed'])
        self.assertFalse(document['rows_exported'])
        self.assertNotIn(SECRET, output.read_text())

    def test_cli_output_failure_never_leaves_success_artifact(self):
        self.ledger()
        reporter = self.reporter()
        output = self.root / SECRET / 'metadata.json'
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
            status = reporter.main([str(self.evidence), str(self.repo), str(output)])
        self.assertEqual(status, 2)
        self.assertFalse(output.exists())
        self.assertNotIn(SECRET, stream.getvalue())

    def test_cli_replace_and_cleanup_errors_are_fixed_without_traceback(self):
        self.ledger()
        reporter = self.reporter()
        output = self.root / 'metadata.json'
        stream = io.StringIO()
        with patch.object(reporter.os, 'replace', side_effect=OSError(SECRET)):
            with patch.object(Path, 'unlink', side_effect=OSError(SECRET)):
                with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
                    status = reporter.main([str(self.evidence), str(self.repo), str(output)])
        self.assertEqual(status, 2)
        self.assertFalse(output.exists())
        self.assertNotIn(SECRET, stream.getvalue())

    def test_cli_refuses_stale_output_without_overwriting_it(self):
        self.ledger()
        reporter = self.reporter()
        output = self.root / 'metadata.json'
        output.write_text('stale artifact')
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            status = reporter.main([str(self.evidence), str(self.repo), str(output)])
        self.assertEqual(status, 2)
        self.assertEqual(output.read_text(), 'stale artifact')

    def test_cli_unexpected_metadata_exception_is_fixed_and_incomplete(self):
        self.ledger()
        reporter = self.reporter()
        output = self.root / 'metadata.json'
        stream = io.StringIO()

        def broken_metadata(*args):
            print(SECRET)
            print(SECRET, file=sys.stderr)
            raise RuntimeError(SECRET)

        with patch.object(reporter, 'build_metadata', side_effect=broken_metadata):
            with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
                try:
                    status = reporter.main([str(self.evidence), str(self.repo), str(output)])
                except Exception:
                    self.fail('Metadata exception escaped the CLI boundary')
        self.assertEqual(status, 2)
        self.assertNotIn(SECRET, stream.getvalue())
        document = json.loads(output.read_text())
        self.assertFalse(document['coverage']['ci_success_consistent'])
        self.assertEqual(document['metadata_error_codes'], ['METADATA_INTERNAL_ERROR'])

    def test_cli_serialization_exception_never_prints_repr(self):
        self.ledger()
        reporter = self.reporter()
        output = self.root / 'metadata.json'
        stream = io.StringIO()
        document, _ = reporter.build_metadata(self.evidence, self.repo)
        with patch.object(reporter, 'build_metadata', return_value=(document, 0)):
            with patch.object(reporter.json, 'dumps', side_effect=RuntimeError(SECRET)):
                with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
                    try:
                        status = reporter.main([str(self.evidence), str(self.repo), str(output)])
                    except Exception:
                        self.fail('Serialization exception escaped the CLI boundary')
        self.assertEqual(status, 2)
        self.assertNotIn(SECRET, stream.getvalue())
        self.assertFalse(output.exists())

    def workflow_run(self):
        workflow = (SCRIPTS.parent / 'workflows/ci.yml').read_text()
        marker = '      - name: Generate backend metadata\n'
        self.assertIn(marker, workflow, 'Metadata generation step is not implemented')
        step = workflow.split(marker, 1)[1].split('      - ', 1)[0]
        return textwrap.dedent(step.split('        run: |\n', 1)[1])

    def run_generation_step(self, mode='', evidence=None):
        script = self.workflow_run()
        bin_path = self.root / 'bin'
        bin_path.mkdir(exist_ok=True)
        python = bin_path / 'python'
        python.write_text(
            '#!/usr/bin/python3 -I\nimport sys\n'
            'def deny(event, args):\n'
            "    if event.startswith(('sqlite3.', 'socket.')):\n"
            "        raise RuntimeError('SQL_SOCKET_DENIED')\n"
            'sys.addaudithook(deny)\nimport os, runpy\n'
            "mode = os.environ.get('SYNTHETIC_METADATA_MODE')\n"
            f"if mode in ('noisy', 'exception'):\n    print({SECRET!r})\n"
            f'    print({SECRET!r}, file=sys.stderr)\n'
            f"if mode == 'exception':\n    raise RuntimeError({SECRET!r})\n"
            'sys.argv = sys.argv[1:]\nrunpy.run_path(sys.argv[0], run_name="__main__")\n')
        python.chmod(0o700)
        # Run the actual workflow shell body; substitute only its public checkout.
        script = script.replace('"$GITHUB_WORKSPACE"', '"$PUBLIC_TEST_SOURCE"')
        output = self.root / 'step-output.txt'
        environment = {'PATH': str(bin_path) + ':' + os.defpath, 'HOME': str(self.root),
                       'RUNNER_TEMP': str(self.root), 'GITHUB_OUTPUT': str(output),
                       'GITHUB_WORKSPACE': str(SCRIPTS.parents[1]),
                       'PUBLIC_TEST_SOURCE': str(self.repo),
                       'BACKEND_EVIDENCE': str(self.evidence) if evidence is None else evidence,
                       'SYNTHETIC_METADATA_MODE': mode}
        result = subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', script],
                                cwd=SCRIPTS.parents[1], env=environment,
                                capture_output=True, text=True)
        lines = output.read_text().splitlines()
        self.assertEqual(len(lines), 1)
        key, value = lines[0].split('=', 1)
        self.assertEqual(key, 'metadata_file')
        artifact = Path(value)
        self.assertEqual(artifact.is_file(), mode != 'exception')
        self.assertTrue((artifact.parent / 'reporter.log').is_file())
        self.assertNotIn(SECRET, result.stdout + result.stderr)
        if mode == 'exception':
            self.assertEqual(set(artifact.parent.iterdir()), {artifact.parent / 'reporter.log'})
            return result, None
        self.assertEqual(set(artifact.parent.iterdir()), {artifact, artifact.parent / 'reporter.log'})
        self.assertNotIn(SECRET, artifact.read_text())
        return result, json.loads(artifact.read_text())

    def test_workflow_exports_failed_backend_metadata_without_turning_it_green(self):
        self.ledger()
        result, document = self.run_generation_step()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(document['pytest_exit_code'], 1)
        self.assertFalse(document['coverage']['ci_success_consistent'])
        self.assertEqual(len(document['phases']), 6)

    def test_workflow_incomplete_reporter_is_an_actual_step_failure(self):
        self.ledger()
        (self.evidence / 'coverage.json').write_text(SECRET)
        result, document = self.run_generation_step()
        self.assertEqual(result.returncode, 2)
        self.assertFalse(document['coverage']['all_collected_completed'])
        self.assertTrue(document['metadata_error_codes'])

    def test_workflow_noisy_reporter_stdout_stderr_never_escape(self):
        self.ledger()
        result, document = self.run_generation_step(mode='noisy')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, 'CI_BACKEND_METADATA_READY\n')
        self.assertEqual(result.stderr, '')
        self.assertEqual(document['pytest_exit_code'], 1)

    def test_workflow_reporter_crash_is_fixed_nonzero_and_never_uploads_raw_log(self):
        self.ledger()
        result, document = self.run_generation_step(mode='exception')
        self.assertNotEqual(result.returncode, 0)
        self.assertIsNone(document)
        self.assertEqual(result.stdout, '')
        self.assertEqual(result.stderr, 'CI_BACKEND_METADATA_FAILED\n')

    def test_workflow_without_backend_evidence_is_incomplete_not_skipped(self):
        result, document = self.run_generation_step(evidence='')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr, 'CI_BACKEND_METADATA_FAILED\n')
        self.assertFalse(document['coverage']['all_collected_completed'])
        self.assertFalse(document['rows_exported'])


if __name__ == '__main__':
    unittest.main()
