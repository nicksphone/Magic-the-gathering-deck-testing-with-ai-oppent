"""Checkpoint protocols and actual nonlinear learning, not game-quality claims."""
from copy import deepcopy
import importlib
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ABI = '0b3aadfead9f66999c8b6c3ddc13699ad7dc5dd1c76179e95585042ba0339ed5'


def subject(case):
    case.assertIsNotNone(importlib.util.find_spec('ai.learned_qv'),
                         'Missing safe learned Q/V implementation')
    return importlib.import_module('ai.learned_qv')


def tree(value):
    return {'version': 'mtg.features.v1', 'entities': [], 'root': value}


def number(value):
    return tree({'kind': 'number', 'value': value})


def contract():
    return {'decision_version': 'mtg.decision.v1', 'feature_version': 'mtg.features.v1',
            'feature_schema_sha256': ABI, 'dataset_version': 'mtg.dataset.v2',
            'action_version': 'mtg.action.v1:', 'engine_hash': 'a' * 64}


def blank_checkpoint(module):
    # Protocol weights only; the learning tests below never use these weights.
    weights = {key: ([[0.0] * shape[1] for _ in range(shape[0])]
                     if len(shape) == 2 else [0.0] * shape[0])
               for key, shape in module.PARAMETERS.items()}
    return module.checkpoint(weights, contract(), {
        'dataset_sha256': 'b' * 64, 'split_sha256': 'c' * 64,
        'trainer_sha256': 'e' * 64, 'torch_version': '0+protocol',
        'trainer_seed': 17, 'updates': 0, 'samples': 0,
    })


class CheckpointTests(unittest.TestCase):
    def test_prepared_decision_encodes_state_once_for_multiple_complete_actions(self):
        m = subject(self)
        policy = m.QVPolicy(blank_checkpoint(m), expected=contract())
        state, calls = number(1), []
        original = policy._encode

        def retaining(pack, cache):
            calls.append(pack is state)
            return original(pack, cache)

        policy._encode = retaining
        prepared = policy.prepare(state)
        state['root']['value'] = 99
        self.assertEqual(prepared.predict(number(-1)), {'q': 0.0, 'v': 0.0})
        self.assertEqual(prepared.predict(number(1)), {'q': 0.0, 'v': 0.0})
        self.assertEqual(calls, [True, False, False])

    def test_text_pool_has_independent_ordered_position_moments(self):
        m = subject(self)
        moments, length = m.text_moments('ab')
        self.assertEqual([row[ord('a')] for row in moments], [0.5, -0.5, 0.5])
        self.assertEqual([row[ord('b')] for row in moments], [0.5, 0.5, 0.5])
        self.assertEqual(length, 2 / 3)
        empty, length = m.text_moments('')
        self.assertEqual(empty, [[0.0] * 256 for _ in range(3)])
        self.assertEqual(length, 0.0)

    def test_text_pool_scans_each_moment_once_without_changing_arithmetic(self):
        m = subject(self)
        payload = blank_checkpoint(m)
        payload['weights']['byte.weight'] = [
            [((byte * 13 + index * 7) % 31 - 15) / 16 *
             (math.ulp(0.0) if index % 4 == 0 else 1.0) for index in range(m.WIDTH)]
            for byte in range(256)]
        policy = m.QVPolicy(payload, expected=contract())

        class CountedRow(list):
            scans = 0

            def __iter__(self):
                self.scans += 1
                return super().__iter__()

        for text in ('', 'Boros Charm', '\u00e9\u0301\U0001f525', 'burn' * 256):
            with self.subTest(text_bytes=len(text.encode('utf-8'))):
                moments, length = m.text_moments(text)
                expected = [math.fsum(coefficient * payload['weights']['byte.weight'][byte][index]
                                      for byte, coefficient in enumerate(row) if coefficient)
                            for row in moments for index in range(m.WIDTH)] + [length]
                rows = [CountedRow(row) for row in moments]
                cache = {}
                with patch.object(m, 'text_moments', return_value=(rows, length)), \
                        patch.object(policy, '_linear', wraps=policy._linear) as linear:
                    pack = tree({'kind': 'text', 'value': text})
                    encoded = policy._encode(pack, cache)
                    self.assertEqual(linear.call_args.args, ('text', expected))
                    self.assertEqual([value.hex() for value in linear.call_args.args[1]],
                                     [value.hex() for value in expected])
                    self.assertEqual([row.scans for row in rows], [1, 1, 1])
                    self.assertEqual(policy._encode(pack, cache), encoded)
                    self.assertEqual(linear.call_count, 1)

    def test_json_roundtrip_is_detached_and_inference_is_finite(self):
        m = subject(self)
        raw = blank_checkpoint(m)
        policy = m.QVPolicy(raw, expected=contract())
        raw['weights']['q_out.bias'][0] = 1.0
        self.assertEqual(policy.predict(number(1), number(-1)), {'q': 0.0, 'v': 0.0})
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'model.json'
            m.save_checkpoint(path, policy.payload())
            restored = m.load_checkpoint(path, expected=contract())
            self.assertEqual(restored.predict(number(1), number(-1)), {'q': 0.0, 'v': 0.0})
            with self.assertRaises(FileExistsError):
                m.save_checkpoint(path, policy.payload())

    def test_loader_rejects_duplicates_unknown_fields_nonfinite_and_bad_shapes(self):
        m = subject(self)
        original = blank_checkpoint(m)
        mutants = []
        for value in (True, float('nan'), float('inf'), '0'):
            row = deepcopy(original)
            row['weights']['q_out.bias'][0] = value
            mutants.append(row)
        for change in ('unknown', 'version', 'shape', 'feature', 'engine'):
            row = deepcopy(original)
            if change == 'unknown':
                row['command'] = 'not executable'
            elif change == 'version':
                row['version'] = True
            elif change == 'shape':
                row['weights']['fold.weight'].pop()
            elif change == 'feature':
                row['contract']['feature_schema_sha256'] = 'd' * 64
            else:
                row['contract']['engine_hash'] = 'd' * 64
            mutants.append(row)
        for row in mutants:
            with self.subTest(case=mutants.index(row)):
                with self.assertRaises(ValueError):
                    m.QVPolicy(row, expected=contract())
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'bad.json'
            path.write_text('{"version":1,"version":2}')
            with self.assertRaises(ValueError):
                m.load_checkpoint(path, expected=contract())
            path.write_bytes(b' ' * (m.MAX_CHECKPOINT_BYTES + 1))
            with self.assertRaises(ValueError):
                m.load_checkpoint(path, expected=contract())

    def test_checkpoint_symlink_is_not_followed(self):
        m = subject(self)
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / 'model.json'
            m.save_checkpoint(target, blank_checkpoint(m))
            link = Path(root) / 'link.json'
            link.symlink_to(target.name)
            with self.assertRaises((ValueError, OSError)):
                m.load_checkpoint(link, expected=contract())

    def test_grammar_rejects_forward_refs_unknown_nodes_and_excessive_inputs(self):
        m = subject(self)
        policy = m.QVPolicy(blank_checkpoint(m), expected=contract())
        bad = [tree({'kind': 'ref', 'index': 0}), tree({'kind': 'number', 'value': True}),
               tree({'kind': 'future', 'value': 0}), tree({'kind': 'null', 'id': 'opaque'}),
               tree({'kind': 'text', 'value': 'x' * (m.MAX_TEXT_BYTES + 1)}),
               {'version': 'mtg.features.v1', 'root': {'kind': 'null'},
                'entities': [{'kind': 'ref', 'index': 0}]}]
        for row in bad:
            with self.assertRaises(ValueError):
                policy.predict(row, number(0))


