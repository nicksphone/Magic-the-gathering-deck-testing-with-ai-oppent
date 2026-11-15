"""Explicit optional CPU-Torch learning/parity controls; not default pytest collection."""
try:
    from . import _bootstrap  # noqa: F401
except ImportError:
    import _bootstrap  # noqa: F401

from copy import deepcopy
import importlib
import importlib.util
import unittest

from tests.test_learned_qv import contract, number, subject, tree


class TorchLearningTests(unittest.TestCase):
    def trainer(self):
        self.assertIsNotNone(importlib.util.find_spec('scripts.train_qv'),
                             'Missing offline Torch trainer')
        return importlib.import_module('scripts.train_qv')

    def test_actual_gradient_learning_changes_weights_and_fits_nonlinear_targets(self):
        subject(self)
        trainer = self.trainer()
        # Explicit numeric XOR protocol, not fabricated canonical game outcomes.
        samples = [{'state': number(x), 'action': number(y),
                    'return': 1.0 if x != y else -1.0}
                   for x in (-1, 1) for y in (-1, 1)]
        payload, report = trainer.train_samples(samples, contract=contract(),
            dataset_sha256='b' * 64, split_sha256='c' * 64,
            seed=31, epochs=180, learning_rate=0.025, seconds=60)
        self.assertGreater(report['updates'], 0)
        self.assertTrue(report['weights_changed'])
        self.assertLess(report['final_q_mse'], report['initial_q_mse'] * 0.25)
        self.assertEqual(payload['provenance']['updates'], report['updates'])

    def test_export_matches_torch_for_typed_ordered_sets_and_reference_gathers(self):
        m = subject(self)
        trainer = self.trainer()
        model = trainer.torch_model(seed=7)
        state = {'version': 'mtg.features.v1', 'entities': [
            {'kind': 'map', 'items': [[{'kind': 'text', 'value': 'power'},
                                     {'kind': 'number', 'value': 2}]]}],
            'root': {'kind': 'list', 'items': [{'kind': 'ref', 'index': 0},
                                             {'kind': 'bool', 'value': True}]}}
        action = tree({'kind': 'set', 'items': [{'kind': 'text', 'value': 'a'},
                                               {'kind': 'number', 'value': 3}]})
        payload = m.checkpoint(trainer.export_weights(model), contract(), {
            'dataset_sha256': 'b' * 64, 'split_sha256': 'c' * 64,
            'trainer_sha256': 'e' * 64, 'torch_version': '0+protocol',
            'trainer_seed': 7, 'updates': 0, 'samples': 0})
        policy = m.QVPolicy(payload, expected=contract())
        actual = policy.predict(state, action)
        q, v = model(state, action)
        self.assertAlmostEqual(actual['q'], q.item(), places=9)
        self.assertAlmostEqual(actual['v'], v.item(), places=9)
        reverse = deepcopy(action)
        reverse['root']['items'].reverse()
        self.assertAlmostEqual(policy.predict(state, reverse)['q'], actual['q'], places=12)
        repeated = deepcopy(action)
        repeated['root']['items'].append(deepcopy(action['root']['items'][0]))
        self.assertNotEqual(policy.predict(state, repeated)['q'], actual['q'])
        ordered = deepcopy(state)
        ordered['root']['items'].reverse()
        self.assertNotEqual(policy.predict(ordered, action)['q'], actual['q'])
        renumbered = deepcopy(state)
        renumbered['entities'].insert(0, {'kind': 'null'})
        renumbered['root']['items'][0]['index'] = 1
        self.assertEqual(policy.predict(renumbered, action), actual)
        forward = tree({'kind': 'text', 'value': 'ab'})
        backward = tree({'kind': 'text', 'value': 'ba'})
        self.assertNotEqual(policy.predict(forward, action)['q'], policy.predict(backward, action)['q'])

    def test_actual_value_head_learns_actor_relative_numeric_returns(self):
        subject(self)
        trainer = self.trainer()
        samples = [{'state': number(x), 'action': number(0), 'return': float(x)} for x in (-1, 1)]
        payload, report = trainer.train_samples(samples, contract=contract(),
            dataset_sha256='b' * 64, split_sha256='c' * 64,
            seed=19, epochs=100, learning_rate=0.025, seconds=60)
        policy = subject(self).QVPolicy(payload, expected=contract())
        self.assertLess(policy.predict(number(-1), number(0))['v'], -0.5)
        self.assertGreater(policy.predict(number(1), number(0))['v'], 0.5)
        self.assertTrue(report['weights_changed'])

    def test_preferences_learn_context_sensitive_rankings_and_export_parity(self):
        from scripts.train_qv_preferences import train_preferences

        # Synthetic numeric rankings, not expert labels or game-quality evidence.
        rows = [dict(state=number(x), preferred=number(x),
                     alternatives=[number(-x)], **{'return': float(x)})
                for x in (1, -1)]
        before = deepcopy(rows)
        payload, report = train_preferences(rows, contract=contract(),
            dataset_sha256='b' * 64, split_sha256='c' * 64,
            seed=17, epochs=150, learning_rate=.001, seconds=60)
        self.assertEqual(rows, before)
        self.assertEqual(report['updates'], 300)
        self.assertTrue(report['weights_changed'])
        self.assertEqual(report['final']['strict_top1'], 1)
        self.assertLess(report['final']['preference_loss'],
                        report['initial']['preference_loss'] * .1)
        self.assertEqual(report['final']['parity_actions'], 4)
        self.assertLessEqual(report['final']['max_parity_error'], 1e-9)
        policy = subject(self).QVPolicy(payload, expected=contract())
        for row in rows:
            preferred = policy.predict(row['state'], row['preferred'])['q']
            alternative = policy.predict(row['state'], row['alternatives'][0])['q']
            self.assertGreater(preferred, alternative)


if __name__ == '__main__':
    unittest.main()
