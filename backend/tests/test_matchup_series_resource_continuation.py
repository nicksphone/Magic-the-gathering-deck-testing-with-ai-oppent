"""Actual scheduler/replay caller protocol with INERT actions, not native games."""
import copy
import tempfile
import unittest
from pathlib import Path

from analytics.resource_budget import SimulationResourceLimit
from tests import test_matchup_round_robin_protocol as protocol


class SeriesResourceContinuationTests(unittest.TestCase):
    def route(self, root, *, fault='resource_limit', writer_fault=None, drift=False):
        fixture = protocol.RoundRobinProtocolTests('test_13_complete_callable_route_real_projected_series')
        fixture.setUp()
        limits, _ = fixture.composition()
        api = fixture.runner
        original_checked = fixture.replay['checked_action']
        decisions = []

        def checked(state, engine, pid, action):
            decisions.append(True)
            if len(decisions) == 1:
                if fault in ('resource_limit', 'unknown_stop', 'global_stop') or fault.startswith('receipt_'):
                    raise SimulationResourceLimit('deadline')  # Inert fault, NOT a measured timeout.
                if fault == 'action_error':
                    raise ValueError('inert action fault')
            return original_checked(state, engine, pid, action)

        fixture.replay['checked_action'] = checked
        imports = api['__builtins__']['__import__']
        resource = imports('analytics.resource_budget')
        original_budget = resource.ResourceBudget
        budgets = []

        class TrackedBudget(original_budget):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.starts = []
                budgets.append(self)

            def begin_game(self, log):
                self.starts.append(self.deadline)
                return super().begin_game(log)

        resource.ResourceBudget = TrackedBudget
        original_game = fixture.replay['run_game']
        if fault in ('unknown_stop', 'global_stop') or fault.startswith('receipt_'):
            def returned(*args, **kwargs):
                result = original_game(*args, **kwargs)
                if result.get('stop_reason'):
                    if fault.startswith('receipt_'):
                        if fault == 'receipt_bool':
                            result['evidence']['bytes'] = True
                        elif fault == 'receipt_changed':
                            result['evidence']['raw_sha256'] = 'b' * 64
                        else:
                            result['evidence']['extra'] = 'not a receipt field'
                    else:
                        result['stop_reason'] = 'unknown_stop' if fault == 'unknown_stop' else 'global_budget'
                return result
            imports('scripts.regression_matrix_replay').run_game = returned
        original_writer = api['write_private_game']
        writes = []

        def write(directory, ordinal, result, raw):
            if writer_fault == 'first' or writer_fault == 'second_series' and directory.name == 'series-00001':
                raise OSError('inert output refusal')
            receipt = original_writer(directory, ordinal, result, raw)
            writes.append((directory / receipt['reference'], copy.deepcopy(receipt)))
            return receipt

        api['write_private_game'] = write
        original_closure = api['source_closure']
        if drift:
            samples = []
            def closure(*args):
                result = original_closure(*args)
                self.assertTrue(result['equal'])
                samples.append(True)
                if drift != 'boundary_only' or len(samples) == 1:
                    result.update(equal=False, after_sha256='b' * 64)
                return result
            api['source_closure'] = closure
        result = api['run_round_robin'](api['make_export'](protocol.roster(), corpus_sha256='a' * 64), [1],
            difficulty='strong', max_ticks=6000, limits=dict(limits), private_directory=root / 'private')
        return result, budgets, writes, decisions

    def test_complete_resource_receipt_continues_all110_without_resuming_stopped_bo3(self):
        with tempfile.TemporaryDirectory() as temporary:
            result, budgets, writes, decisions = self.route(Path(temporary))
            self.assertEqual(result['attempted_series'], 110)
            self.assertEqual(result['not_run_series'], 0)
            self.assertFalse(result['complete'])  # Not110 resolved BO3s.
            self.assertEqual(len(result['pairs']), 55)
            stopped = result['series'][0]
            self.assertEqual(stopped['status'], 'resource_limit')
            self.assertIsNone(stopped['winner'])
            self.assertEqual(stopped['wins'], {'deck_a': 0, 'deck_b': 0})
            self.assertEqual(len(stopped['games']), 1)
            self.assertIsNone(stopped['games'][0]['winner'])
            self.assertTrue(stopped['games'][0]['evidence_complete'])
            for later in result['series'][1:]:
                self.assertEqual(later['status'], 'resolved')
                self.assertEqual(later['winner'], 1)
                self.assertEqual(len(later['games']), 2)
            self.assertEqual(result['pairs'][0]['unresolved'], {'resource_limit': 1})
            self.assertEqual(len(budgets), 110)
            self.assertEqual(len({id(b) for b in budgets}), 110)
            self.assertEqual([len(b.starts) for b in budgets], [1] + [2] * 109)
            self.assertTrue(all(b.limits['deadline_seconds'] == 600 for b in budgets))
            self.assertTrue(all(all(deadline == b.deadline for deadline in b.starts) for b in budgets))
            self.assertEqual(len(writes), 219)
            self.assertEqual(len(decisions), 219)
            self.assertEqual(len(list((Path(temporary) / 'private').rglob('game-*.json'))), 219)

    def test_resource_partial_quality_is_not_a_full_game_numeric_certificate(self):
        with tempfile.TemporaryDirectory() as temporary:
            result, _, _, _ = self.route(Path(temporary))
            game = result['series'][0]['games'][0]
            self.assertIsNone(game['quality'])
            self.assertIs(game.get('quality_available'), False)
            self.assertEqual(game.get('quality_unavailable_reason'), 'partial_game_resource_limit')
            self.assertTrue(all(value is None for value in result['pairs'][0]['decision_quality_a'].values()))
            self.assertTrue(all(value is None for value in result['pairs'][0]['decision_quality_b'].values()))

    def test_action_unknown_and_global_stop_remain_fatal_with_complete_receipts(self):
        for fault in ('action_error', 'unknown_stop', 'global_stop'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as temporary:
                result, budgets, writes, _ = self.route(Path(temporary), fault=fault)
                self.assertEqual(result['attempted_series'], 1)
                self.assertEqual(result['not_run_series'], 109)
                self.assertIsNone(result['series'][0]['winner'])
                self.assertEqual(len(budgets), 1)
                self.assertEqual(len(writes), 1)

    def test_missing_resource_receipt_and_ordinary_writer_error_stop_immediately(self):
        for fault in ('resource_limit', 'none'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as temporary:
                result, budgets, writes, _ = self.route(Path(temporary), fault=fault, writer_fault='first')
                self.assertEqual(result['attempted_series'], 1)
                self.assertEqual(len(budgets), 1)
                self.assertEqual(writes, [])
                self.assertIsNone(result['series'][0]['games'][0]['evidence'])
                self.assertFalse(result['series'][0]['games'][0]['evidence_complete'])

    def test_resource_boundary_source_drift_stops_all_later_series(self):
        with tempfile.TemporaryDirectory() as temporary:
            result, budgets, writes, _ = self.route(Path(temporary), drift=True)
            self.assertEqual(result['attempted_series'], 1)
            self.assertEqual(result['not_run_series'], 109)
            self.assertFalse(result['measured_source']['equal'])
            self.assertEqual(len(budgets), 1)
            self.assertEqual(len(writes), 1)
            self.assertIsNone(result['series'][0]['games'][0]['quality'])
            self.assertEqual(result['series'][0]['games'][0]['quality_unavailable_reason'], 'source_unavailable')

    def test_later_writer_fault_stops_without_erasing_prior_resource_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            result, budgets, writes, _ = self.route(Path(temporary), writer_fault='second_series')
            self.assertEqual(result['attempted_series'], 2)
            self.assertEqual(result['not_run_series'], 108)
            self.assertEqual(result['series'][0]['status'], 'resource_limit')
            self.assertEqual(result['series'][1]['status'], 'evidence_error')
            self.assertEqual(len(budgets), 2)
            self.assertEqual(len(writes), 1)
            self.assertTrue(writes[0][0].exists())
            self.assertTrue(result['series'][0]['games'][0]['evidence_complete'])

    def test_observed_source_fault_stays_unavailable_even_if_end_bytes_restore(self):
        with tempfile.TemporaryDirectory() as temporary:
            result, budgets, writes, _ = self.route(Path(temporary), drift='boundary_only')
            self.assertEqual(result['attempted_series'], 1)
            self.assertEqual(len(budgets), 1)
            self.assertEqual(len(writes), 1)
            self.assertFalse(result['measured_source']['equal'])
            self.assertIn('source_unavailable_reason', result['manifest'])
            self.assertEqual(result['series'][0]['games'][0]['quality_unavailable_reason'], 'source_unavailable')

    def test_truthy_but_changed_finite_receipt_cannot_admit_later_series(self):
        for fault in ('receipt_bool', 'receipt_changed', 'receipt_extra'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as temporary:
                result, budgets, writes, _ = self.route(Path(temporary), fault=fault)
                self.assertEqual(result['attempted_series'], 1)
                self.assertEqual(result['not_run_series'], 109)
                self.assertEqual(len(budgets), 1)
                self.assertEqual(len(writes), 1)
