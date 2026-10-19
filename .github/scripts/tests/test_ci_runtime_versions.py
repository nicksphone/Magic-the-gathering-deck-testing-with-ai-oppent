"""Optional pre-pytest version projection; public synthetic metadata only."""
import contextlib
import importlib.metadata
import io
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch

import test_ci_backend_metadata as legacy


SECRET = 'SYNTHETIC_PRIVATE_VERSION_DO_NOT_EXPORT'
ROOT = Path(__file__).resolve().parents[3]
PINS = dict(re.findall(r'^([a-z0-9-]+)==([^ ]+) ',
    (ROOT / 'backend/requirements-py312-linux.lock').read_text(), re.MULTILINE))
DIRECT = re.findall(r'^([a-z0-9-]+)==',
    (ROOT / 'backend/requirements.txt').read_text(), re.MULTILINE)


class RuntimeVersionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        legacy.MetadataTests.setUpClass()

    @classmethod
    def tearDownClass(cls):
        legacy.MetadataTests.tearDownClass()

    def setUp(self):
        self.case = legacy.MetadataTests('test_passing_run_retains_actual_phase_counts')
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.case.ledger(nodes=[legacy.SECOND], exitcode=0)
        self.evidence = self.case.evidence
        self.reporter = self.case.reporter()

    def snapshot(self, packages=None, python='Python 3.12.3\n'):
        if packages is None:
            packages = [{'name': name, 'version': version} for name, version in PINS.items()]
        (self.evidence / 'installed-packages.json').write_text(json.dumps(packages))
        (self.evidence / 'python-version.txt').write_text(python)

    def export(self):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
            document, status = self.reporter.build_metadata(self.evidence, self.case.repo)
        self.assertEqual(stream.getvalue(), '')
        self.assertNotIn(SECRET, json.dumps(document))
        self.assertIn('runtime_versions', document, 'Existing snapshots lack public version projection')
        return document, status

    def projected(self):
        return self.export()[0]['runtime_versions']

    def test_complete_actual_lock_roster_is_observed_not_certified(self):
        self.assertEqual(len(PINS), 28)
        self.assertEqual(len(DIRECT), 9)
        self.snapshot()
        self.assertEqual(self.projected(), {
            'observation': 'before_pytest', 'status': 'available',
            'python_version': '3.12.3', 'packages': PINS,
            'direct_packages': sorted(DIRECT)})

    def test_absent_snapshots_are_explicitly_unavailable(self):
        value = self.projected()
        self.assertEqual(value['status'], 'unavailable')
        self.assertIsNone(value['python_version'])
        self.assertEqual(value['packages'], dict.fromkeys(PINS))

    def test_partial_snapshot_keeps_observed_python_without_invented_packages(self):
        (self.evidence / 'python-version.txt').write_text('Python 3.12.3\n')
        value = self.projected()
        self.assertEqual(value['status'], 'degraded')
        self.assertEqual(value['python_version'], '3.12.3')
        self.assertEqual(value['packages'], dict.fromkeys(PINS))

    def test_unknown_packages_and_extra_keys_never_escape(self):
        self.snapshot([{'name': name, 'version': version, 'path': SECRET, 'env': SECRET}
                       for name, version in PINS.items()] +
                      [{'name': SECRET, 'version': SECRET, 'args': [SECRET]}])
        value = self.projected()
        self.assertEqual(value['status'], 'available')
        self.assertEqual(value['packages'], PINS)

    def test_selected_versions_reject_urls_local_tags_controls_and_non_strings(self):
        for version in (SECRET, 'https://example.invalid/' + SECRET, '2.9.2+' + SECRET,
                        '2.9.2\n' + SECRET, True, 29, None, ['2.9.2'], '1.' * 70):
            with self.subTest(kind=type(version).__name__):
                packages = [{'name': name, 'version': version if name == 'pydantic' else pin}
                            for name, pin in PINS.items()]
                self.snapshot(packages)
                value = self.projected()
                self.assertEqual(value['status'], 'degraded')
                self.assertIsNone(value['packages']['pydantic'])

    def test_duplicate_canonical_selected_names_never_choose_a_winner(self):
        packages = [{'name': name, 'version': version} for name, version in PINS.items()]
        packages.extend([{'name': 'Pydantic_Core', 'version': '2.23.4'},
                         {'name': 'pydantic.core', 'version': '2.23.5'}])
        self.snapshot(packages)
        value = self.projected()
        self.assertEqual(value['status'], 'degraded')
        self.assertIsNone(value['packages']['pydantic-core'])
        self.assertEqual(value['packages']['pydantic'], PINS['pydantic'])

    def test_public_prerelease_versions_remain_observations_not_lock_equality(self):
        packages = [{'name': name, 'version': version} for name, version in PINS.items()]
        packages[0] = {'name': packages[0]['name'].upper(), 'version': '1.2.3rc1.post2.dev3'}
        self.snapshot(packages)
        value = self.projected()
        self.assertEqual(value['status'], 'available')
        self.assertEqual(value['packages'][packages[0]['name'].lower()], '1.2.3rc1.post2.dev3')

    def test_python_version_accepts_only_exact_numeric_producer_line(self):
        for text in ('Python 3.12.3 ' + SECRET, SECRET, 'Python 3.12.3rc1',
                     'Python 3.12.3\n' + SECRET, 'Python True.12.3', '3.12.3'):
            with self.subTest(length=len(text)):
                self.snapshot(python=text)
                value = self.projected()
                self.assertIsNone(value['python_version'])
                self.assertEqual(value['status'], 'degraded')

    def test_malformed_inventory_and_invalid_utf8_never_modify_qualification(self):
        for data in (b'not json', b'{}', b'null', b'false', b'[NaN]', b'\xff'):
            with self.subTest(length=len(data)):
                self.snapshot()
                (self.evidence / 'installed-packages.json').write_bytes(data)
                document, status = self.export()
                self.assertEqual(document['runtime_versions']['packages'], dict.fromkeys(PINS))
                self.assertEqual(document['runtime_versions']['status'], 'degraded')
                self.assertEqual(status, 0)
                self.assertEqual(document['metadata_error_codes'], [])
                self.assertTrue(document['coverage']['ci_success_consistent'])

    def test_symlink_snapshots_are_not_followed_or_echoed(self):
        outside = self.case.root / (SECRET + '.json')
        outside.write_text(SECRET)
        for filename in ('installed-packages.json', 'python-version.txt'):
            (self.evidence / filename).symlink_to(outside)
        original = io.open
        def opening(path, *args, **kwargs):
            if str(path) == str(outside):
                self.fail('Followed private symlink target')
            return original(path, *args, **kwargs)
        with patch('io.open', side_effect=opening):
            self.assertEqual(self.projected()['status'], 'unavailable')

    def test_oversized_snapshots_and_row_count_are_unavailable_not_raw(self):
        for packages in (' ' * (1024 * 1024 + 1), json.dumps([{}] * 1025)):
            with self.subTest(length=len(packages)):
                (self.evidence / 'installed-packages.json').write_text(packages)
                (self.evidence / 'python-version.txt').write_text('Python ' + '1' * 200)
                value = self.projected()
                self.assertEqual(value['status'], 'unavailable')
                self.assertEqual(value['packages'], dict.fromkeys(PINS))

    def test_all_existing_failure_and_coverage_fields_remain_byte_equivalent(self):
        for exitcode, phases in ((0, None), (1, None), (2, [])):
            with self.subTest(exitcode=exitcode):
                self.case.ledger(exitcode=exitcode, phases=phases)
                self.snapshot()
                document, status = self.export()
                document.pop('runtime_versions')
                self.assertTrue(callable(getattr(self.reporter, 'runtime_version_fields', None)))
                with patch.object(self.reporter, 'runtime_version_fields', return_value={}):
                    legacy_document, legacy_status = self.reporter.build_metadata(self.evidence, self.case.repo)
                self.assertEqual((document, status), (legacy_document, legacy_status))

    def test_observation_uses_captured_files_not_converter_environment(self):
        self.snapshot(python='Python 3.12.3\n')
        with patch.object(importlib.metadata, 'version', side_effect=AssertionError('metadata remeasured')):
            self.assertEqual(self.projected()['python_version'], '3.12.3')

    def test_deeply_nested_optional_json_cannot_break_qualification(self):
        self.snapshot()
        (self.evidence / 'installed-packages.json').write_text('[' * 20000 + ']' * 20000)
        document, status = self.export()
        self.assertEqual(document['runtime_versions']['status'], 'degraded')
        self.assertEqual(document['runtime_versions']['packages'], dict.fromkeys(PINS))
        self.assertEqual(status, 0)
        self.assertEqual(document['metadata_error_codes'], [])
        self.assertTrue(document['coverage']['ci_success_consistent'])

    def test_early_ledger_failure_retains_optional_observation_without_changing_error(self):
        self.snapshot()
        (self.evidence / 'collected.json').unlink()
        document, status = self.export()
        self.assertEqual(document['runtime_versions']['status'], 'available')
        self.assertEqual(status, 2)
        self.assertEqual(document['metadata_error_codes'], ['EVIDENCE_MISSING'])
        self.assertFalse(document['coverage']['all_collected_completed'])


if __name__ == '__main__':
    unittest.main()
