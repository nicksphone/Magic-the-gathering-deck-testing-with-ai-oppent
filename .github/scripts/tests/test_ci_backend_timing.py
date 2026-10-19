"""Synthetic public phase timings never carry raw parameters or diagnostics."""
import unittest
from unittest.mock import Mock

import test_ci_backend_metadata as fixtures

NODE, SECOND, SECRET, sha = fixtures.NODE, fixtures.SECOND, fixtures.SECRET, fixtures.sha


class TimingTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.MetadataTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.MetadataTests.tearDownClass.__func__)
    git = classmethod(fixtures.MetadataTests.git.__func__)
    setUp = fixtures.MetadataTests.setUp
    reporter = fixtures.MetadataTests.reporter
    rows = fixtures.MetadataTests.rows
    ledger = fixtures.MetadataTests.ledger
    audit = fixtures.MetadataTests.audit
    export = fixtures.MetadataTests.export

    def test_actual_numeric_phase_timings_keep_coverage_and_public_identity(self):
        phases = self.ledger()
        for row, seconds in zip(phases, [1.1, 0.2, 0, 2.5, 0.6, 0.1]):
            row['duration_seconds'] = seconds
        self.rows('phases.jsonl', phases)
        document, status = self.export()
        self.assertEqual(status, 0)
        timing = document.get('timing', {})
        self.assertEqual(timing.get('recorded_phase_count'), 6)
        self.assertEqual(timing.get('total_recorded_seconds'), 4.5)
        self.assertEqual(timing.get('slowest_phases', [None])[0], {
            'nodeid_sha256': sha(SECOND), 'public_test': 'test_public.test_success',
            'phase': 'setup', 'seconds': 2.5})
        self.assertTrue(document['coverage']['all_collected_completed'])

    def test_non_numeric_boolean_missing_negative_and_oversized_values_stay_unavailable(self):
        phases = self.ledger()
        for row, seconds in zip(phases, [True, SECRET, None, -1, 86401, {}]):
            row['duration_seconds'] = seconds
        self.rows('phases.jsonl', phases)
        document, status = self.export()
        self.assertEqual(status, 0)
        self.assertEqual(document.get('timing'), {
            'recorded_phase_count': 0, 'total_recorded_seconds': None,
            'slowest_phases': []})

    def test_unknown_public_identity_remains_null_without_exporting_parameters(self):
        node = 'tests/not_committed.py::test_private[' + SECRET + ']'
        phases = self.ledger(nodes=[node])
        for row in phases:
            row.pop('duration_seconds', None)
        phases[1]['duration_seconds'] = 3.0
        self.rows('phases.jsonl', phases)
        document, status = self.export()
        self.assertEqual(status, 0)
        self.assertEqual(document.get('timing', {}).get('slowest_phases'), [{
            'nodeid_sha256': sha(node), 'public_test': None, 'phase': 'call', 'seconds': 3.0}])

    def test_top_twenty_is_bounded_without_dropping_complete_phase_rows(self):
        nodes = [SECOND + '[' + SECRET + str(index) + ']' for index in range(30)]
        phases = self.ledger(nodes=nodes)
        for index, row in enumerate(phases):
            row['duration_seconds'] = index
        self.rows('phases.jsonl', phases)
        document, status = self.export()
        self.assertEqual(status, 0)
        self.assertEqual(len(document['phases']), 90)
        self.assertEqual(document.get('timing', {}).get('recorded_phase_count'), 90)
        slow = document.get('timing', {}).get('slowest_phases', [])
        self.assertEqual(len(slow), 20)
        self.assertEqual([row['seconds'] for row in slow], list(range(89, 69, -1)))

    def test_public_source_resolution_is_bounded_to_twenty_slowest_rows(self):
        public = Mock()
        public.resolve.return_value = None
        rows = [{'nodeid': SECOND + '[' + str(index) + ']', 'phase': 'call',
                 'duration_seconds': index} for index in range(30)]
        timing = self.reporter().phase_timing(rows, public)
        self.assertEqual(timing['recorded_phase_count'], 30)
        self.assertEqual(public.resolve.call_count, 20)
