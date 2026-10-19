"""Actual scheduler caller controls with inert game bindings, not game evidence."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tests import test_matchup_round_robin_protocol as protocol


class GameQualitySourceTests(unittest.TestCase):
    def route(self, temporary, *, drift=False, unreadable=False):
        fixture = protocol.RoundRobinProtocolTests('test_13_complete_callable_route_real_projected_series')
        fixture.setUp()
        limits, calls = fixture.composition()
        original_closure = fixture.runner['source_closure']
        original_writer = fixture.runner['write_private_game']
        writes = []

        def write(directory, ordinal, result, raw):
            receipt = original_writer(directory, ordinal, result, raw)
            path = directory / receipt['reference']
            writes.append((path, path.read_bytes(), copy.deepcopy(receipt)))
            return receipt

        def closure(*args):
            result = original_closure(*args)
            self.assertTrue(result['equal'])
            if drift:
                result.update(equal=False, after_sha256=None if unreadable else 'b' * 64)
            return result

        fixture.runner.update(source_closure=closure, write_private_game=write)
        result = fixture.runner['run_round_robin'](
            fixture.runner['make_export'](protocol.roster(), corpus_sha256='a' * 64), [0],
            difficulty='strong', max_ticks=1, limits=dict(limits),
            private_directory=Path(temporary) / 'private')
        self.assertEqual(len(calls), 220)  # Inert callbacks, NOT measured games.
        self.assertEqual(len(writes), 220)
        self.assertEqual(result['attempted_series'], 110)
        self.assertEqual(result['not_run_series'], 0)
        for series in result['series']:
            self.assertEqual(series['winner'], 1)
            self.assertEqual(series['wins'], {'deck_a': 2, 'deck_b': 0})
            self.assertEqual(series['status'], 'resolved')
            for n, game in enumerate(series['games']):
                self.assertEqual(game['winner'], 1)
                self.assertEqual(game['seed'], series['root_seed'] + n)
                self.assertTrue(game['evidence_complete'])
                self.assertIsNone(game.get('stop_reason'))
        for path, payload, receipt in writes:
            self.assertEqual(path.read_bytes(), payload)
            stored = json.loads(payload)
            self.assertEqual(hashlib.sha256(payload).hexdigest(), receipt['record_sha256'])
            raw = json.dumps(stored['raw_log'], ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), receipt['raw_sha256'])
            self.assertEqual(len(raw), receipt['bytes'])
            game = result['series'][int(path.parent.name.split('-')[1])]['games'][int(path.stem.split('-')[1]) - 1]
            self.assertEqual(game['evidence'], {key: receipt[key] for key in ('reference', 'complete', 'bytes', 'raw_sha256')})
            self.assertEqual(game['log_hash'], stored['result']['log_hash'])
        return result

    def test_drift_and_unreadable_caller_clear_all_game_quality_not_outcomes(self):
        for unreadable in (False, True):
            with self.subTest(unreadable=unreadable), tempfile.TemporaryDirectory() as temporary:
                result = self.route(temporary, drift=True, unreadable=unreadable)
                self.assertFalse(result['complete'])
                self.assertEqual(result['status'], 'stopped')
                self.assertFalse(result['measured_source']['equal'])
                for pair in result['pairs']:
                    self.assertTrue(all(value is None for value in pair['decision_quality_a'].values()))
                    self.assertTrue(all(value is None for value in pair['decision_quality_b'].values()))
                for series in result['series']:
                    for game in series['games']:
                        self.assertIsNone(game['quality'])
                        self.assertIs(game.get('quality_available'), False)
                        self.assertEqual(game.get('quality_unavailable_reason'), 'source_unavailable')

    def test_equal_source_preserves_existing_quality_schema_and_availability(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = self.route(temporary)
            self.assertTrue(result['complete'])
            self.assertTrue(result['measured_source']['equal'])
            for series in result['series']:
                for game in series['games']:
                    self.assertIsInstance(game['quality'], dict)
                    self.assertTrue(any(flag for seat in game['quality']['availability'].values() for flag in seat.values()))
                    self.assertNotIn('quality_available', game)
                    self.assertNotIn('quality_unavailable_reason', game)