class TrainingProtocolTests(unittest.TestCase):
    def trainer(self):
        self.assertIsNotNone(importlib.util.find_spec('scripts.train_qv'))
        return importlib.import_module('scripts.train_qv')

    def test_terminal_targets_follow_actor_seat_and_incomplete_episodes_have_no_labels(self):
        subject(self)
        trainer = self.trainer()
        transitions = [{'input': {'observation': {'seat': seat}}} for seat in (1, 1, 2)]
        self.assertEqual(trainer.terminal_targets(transitions, {
            'complete': True, 'reason': 'terminal', 'terminal_rewards': {'1': 1, '2': -1}}),
            [1.0, 1.0, -1.0])
        self.assertIsNone(trainer.terminal_targets(transitions, {
            'complete': False, 'reason': 'tick_budget', 'terminal_rewards': None}))
        with self.assertRaises(ValueError):
            trainer.terminal_targets(transitions, {
                'complete': False, 'reason': 'tick_budget', 'terminal_rewards': {'1': 0, '2': 0}})

    def test_split_guards_reject_shared_groups_duplicates_and_missing_membership(self):
        subject(self)
        trainer = self.trainer()
        episodes = [{'episode': 'episode-0000', 'groups': ['seed:' + 'a' * 64], 'fingerprint': 'b' * 64},
                    {'episode': 'episode-0001', 'groups': ['seed:' + 'c' * 64], 'fingerprint': 'd' * 64}]
        split = {'schema': 1, 'train': ['episode-0000'], 'eval': ['episode-0001']}
        self.assertEqual(trainer.validate_split(episodes, split), split)
        for change in ('groups', 'fingerprint', 'missing'):
            rows, selection = deepcopy(episodes), deepcopy(split)
            if change == 'groups':
                rows[1]['groups'] = rows[0]['groups']
            elif change == 'fingerprint':
                rows[1]['fingerprint'] = rows[0]['fingerprint']
            else:
                selection['eval'] = []
            with self.assertRaises(ValueError):
                trainer.validate_split(rows, selection)


if __name__ == '__main__':
    unittest.main()
