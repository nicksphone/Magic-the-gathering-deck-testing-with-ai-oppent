"""Explicit optional CPU-Torch phase protocol; not default pytest collection."""
try:
    from . import _bootstrap  # noqa: F401
except ImportError:
    import _bootstrap  # noqa: F401

from copy import deepcopy
from hashlib import sha256
import importlib.util
import inspect
import math
import os
from pathlib import Path
import stat
import sys
import unittest
from unittest.mock import patch

from scripts import train_qv
from tests.test_learned_qv import contract, number


class TorchProgressTests(unittest.TestCase):
    def reference(self):
        value = os.environ.get('QV_REFERENCE_TRAINER')
        self.assertIsNotNone(value, 'Bind the sealed original reference source explicitly')
        path = Path(value)
        self.assertEqual(path.resolve(strict=True), path.absolute())
        info = path.lstat()
        self.assertTrue(stat.S_ISREG(info.st_mode))
        self.assertEqual(info.st_nlink, 1)
        self.assertLessEqual(info.st_size, 65536)
        raw = path.read_bytes()
        self.assertEqual(sha256(raw).hexdigest(),
                         'fdfb909f0e216715e6cab00a324fad4306ef755aab6580cb3a8ca9e99c375b58')
        name = 'scripts._qv_prefusion_reference'
        self.assertNotIn(name, sys.modules)
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        self.addCleanup(sys.modules.pop, name, None)
        spec.loader.exec_module(module)
        return module

    def counted_training(self, module, samples, options):
        counts = {'torch_forwards': 0, 'stdlib_parity': 0}
        original_factory = module.torch_model
        original_predict = module.QVPolicy.predict

        def factory(*args, **kwargs):
            model = original_factory(*args, **kwargs)
            original_forward = model.forward

            def forward(*values, **named):
                result = original_forward(*values, **named)
                counts['torch_forwards'] += 1
                return result

            model.forward = forward
            return model

        def predict(policy, *args, **kwargs):
            result = original_predict(policy, *args, **kwargs)
            counts['stdlib_parity'] += 1
            return result

        with patch.object(module, 'torch_model', side_effect=factory):
            with patch.object(module.QVPolicy, 'predict', new=predict):
                result = module.train_samples(samples, **options)
        return result, counts

    def test_phase_counts_and_default_numerics_match_actual_cpu_training(self):
        self.assertIn('progress', inspect.signature(train_qv.train_samples).parameters,
                      'Missing optional training progress callback')
        # Numeric protocol only; these are not canonical games or quality labels.
        samples = [{'state': number(-1 if i % 2 else 1), 'action': number(0),
                    'return': float(-1 if i % 2 else 1)} for i in range(65)]
        original = deepcopy(samples)
        options = dict(contract=contract(), dataset_sha256='b' * 64,
                       split_sha256='c' * 64, seed=17, epochs=1,
                       learning_rate=0.01, seconds=120)
        baseline = train_qv.train_samples(samples, **options)
        events = []
        actual = train_qv.train_samples(samples, progress=events.append, **options)
        self.assertEqual(actual, baseline)
        self.assertEqual(samples, original)
        self.assertEqual(actual[1]['updates'], 65)
        phases = ('initial_mse', 'updates', 'final_mse', 'export_parity')
        self.assertEqual([row['phase'] for row in events if row['event'] == 'start'],
                         list(phases))
        self.assertEqual([row['phase'] for row in events if row['event'] == 'end'],
                         list(phases))
        for phase in phases:
            rows = [row for row in events if row['phase'] == phase]
            self.assertEqual([row['event'] for row in rows], ['start', 'progress', 'end'])
            self.assertEqual([row['processed'] for row in rows], [0, 64, 65])
            for row in rows:
                self.assertEqual(set(row), {'phase', 'event', 'processed', 'total',
                                           'updates', 'elapsed_seconds'})
                for key in ('processed', 'total', 'updates'):
                    self.assertIs(type(row[key]), int)
                self.assertEqual(row['total'], 65)
                self.assertIs(type(row['elapsed_seconds']), float)
                self.assertTrue(math.isfinite(row['elapsed_seconds']))
        # Final MSE and parity share a pass; use chronological, not grouped, time.
        elapsed = [row['elapsed_seconds'] for row in events]
        updates = [row['updates'] for row in events]
        self.assertEqual(elapsed, sorted(elapsed))
        self.assertEqual(updates, sorted(updates))

    def test_final_mse_reuses_parity_forward_with_exact_reference_weights_and_loss(self):
        reference = self.reference()
        samples = [{'state': number(-1 if i % 2 else 1), 'action': number(0),
                    'return': float(-1 if i % 2 else 1)} for i in range(65)]
        options = dict(contract=contract(), dataset_sha256='b' * 64,
                       split_sha256='c' * 64, seed=17, epochs=1,
                       learning_rate=0.01, seconds=120)
        old, old_counts = self.counted_training(reference, samples, options)
        new, new_counts = self.counted_training(train_qv, samples, options)
        self.assertEqual(old_counts, {'torch_forwards': 4 * 65, 'stdlib_parity': 65})
        self.assertEqual(new_counts, {'torch_forwards': 3 * 65, 'stdlib_parity': 65})
        self.assertEqual(new[0]['weights'], old[0]['weights'])
        self.assertEqual(new[0]['contract'], old[0]['contract'])
        self.assertEqual(new[1], old[1])
        self.assertEqual(new[1]['updates'], 65)
        for module, payload in ((reference, old[0]), (train_qv, new[0])):
            self.assertEqual(payload['provenance']['trainer_sha256'],
                             sha256(Path(module.__file__).read_bytes()).hexdigest())
        old_policy = reference.QVPolicy(old[0], expected=contract())
        new_policy = train_qv.QVPolicy(new[0], expected=contract())
        for x in (-1, 1):
            self.assertEqual(new_policy.predict(number(x), number(0)),
                             old_policy.predict(number(x), number(0)))

    def test_last_parity_comparison_still_rejects(self):
        samples = [{'state': number(-1 if i % 2 else 1), 'action': number(0),
                    'return': float(-1 if i % 2 else 1)} for i in range(65)]
        original_predict = train_qv.QVPolicy.predict
        comparisons = 0

        def predict(policy, *args, **kwargs):
            nonlocal comparisons
            result = original_predict(policy, *args, **kwargs)
            comparisons += 1
            return {**result, 'q': result['q'] + 0.001} if comparisons == 65 else result

        with patch.object(train_qv.QVPolicy, 'predict', new=predict):
            with self.assertRaisesRegex(ValueError, 'Actual trained Torch/stdlib export parity failed'):
                train_qv.train_samples(samples, contract=contract(),
                    dataset_sha256='b' * 64, split_sha256='c' * 64,
                    seed=17, epochs=1, learning_rate=0.01, seconds=120)
        self.assertEqual(comparisons, 65)

    def test_callback_failure_is_same_exception_and_restores_cpu_threads(self):
        self.assertIn('progress', inspect.signature(train_qv.train_samples).parameters,
                      'Missing optional training progress callback')
        import torch
        before_threads = torch.get_num_threads()
        error = ValueError('protocol observer stop')
        events = []

        def observing(row):
            events.append(row)
            if row['phase'] == 'final_mse' and row['event'] == 'start':
                raise error

        samples = [{'state': number(x), 'action': number(0), 'return': float(x)}
                   for x in (-1, 1)]
        with self.assertRaises(ValueError) as caught:
            train_qv.train_samples(samples, contract=contract(),
                dataset_sha256='b' * 64, split_sha256='c' * 64,
                seed=17, epochs=1, seconds=120, progress=observing)
        self.assertIs(caught.exception, error)
        self.assertEqual(torch.get_num_threads(), before_threads)
        self.assertEqual(events[-1]['phase'], 'final_mse')
        self.assertEqual(events[-1]['event'], 'start')
        self.assertEqual(events[-1]['updates'], 2)
        self.assertNotIn('export_parity', [row['phase'] for row in events])


if __name__ == '__main__':
    unittest.main()
