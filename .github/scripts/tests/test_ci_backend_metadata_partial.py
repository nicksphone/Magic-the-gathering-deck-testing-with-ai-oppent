"""Synthetic completed-report diagnostics; never terminal-run qualification."""
import contextlib
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import test_ci_backend_metadata as fixtures


PACKAGES = (
    'annotated-doc', 'annotated-types', 'anyio', 'certifi', 'click', 'fastapi',
    'greenlet', 'h11', 'httpcore', 'httpx', 'idna', 'iniconfig',
    'opentelemetry-api', 'packaging', 'pluggy', 'pydantic-core', 'pydantic',
    'pygments', 'pytest', 'python-multipart', 'rapidfuzz', 'sniffio',
    'sqlalchemy', 'sqlmodel', 'starlette', 'typing-extensions',
    'typing-inspection', 'uvicorn',
)
DIRECT = ['fastapi', 'httpx', 'pydantic', 'pytest', 'python-multipart',
          'rapidfuzz', 'sqlmodel', 'starlette', 'uvicorn']


def empty_golden():
    return {
        'schema_version': 1, 'source_commit': None, 'pytest_exit_code': None,
        'coverage': {'all_collected_completed': False,
                     'ci_success_consistent': False, 'collected_count': None,
                     'unique_count': None, 'phase_counts': {},
                     'missing_phases': [], 'duplicate_phases': [],
                     'unexpected_node_sha256': []},
        'collected_node_sha256': [], 'discovered_node_sha256': [],
        'deselected_node_sha256': [], 'deselection_row_count': None,
        'phases': [], 'subtests': [], 'failures': [], 'collection_errors': [],
        'sessions': [], 'unresolved_failure_count': None,
        'rows_exported': False, 'skips_and_xfails_are_not_passes': True,
        'metadata_error_codes': [],
        'timing': {'recorded_phase_count': 0, 'total_recorded_seconds': None,
                   'slowest_phases': []},
    }


def unavailable_runtime_golden():
    return {'observation': 'before_pytest', 'status': 'unavailable',
            'python_version': None, 'packages': dict.fromkeys(PACKAGES),
            'direct_packages': DIRECT}


class PartialMetadataTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.MetadataTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.MetadataTests.tearDownClass.__func__)
    git = classmethod(fixtures.MetadataTests.git.__func__)
    setUp = fixtures.MetadataTests.setUp
    reporter = fixtures.MetadataTests.reporter
    rows = fixtures.MetadataTests.rows
    ledger = fixtures.MetadataTests.ledger
    audit = fixtures.MetadataTests.audit
    export = fixtures.MetadataTests.export
    workflow_run = fixtures.MetadataTests.workflow_run
    run_generation_step = fixtures.MetadataTests.run_generation_step

    def incomplete(self, code):
        document, status = self.export()
        self.assertEqual(status, 2)
        self.assertIsNone(document['pytest_exit_code'])
        self.assertEqual(document['metadata_error_codes'], [code])
        self.assertFalse(document['coverage']['all_collected_completed'])
        self.assertFalse(document['coverage']['ci_success_consistent'])
        self.assertIsNone(document['coverage']['collected_count'])
        self.assertFalse(document['rows_exported'])
        self.assertEqual(document['phases'], [])
        return document

    def partial(self, document, status='available'):
        self.assertIn('partial_diagnostics', document,
                      'Completed report diagnostics were suppressed by the exit error')
        value = document['partial_diagnostics']
        self.assertEqual(value['status'], status)
        self.assertIs(value['nonfinal'], True)
        return value

    def invalid_exit(self, text=''):
        (self.evidence / 'pytest-exit-code.txt').write_text(text, encoding='utf-8')

    def test_invalid_exit_exports_only_nonfinal_completed_report_rows(self):
        for text in ('', fixtures.SECRET, '-15', '256'):
            with self.subTest(exit_text=text):
                phases = self.ledger()
                self.invalid_exit(text)
                document = self.incomplete('EXIT_CODE_INVALID')
                value = self.partial(document)
                self.assertEqual(value['phases'], [
                    {'nodeid_sha256': fixtures.sha(row['nodeid']),
                     'phase': row['phase'], 'outcome': row['outcome'],
                     'xfail_marker': False} for row in phases])
                self.assertEqual(value['timing']['recorded_phase_count'], 6)
                self.assertEqual(value['failures'], [{
                    'nodeid_sha256': fixtures.sha(fixtures.NODE), 'phase': 'call',
                    'public_test': 'test_public.TestKnown.test_failure'}])
                self.rows('phases.jsonl', phases[:1])
                setup_only = self.partial(self.incomplete('EXIT_CODE_INVALID'))
                self.assertEqual([row['phase'] for row in setup_only['phases']], ['setup'])
                self.assertNotIn('completed_tests', setup_only)

    def test_missing_exit_keeps_its_distinct_code_and_io_is_not_missing(self):
        self.ledger()
        exit_path = self.evidence / 'pytest-exit-code.txt'
        exit_path.unlink()
        self.assertEqual(len(self.partial(self.incomplete('EVIDENCE_MISSING'))['phases']), 6)
        target = self.root / 'synthetic-exit-target'
        target.write_text('0\n')
        exit_path.symlink_to(target)
        document = self.incomplete('EVIDENCE_NOT_REGULAR')
        self.assertNotIn('partial_diagnostics', document)
        exit_path.unlink()
        exit_path.write_text('0\n')
        reporter = self.reporter()
        original = reporter.read_text

        def unreadable(root, name, *args, **kwargs):
            if name == 'pytest-exit-code.txt':
                raise PermissionError(fixtures.SECRET)
            return original(root, name, *args, **kwargs)

        with patch.object(reporter, 'read_text', side_effect=unreadable):
            document, status = reporter.build_metadata(self.evidence, self.repo)
        self.assertEqual(status, 2)
        self.assertEqual(document['metadata_error_codes'], ['EVIDENCE_IO_ERROR'])
        self.assertNotIn('partial_diagnostics', document)
        self.assertNotIn(fixtures.SECRET, json.dumps(document))

    def test_valid_exit_documents_and_encoded_bytes_match_independent_goldens(self):
        for exitcode, nodes in ((0, [fixtures.SECOND]),
                                (1, [fixtures.NODE, fixtures.SECOND])):
            with self.subTest(exitcode=exitcode):
                phases = self.ledger(nodes=nodes, exitcode=exitcode)
                expected = empty_golden()
                expected.update(source_commit=self.commit, pytest_exit_code=exitcode,
                                runtime_versions=unavailable_runtime_golden())
                expected['coverage'].update(
                    all_collected_completed=True, ci_success_consistent=exitcode == 0,
                    collected_count=len(nodes), unique_count=len(nodes),
                    phase_counts={key: sum(row['phase'] + '/' + row['outcome'] == key
                                           for row in phases) for key in
                                  dict.fromkeys(row['phase'] + '/' + row['outcome']
                                                for row in phases)})
                expected.update(
                    collected_node_sha256=[fixtures.sha(node) for node in nodes],
                    discovered_node_sha256=[fixtures.sha(node) for node in nodes],
                    deselection_row_count=0, unresolved_failure_count=0,
                    rows_exported=True, failure_diagnostics_status='not_recorded',
                    sessions=[{'event': 'start'}, {'event': 'finish', 'exitstatus': exitcode}])
                expected['phases'] = [
                    {'nodeid_sha256': fixtures.sha(row['nodeid']),
                     'phase': row['phase'], 'outcome': row['outcome'],
                     'xfail_marker': False} for row in phases]
                names = {fixtures.NODE: 'test_public.TestKnown.test_failure',
                         fixtures.SECOND: 'test_public.test_success'}
                expected['failures'] = [
                    {'nodeid_sha256': fixtures.sha(row['nodeid']), 'phase': row['phase'],
                     'public_test': names[row['nodeid']]}
                    for row in phases if row['outcome'] == 'failed']
                expected['timing'] = {
                    'recorded_phase_count': len(phases),
                    'total_recorded_seconds': len(phases) * 0.25,
                    'slowest_phases': [
                        {'nodeid_sha256': fixtures.sha(row['nodeid']),
                         'public_test': names[row['nodeid']], 'phase': row['phase'],
                         'seconds': 0.25} for row in phases]}
                document, status = self.export()
                self.assertEqual((document, status), (expected, 0))
                output = self.root / ('healthy-' + str(exitcode) + '.json')
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    status = self.reporter().main([str(self.evidence), str(self.repo), str(output)])
                self.assertEqual(status, 0)
                self.assertEqual(output.read_bytes(),
                                 (json.dumps(expected, sort_keys=True, indent=2) + '\n').encode())
                (self.evidence / 'coverage.json').unlink()
                unavailable = empty_golden()
                unavailable.update(source_commit=self.commit, pytest_exit_code=exitcode,
                                   runtime_versions=unavailable_runtime_golden(),
                                   metadata_error_codes=['EVIDENCE_MISSING'])
                self.assertEqual(self.export(), (unavailable, 2))

    def test_invalid_or_unterminated_phase_file_never_salvages_a_valid_prefix(self):
        self.ledger()
        self.invalid_exit()
        valid = json.dumps({'nodeid': fixtures.SECOND, 'phase': 'setup', 'outcome': 'passed'})
        invalid = (
            fixtures.SECRET, '{', 'null', '[]',
            json.dumps({'nodeid': [], 'phase': 'call', 'outcome': 'passed'}),
            json.dumps({'nodeid': fixtures.SECOND, 'phase': fixtures.SECRET, 'outcome': 'passed'}),
            json.dumps({'nodeid': fixtures.SECOND, 'phase': 'call', 'outcome': fixtures.SECRET}),
            '{"nodeid":"x","phase":"call","outcome":"passed","duration_seconds":NaN}',
        )
        for tail in invalid:
            with self.subTest(tail=tail):
                (self.evidence / 'phases.jsonl').write_text(valid + '\n' + tail + '\n')
                value = self.partial(self.incomplete('EXIT_CODE_INVALID'), 'unavailable')
                self.assertFalse(value.get('phases'))
                self.assertTrue(value['error_codes'])
        for raw in ((valid + '\n' + valid).encode(), valid.encode() + b'\n\xff\n', b''):
            with self.subTest(raw_kind=repr(raw[-8:])):
                (self.evidence / 'phases.jsonl').write_bytes(raw)
                value = self.partial(self.incomplete('EXIT_CODE_INVALID'), 'unavailable')
                self.assertFalse(value.get('phases'))
        (self.evidence / 'phases.jsonl').unlink()
        self.partial(self.incomplete('EXIT_CODE_INVALID'), 'unavailable')

    def test_source_and_phase_path_trust_checks_precede_partial_observation(self):
        self.ledger()
        self.invalid_exit()
        (self.evidence / 'source-head.txt').write_text('0' * 40)
        reporter = self.reporter()
        original = reporter.read_text

        def no_phase_read(root, name, *args, **kwargs):
            if name == 'phases.jsonl':
                self.fail('Unbound source reached partial phase observation')
            return original(root, name, *args, **kwargs)

        with patch.object(reporter, 'read_text', side_effect=no_phase_read):
            document, status = reporter.build_metadata(self.evidence, self.repo)
        self.assertEqual(status, 2)
        self.assertEqual(document['metadata_error_codes'], ['SOURCE_COMMIT_MISMATCH'])
        self.assertNotIn('partial_diagnostics', document)
        (self.evidence / 'source-head.txt').write_text(self.commit)
        phase_path = self.evidence / 'phases.jsonl'
        phase_path.unlink()
        target = self.root / 'synthetic-phase-target'
        target.write_text(fixtures.SECRET)
        phase_path.symlink_to(target)
        self.partial(self.incomplete('EXIT_CODE_INVALID'), 'unavailable')
        phase_path.unlink()
        phase_path.mkdir()
        self.partial(self.incomplete('EXIT_CODE_INVALID'), 'unavailable')
        phase_path.rmdir()
        phase_path.write_text('{}\n')
        linked = self.root / 'evidence-link'
        linked.symlink_to(self.evidence, target_is_directory=True)
        with patch.object(reporter, 'read_text', side_effect=AssertionError('early path guard missed')):
            document, status = reporter.build_metadata(linked, self.repo)
        self.assertEqual(status, 2)
        self.assertEqual(document['metadata_error_codes'], ['EVIDENCE_NOT_REGULAR'])
        self.assertNotIn('partial_diagnostics', document)

    def test_hash_order_skip_xfail_and_unknown_names_do_not_invent_completion(self):
        phases = self.ledger()
        duplicate = dict(phases[1], wasxfail=fixtures.SECRET, duration_seconds=True)
        unknown = 'tests/untracked.py::test_unknown[synthetic-\u2603::' + fixtures.SECRET + ']'
        phases.extend([duplicate, {'nodeid': unknown, 'phase': 'setup', 'outcome': 'skipped',
                                   'duration_seconds': -1}])
        self.rows('phases.jsonl', phases)
        self.invalid_exit()
        value = self.partial(self.incomplete('EXIT_CODE_INVALID'))
        self.assertEqual(len(value['phases']), len(phases))
        self.assertEqual([row['nodeid_sha256'] for row in value['phases']],
                         [fixtures.sha(row['nodeid']) for row in phases])
        self.assertTrue(value['phases'][-2]['xfail_marker'])
        self.assertEqual(value['phases'][-1]['outcome'], 'skipped')
        self.assertEqual(value['timing']['recorded_phase_count'], 6)
        unknown_failure = dict(phases[-1], phase='call', outcome='failed', duration_seconds=1.0)
        phases.append(unknown_failure)
        self.rows('phases.jsonl', phases)
        value = self.partial(self.incomplete('EXIT_CODE_INVALID'))
        self.assertIsNone(value['failures'][-1]['public_test'])
        self.assertEqual(value['failures'][-1]['nodeid_sha256'], fixtures.sha(unknown))
        self.assertNotIn(fixtures.SECRET, json.dumps(value))

    def test_private_keys_raw_files_and_optional_failures_cannot_cross_boundary(self):
        phases = self.ledger()
        for row in phases:
            row.update(excerpt=fixtures.SECRET, env=fixtures.SECRET,
                       game_payload={'private': fixtures.SECRET})
        self.rows('phases.jsonl', phases)
        self.invalid_exit()
        forbidden = {'failures.jsonl', 'pytest.log', 'runner.log', 'failure-signatures.jsonl'}
        for name in forbidden:
            (self.evidence / name).write_text(fixtures.SECRET)
        original = io.open

        def no_raw_read(path, mode='r', *args, **kwargs):
            if not isinstance(path, int) and Path(path).name in forbidden and not set(mode) & set('wax+'):
                self.fail('Partial reporter opened raw/optional content: ' + Path(path).name)
            return original(path, mode, *args, **kwargs)

        with patch('io.open', side_effect=no_raw_read):
            self.partial(self.incomplete('EXIT_CODE_INVALID'))
        reporter = self.reporter()
        with patch.object(reporter, 'phase_timing', side_effect=RuntimeError(fixtures.SECRET)):
            document, status = reporter.build_metadata(self.evidence, self.repo)
        self.assertEqual(status, 2)
        self.assertEqual(document['metadata_error_codes'], ['EXIT_CODE_INVALID'])
        self.assertNotIn(fixtures.SECRET, json.dumps(document))
        self.partial(document, 'unavailable')

    def test_original_cli_workflow_failure_stays_nonzero_with_partial_json_only(self):
        for missing in (False, True):
            with self.subTest(missing=missing):
                output = self.root / 'step-output.txt'
                if output.exists():
                    output.unlink()
                self.ledger()
                self.invalid_exit()
                if missing:
                    (self.evidence / 'pytest-exit-code.txt').unlink()
                result, document = self.run_generation_step()
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, '')
                self.assertEqual(result.stderr, 'CI_BACKEND_METADATA_FAILED\n')
                self.assertEqual(document['metadata_error_codes'],
                                 ['EVIDENCE_MISSING' if missing else 'EXIT_CODE_INVALID'])
                self.assertFalse(document['rows_exported'])
                self.assertFalse(document['coverage']['all_collected_completed'])
                self.assertFalse(document['coverage']['ci_success_consistent'])
                self.assertIsNone(document['pytest_exit_code'])
                self.assertEqual(len(self.partial(document)['phases']), 6)


if __name__ == '__main__':
    unittest.main()
