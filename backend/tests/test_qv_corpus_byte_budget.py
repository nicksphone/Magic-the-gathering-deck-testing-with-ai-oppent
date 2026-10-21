"""Explicit aggregate-cap protocols; native fixture facts are never resized."""
from contextlib import contextmanager, redirect_stdout
import inspect
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import train_qv
from tests import test_qv_multirun_corpus as fixtures


MIB = 1024 * 1024


class CorpusByteBudgetTests(unittest.TestCase):
    def capability(self):
        for function in (train_qv.collect_corpus, train_qv.load_samples):
            self.assertIn('max_corpus_bytes', inspect.signature(function).parameters,
                          'Missing explicit bounded aggregate capacity admission')

    def runs(self, directory):
        fixture = fixtures.CorpusTests(
            'test_two_real_disjoint_runs_load_with_full_groups_and_terminal_labels')
        return fixture, *fixture.setup_runs(directory)

    @contextmanager
    def charged_sizes(self):
        # Only byte accounting is synthetic; every returned episode is validated
        # by the real original reader. This is not a large-game qualification.
        original = train_qv._read_run

        def read(root, engine):
            identity, episodes, contract, _actual_bytes = original(root, engine)
            return identity, episodes, contract, 26 * MIB

        with patch.object(train_qv, '_read_run', side_effect=read):
            yield

    def test_default_aggregate_limit_still_rejects_more_than_fifty_mib(self):
        with tempfile.TemporaryDirectory() as directory:
            _, roots, engine = self.runs(directory)
            with self.charged_sizes(), self.assertRaisesRegex(ValueError, 'Aggregate'):
                train_qv.collect_corpus(roots, expected_engine_hash=engine)

    def test_explicit_hundred_mib_admits_same_validated_runs_without_rewriting(self):
        self.capability()
        with tempfile.TemporaryDirectory() as directory:
            _, roots, engine = self.runs(directory)
            before = [fixtures.files(root) for root in roots]
            expected = train_qv.collect_corpus(roots, expected_engine_hash=engine)
            with self.charged_sizes():
                actual = train_qv.collect_corpus(roots, expected_engine_hash=engine,
                                               max_corpus_bytes=100 * MIB)
            self.assertEqual(actual, expected)
            self.assertEqual(before, [fixtures.files(root) for root in roots])
            self.assertTrue(all(row['end']['complete'] for row in actual['episodes']))

    def test_explicit_limit_is_inclusive_but_one_byte_less_rejects(self):
        self.capability()
        with tempfile.TemporaryDirectory() as directory:
            _, roots, engine = self.runs(directory)
            with self.charged_sizes():
                corpus = train_qv.collect_corpus(roots, expected_engine_hash=engine,
                                               max_corpus_bytes=52 * MIB)
                self.assertEqual(len(corpus['episodes']), 2)
                with self.assertRaisesRegex(ValueError, 'Aggregate'):
                    train_qv.collect_corpus(roots, expected_engine_hash=engine,
                                           max_corpus_bytes=52 * MIB - 1)

    def test_invalid_scalar_types_and_out_of_bounds_fail_before_any_run_read(self):
        self.capability()
        for value in (None, True, False, 100.0 * MIB, '104857600', 0, 4095,
                      100 * MIB + 1, 2**80):
            with self.subTest(value=value), patch.object(train_qv, '_read_run') as reader:
                with self.assertRaises(ValueError):
                    train_qv.collect_corpus([Path('never-opened')],
                        expected_engine_hash='a' * 64, max_corpus_bytes=value)
                reader.assert_not_called()

    def test_larger_aggregate_does_not_admit_a_larger_per_run_manifest(self):
        self.capability()
        with tempfile.TemporaryDirectory() as directory:
            _, roots, engine = self.runs(directory)
            path = roots[0] / 'manifest.json'
            manifest = json.loads(path.read_bytes())
            manifest['max_bytes'] = 100 * MIB
            path.write_text(json.dumps(manifest) + '\n')
            before = [fixtures.files(root) for root in roots]
            with self.assertRaises(ValueError):
                train_qv.collect_corpus(roots, expected_engine_hash=engine,
                                       max_corpus_bytes=100 * MIB)
            self.assertEqual(before, [fixtures.files(root) for root in roots])

    def test_load_samples_forwards_capacity_and_preserves_terminal_targets(self):
        self.capability()
        with tempfile.TemporaryDirectory() as directory:
            fixture, roots, engine = self.runs(directory)
            corpus = train_qv.collect_corpus(roots, expected_engine_hash=engine)
            split = Path(directory) / 'split.json'
            fixture.selection(corpus, split)
            expected = train_qv.load_samples(roots, split, expected_engine_hash=engine)
            with self.charged_sizes():
                actual = train_qv.load_samples(roots, split, expected_engine_hash=engine,
                                              max_corpus_bytes=100 * MIB)
            self.assertEqual(actual, expected)
            self.assertTrue(all(abs(row['return']) == 1
                                for rows in actual[0].values() for row in rows))

    def test_collect_cli_forwards_capacity_without_importing_or_running_trainer(self):
        self.capability()
        with tempfile.TemporaryDirectory() as directory:
            _, roots, engine = self.runs(directory)
            output = io.StringIO()
            with self.charged_sizes(), patch.object(train_qv, 'collect_corpus',
                    wraps=train_qv.collect_corpus) as collector, patch.object(
                    train_qv, 'train_samples', side_effect=AssertionError('No fitting')) as trainer:
                with redirect_stdout(output):
                    status = train_qv.main(['--dataset', str(roots[0]), '--dataset', str(roots[1]),
                        '--engine-hash', engine, '--collect-only', '--split-out',
                        str(Path(directory) / 'split.json'), '--max-corpus-bytes', str(100 * MIB)])
            self.assertIn(status, (0, 2))
            self.assertFalse(trainer.called)
            self.assertEqual(collector.call_args.kwargs['max_corpus_bytes'], 100 * MIB)
            report = json.loads(output.getvalue())
            self.assertEqual(report['runs'], 2)
            self.assertEqual(status == 0, report['partition_ready'])

    def test_training_cli_forwards_capacity_and_only_train_rows_without_publishing(self):
        self.capability()
        with tempfile.TemporaryDirectory() as directory:
            fixture, roots, engine = self.runs(directory)
            corpus = train_qv.collect_corpus(roots, expected_engine_hash=engine)
            split = Path(directory) / 'split.json'
            fixture.selection(corpus, split)
            expected = train_qv.load_samples(roots, split, expected_engine_hash=engine)[0]['train']
            output = io.StringIO()
            with self.charged_sizes(), patch.object(train_qv, 'train_samples',
                    side_effect=RuntimeError('Deliberate protocol stop before Torch')) as trainer:
                with redirect_stdout(output):
                    status = train_qv.main(['--dataset', str(roots[0]), '--dataset', str(roots[1]),
                        '--engine-hash', engine, '--split', str(split), '--seed', '31',
                        '--out', str(Path(directory) / 'model.json'),
                        '--max-corpus-bytes', str(100 * MIB)])
            self.assertEqual(status, 2)
            self.assertEqual(trainer.call_count, 1)
            self.assertEqual(trainer.call_args.args, (expected,))
            self.assertFalse((Path(directory) / 'model.json').exists())
            self.assertEqual(json.loads(output.getvalue())['status'], 'unavailable')


if __name__ == '__main__':
    unittest.main()
