"""Real pytest subreports remain observations, not duplicate parent phases."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_ci_backend_metadata as fixtures

SCRIPTS = Path(__file__).resolve().parents[1]
SECRET = 'SYNTHETIC_SUBTEST_CONTEXT_NOT_FOR_PUBLIC_METADATA'
BODY = '''import os, unittest
class PublicSubtests(unittest.TestCase):
    def test_five(self):
        for index in range(5):
            with self.subTest(private_context="SYNTHETIC_SUBTEST_CONTEXT_NOT_FOR_PUBLIC_METADATA"):
                if os.environ.get("SUBTEST_CASE") == "fail" and index == 1:
                    self.fail("synthetic failure")
                if os.environ.get("SUBTEST_CASE") == "skip" and index == 1:
                    self.skipTest("synthetic skip")
    def test_ten(self):
        for index in range(10):
            with self.subTest(private_context="SYNTHETIC_SUBTEST_CONTEXT_NOT_FOR_PUBLIC_METADATA"):
                self.assertTrue(index >= 0)
'''
CHILD = '''import sys
def deny(event,args):
    if event.startswith(('sqlite3.','socket.','subprocess.','os.exec')) or event in ('os.system','os.fork','os.posix_spawn'):
        raise RuntimeError('PURE_OPERATION_DENIED')
sys.addaudithook(deny)
sys.path[:0]=[sys.argv.pop(1)]
import pytest
raise SystemExit(pytest.main(sys.argv[1:]))
'''
OBSERVER = '''import hashlib, json, os
from pathlib import Path
from _pytest.reports import TestReport
from _pytest.subtests import SubtestReport
def pytest_runtest_logreport(report):
    row={'nodeid_sha256':hashlib.sha256(report.nodeid.encode()).hexdigest(),
         'phase':report.when,'outcome':report.outcome,
         'exact_subtest_type':type(report) is SubtestReport,
         'exact_parent_type':type(report) is TestReport,
         'class_module':type(report).__module__,'class_name':type(report).__name__}
    with (Path(os.environ['MTG_CI_EVIDENCE'])/'producer-types.jsonl').open('a') as stream:
        stream.write(json.dumps(row,sort_keys=True)+'\\n')
'''


class SubtestReportTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.MetadataTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.MetadataTests.tearDownClass.__func__)
    git = classmethod(fixtures.MetadataTests.git.__func__)
    reporter = fixtures.MetadataTests.reporter
    rows = fixtures.MetadataTests.rows
    ledger = fixtures.MetadataTests.ledger
    audit = fixtures.MetadataTests.audit
    export = fixtures.MetadataTests.export

    def setUp(self):
        fixtures.MetadataTests.setUp(self)
        self.commit = self.git('rev-parse', 'HEAD').strip()

    def actual_pytest(self, case='pass'):
        path = self.repo / 'backend/tests/test_subtest_fixture.py'
        path.write_text(BODY + '\n# synthetic instance ' + self.root.name + '\n')
        self.git('add', 'backend/tests/test_subtest_fixture.py')
        self.git('-c', 'commit.gpgsign=false', 'commit', '-qm', 'public synthetic subtests')
        self.commit = self.git('rev-parse', 'HEAD').strip()
        observer = self.root / 'observer'
        observer.mkdir()
        (observer / 'producer_observer.py').write_text(OBSERVER)
        env = {'PATH': os.defpath, 'HOME': str(self.root), 'TMPDIR': str(self.root),
               'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1', 'PYTHONDONTWRITEBYTECODE': '1',
               'MTG_CI_EVIDENCE': str(self.evidence), 'MTG_ISOLATED_TEST_ROOT': str(self.repo),
               'SUBTEST_CASE': case}
        # Both plugins observe the same genuinely produced reports; no manual mock reports.
        script = CHILD.replace('sys.path[:0]=[sys.argv.pop(1)]',
                               'sys.path[:0]=[sys.argv.pop(1),sys.argv.pop(1)]')
        result = subprocess.run([sys.executable, '-I', '-B', '-c', script,
                                 str(SCRIPTS), str(observer), '-q', '-p', 'no:cacheprovider',
                                 '-p', 'ci_backend_evidence', '-p', 'producer_observer', str(path)],
                                cwd=self.repo / 'backend', env=env,
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, int(case == 'fail'), result.stdout + result.stderr)
        (self.evidence / 'pytest-exit-code.txt').write_text(str(result.returncode) + '\n')
        (self.evidence / 'source-head.txt').write_text(self.commit + '\n')
        producers = [json.loads(line) for line in
                     (self.evidence / 'producer-types.jsonl').read_text().splitlines()]
        self.assertEqual(sum(row['exact_subtest_type'] for row in producers), 15)
        self.assertEqual(sum(row['exact_parent_type'] for row in producers), 6)
        self.assertEqual({(row['class_module'], row['class_name']) for row in producers
                          if row['exact_subtest_type']}, {('_pytest.subtests', 'SubtestReport')})
        print('ACTUAL_PRODUCERS=' + json.dumps({'case': case, 'subreports': 15,
              'ordinary_reports': 6, 'subreport_class': '_pytest.subtests.SubtestReport'}))
        self.audit(result.returncode)
        return producers

    def test_actual_pytest_two_nodes_five_and_ten_reports_are_all_retained(self):
        producers = self.actual_pytest()
        phases = [json.loads(line) for line in (self.evidence / 'phases.jsonl').read_text().splitlines()]
        self.assertEqual(len(phases), 6, 'real subreports polluted the parent phase ledger')
        subtests = [json.loads(line) for line in (self.evidence / 'subtests.jsonl').read_text().splitlines()]
        self.assertEqual(len(subtests), 15)
        self.assertEqual(len(phases) + len(subtests), len(producers))
        self.assertTrue(all(row['phase'] == 'call' and row['outcome'] == 'passed' for row in subtests))
        self.assertTrue(all(type(row['duration_seconds']) in (int, float) for row in subtests))
        document, status = self.export()
        self.assertEqual(status, 0)
        self.assertTrue(document['coverage']['ci_success_consistent'])
        self.assertEqual(len(document.get('subtests', [])), 15)
        self.assertNotIn(SECRET, json.dumps(document))

    def test_actual_failed_subtest_and_skip_outcomes_survive(self):
        self.actual_pytest('fail')
        document, status = self.export()
        self.assertEqual(status, 0)
        self.assertFalse(document['coverage']['ci_success_consistent'])
        self.assertEqual(sum(row['outcome'] == 'failed' for row in document.get('subtests', [])), 1)
        self.assertTrue(any(row.get('report_kind') == 'subtest' for row in document['failures']))
        self.assertNotIn(SECRET, json.dumps(document))

    def test_actual_skipped_subtest_is_not_a_pass(self):
        self.actual_pytest('skip')
        document, status = self.export()
        self.assertEqual(status, 0)
        self.assertEqual(sum(row['outcome'] == 'skipped' for row in document.get('subtests', [])), 1)
        self.assertEqual(sum(row['outcome'] == 'passed' for row in document.get('subtests', [])), 14)

    def test_failed_subtest_cannot_be_hidden_by_passing_parent_and_zero_exit(self):
        self.ledger(nodes=[fixtures.SECOND], exitcode=0)
        self.rows('subtests.jsonl', [{'nodeid': fixtures.SECOND, 'phase': 'call',
                                   'outcome': 'failed', 'duration_seconds': 0.1}])
        self.audit(0)
        document, status = self.export()
        self.assertEqual(status, 2)
        self.assertFalse(document['coverage']['ci_success_consistent'])
        self.assertIn('SUCCESS_INCONSISTENT', document['metadata_error_codes'])
        self.assertEqual(document.get('subtests', [])[0]['outcome'], 'failed')

    def test_only_exact_subreport_type_is_separated_and_optional_pytest8_is_safe(self):
        from _pytest.reports import TestReport
        from _pytest.subtests import SubtestContext, SubtestReport
        auditor = fixtures.load('ci_backend_evidence')
        auditor._evidence_root = self.evidence
        report = TestReport(fixtures.SECOND, ('tests/test_public.py', 0, 'test_success'),
                            {}, 'passed', None, 'call', duration=0.2)
        sub = SubtestReport._new(report, SubtestContext(msg=SECRET, kwargs={'payload': SECRET}), None, None)
        auditor.pytest_runtest_logreport(sub)
        self.assertEqual(len(list(self.evidence.glob('subtests.jsonl'))), 1)
        self.assertNotIn(SECRET, (self.evidence / 'subtests.jsonl').read_text())
        class ForeignSubtest(SubtestReport):
            pass
        sub.__class__ = ForeignSubtest
        auditor.pytest_runtest_logreport(sub)
        auditor.pytest_runtest_logreport(report)
        phases = (self.evidence / 'phases.jsonl').read_text().splitlines()
        self.assertEqual(len(phases), 2, 'foreign subtypes must retain ordinary strict handling')
        original = __import__
        def absent(name, *args, **kwargs):
            if name == '_pytest.subtests':
                raise ModuleNotFoundError(name=name)
            return original(name, *args, **kwargs)
        with patch('builtins.__import__', side_effect=absent):
            legacy = fixtures.load('ci_backend_evidence')
        legacy._evidence_root = self.evidence
        legacy.pytest_runtest_logreport(report)
        self.assertEqual(len((self.evidence / 'phases.jsonl').read_text().splitlines()), 3)

    def test_orphan_and_invalid_subreport_rows_fail_closed(self):
        self.ledger(nodes=[fixtures.SECOND], exitcode=0)
        for changes in ({'nodeid': 'tests/foreign.py::test_foreign'}, {'phase': 'setup'},
                        {'outcome': 'unknown'}):
            row = {'nodeid': fixtures.SECOND, 'phase': 'call', 'outcome': 'passed', **changes}
            self.rows('subtests.jsonl', [row])
            self.audit(0)
            document, status = self.export()
            self.assertEqual(status, 2)
            self.assertFalse(document['coverage']['ci_success_consistent'])

    def test_safe_subreport_projection_retains_rows_and_bounds_numeric_duration(self):
        self.ledger(nodes=[fixtures.SECOND], exitcode=0)
        durations = [True, SECRET, -1, 86401, 0.125, 0]
        self.rows('subtests.jsonl', [{'nodeid': fixtures.SECOND, 'phase': 'call',
                   'outcome': 'skipped' if index == 0 else 'passed',
                   'duration_seconds': value, 'context': SECRET, 'kwargs': {'data': SECRET},
                   'msg': SECRET, 'longrepr': SECRET} for index, value in enumerate(durations)])
        self.audit(0)
        document, status = self.export()
        self.assertEqual(status, 0)
        safe = document['subtests']
        self.assertEqual([row['subtest_index'] for row in safe], list(range(6)))
        self.assertEqual([row['duration_seconds'] for row in safe], [None] * 4 + [0.125, 0])
        self.assertEqual(document['coverage']['subtest_counts'], {'passed': 5, 'skipped': 1})
        self.assertNotIn(SECRET, json.dumps(document))


if __name__ == '__main__':
    unittest.main()
