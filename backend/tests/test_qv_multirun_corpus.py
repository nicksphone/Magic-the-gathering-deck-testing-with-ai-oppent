"""Multi-run intake contracts; controlled canonical episodes, never expert data."""
from contextlib import redirect_stdout
import importlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch


ABI = '9a1a15d9d41e4585bdb69a87150367df8f6f699c7cde98c84cb6cc07e84eaa06'
_fixtures = None


def files(root):
    return {str(p.relative_to(root)): p.read_bytes()
            for p in sorted(root.rglob('*')) if p.is_file()}


def canonical_fixtures():
    """Cache real engine exports only; no trainer, fake winner, or private input."""
    global _fixtures
    if _fixtures is not None:
        return _fixtures
    from game_state.state import Step, Zone
    from tests.scheduler_fixture_position import ordinary_position
    from tests.test_training_environment import cast, keep, place
    from training import TrainingEnvironment
    from training.dataset import DatasetRun, digest, episode_groups, episode_records
    _fixtures = {}
    for label, decks, families, seed, complete, context in (
        ('burn', ('Mono Red Aggro', 'Blue Control'), ('burn', 'control'), 17, True, True),
        ('elves', ('Tribal', 'Tokens'), ('elves', 'tokens'), 29, True, True),
        ('partial', ('Mono Red Aggro', 'Blue Control'), ('burn', 'control'), 31, False, True),
        ('legacy', ('Tribal', 'Tokens'), ('elves', 'tokens'), 29, True, False),
    ):
        env = TrainingEnvironment()
        env.reset(*decks, seed=seed)
        keep(env)
        state = env._state
        state.active_player = state.priority_player = 1
        ordinary_position(state)
        state.players[2].life = 3 if label in {'burn', 'partial'} else 1
        if label in {'burn', 'partial'}:
            state.step = Step.PRECOMBAT_MAIN
            cid = place(env, 'Lightning Bolt', 1, Zone.HAND)
            place(env, 'Mountain', 1, Zone.BATTLEFIELD)
            actions = [cast(env, cid, target_player=2),
                       {'type': 'pass_priority'}, {'type': 'pass_priority'}]
        else:
            state.step = Step.DECLARE_ATTACKERS
            cid = place(env, 'Llanowar Elves', 1, Zone.BATTLEFIELD)
            state.cards[cid].summoning_sick = False
            actions = [{'type': 'attack', 'attackers': [cid],
                        'attack_targets': {cid: 'player:2'}},
                       {'type': 'pass_priority'}, {'type': 'pass_priority'},
                       {'type': 'block', 'blocks': {}},
                       {'type': 'pass_priority'}, {'type': 'pass_priority'}]
        provenance = env.snapshot()['provenance']
        metadata = {'configuration_hash': digest({'fixture': label, 'seed': seed}),
                    'engine_hash': provenance['engine_hash'],
                    'deck_hashes': provenance['deck_hashes'],
                    'policy_hash': digest('explicit native fixture actions'), 'origin': 'scripted'}
        groups = episode_groups(seed, families, provenance['deck_hashes'])
        sequence = iter(actions)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'run'
            run = DatasetRun(root, metadata, dataset_version='mtg.dataset.v2')
            try:
                run.write_episode(episode_records(env, lambda current: next(sequence),
                    episode='episode-0000', groups=groups, tick_budget=len(actions) if complete else 1,
                    origin='scripted', decision_frame=True, public_context=context))
            finally:
                run.close()
            assert env.terminated is complete
            if complete:
                assert env._state.winner == 1
            _fixtures[label] = files(root)
    return _fixtures


class CorpusTests(unittest.TestCase):
    def capability(self):
        module = importlib.import_module('scripts.train_qv')
        self.assertTrue(callable(getattr(module, 'collect_corpus', None)),
                        'Missing sealed multi-run corpus collection')
        return module

    def setup_runs(self, directory, labels=('burn', 'elves')):
        result = []
        for label in labels:
            root = Path(directory) / label
            root.mkdir()
            for name, value in canonical_fixtures()[label].items():
                (root / name).write_bytes(value)
            result.append(root)
        engine = json.loads((result[0] / 'manifest.json').read_text())['engine_hash']
        return result, engine

    def selection(self, corpus, path):
        rows = corpus['episodes']
        self.assertEqual(len(rows), 2)
        split = {'schema': 2, 'train': [rows[0]['episode']], 'eval': [rows[1]['episode']]}
        path.write_text(json.dumps(split) + '\n')
        return split

    def test_two_real_disjoint_runs_load_with_full_groups_and_terminal_labels(self):
        m = self.capability()
        with tempfile.TemporaryDirectory() as directory:
            roots, engine = self.setup_runs(directory)
            corpus = m.collect_corpus(roots, expected_engine_hash=engine)
            self.assertEqual(corpus['contract']['feature_schema_sha256'], ABI)
            self.assertEqual(corpus['contract']['decision_version'], 'mtg.decision.v2')
            self.assertEqual(corpus['contract']['feature_version'], 'mtg.features.v2')
            self.selection(corpus, Path(directory) / 'split.json')
            samples, contract, _, _ = m.load_samples(roots, Path(directory) / 'split.json', expected_engine_hash=engine)
            self.assertTrue(samples['train'] and samples['eval'])
            self.assertEqual(contract, corpus['contract'])
            for side in samples.values():
                self.assertTrue(all(row['return'] in {-1.0, 1.0} for row in side))
            self.assertFalse(set(corpus['episodes'][0]['groups']) & set(corpus['episodes'][1]['groups']))

    def test_scoped_episode_ids_keep_both_original_episode_zero_records(self):
        m = self.capability()
        with tempfile.TemporaryDirectory() as directory:
            roots, engine = self.setup_runs(directory)
            rows = m.collect_corpus(roots, expected_engine_hash=engine)['episodes']
            self.assertEqual(len({row['episode'] for row in rows}), 2)
            for row in rows:
                self.assertRegex(row['episode'], r'^[0-9a-f]{64}/episode-0000$')

    def test_root_order_and_root_location_are_not_corpus_identities(self):
        m = self.capability()
        with tempfile.TemporaryDirectory() as directory:
            roots, engine = self.setup_runs(directory)
            original = m.collect_corpus(roots, expected_engine_hash=engine)
            copied = Path(directory) / 'copied'
            shutil.copytree(roots[0], copied)
            moved = m.collect_corpus([roots[1], copied], expected_engine_hash=engine)
            self.assertEqual(original, moved)

    def test_duplicate_run_bytes_are_rejected_even_at_a_different_owned_path(self):
        m = self.capability()
        with tempfile.TemporaryDirectory() as directory:
            roots, engine = self.setup_runs(directory)
            copied = Path(directory) / 'copied'
            shutil.copytree(roots[0], copied)
            with self.assertRaises(ValueError):
                m.collect_corpus([roots[0], copied], expected_engine_hash=engine)

    def test_every_manifest_must_match_the_same_engine_epoch(self):
        m = self.capability()
        with tempfile.TemporaryDirectory() as directory:
            roots, engine = self.setup_runs(directory)
            path = roots[1] / 'manifest.json'
            value = json.loads(path.read_text())
            value['engine_hash'] = ('b' if engine[0] != 'b' else 'c') * 64
            path.write_text(json.dumps(value) + '\n')
            before = [files(root) for root in roots]
            with self.assertRaises(ValueError):
                m.collect_corpus(roots, expected_engine_hash=engine)
            self.assertEqual(before, [files(root) for root in roots])

    def test_legacy_and_context_feature_epochs_cannot_be_mixed(self):
        m = self.capability()
        with tempfile.TemporaryDirectory() as directory:
            roots, engine = self.setup_runs(directory, ('burn', 'legacy'))
            with self.assertRaises(ValueError):
                m.collect_corpus(roots, expected_engine_hash=engine)

    def test_full_real_groups_are_retained_not_replaced_by_run_hashes(self):
        m = self.capability()
        with tempfile.TemporaryDirectory() as directory:
            roots, engine = self.setup_runs(directory)
            corpus = m.collect_corpus(roots, expected_engine_hash=engine)
            actual = sorted(sorted(row['groups']) for row in corpus['episodes'])
            expected = sorted(sorted(json.loads((root / 'episode-0000.jsonl').read_text().splitlines()[0])['groups']) for root in roots)
            self.assertEqual(actual, expected)
            self.assertTrue(all(any(group.startswith('seed:') for group in row) and
                                any(group.startswith('family:') for group in row) and
                                any(group.startswith('deck:') for group in row) for row in actual))

    def test_shared_groups_across_runs_cannot_cross_train_and_eval(self):
        m = self.capability()
        a = 'a' * 64 + '/episode-0000'
        b = 'b' * 64 + '/episode-0000'
        rows = [{'episode': a, 'groups': ['seed:' + 'c' * 64], 'fingerprint': 'd' * 64},
                {'episode': b, 'groups': ['seed:' + 'c' * 64], 'fingerprint': 'e' * 64}]
        with self.assertRaises(ValueError):
            m.validate_split(rows, {'schema': 2, 'train': [a], 'eval': [b]})

    def test_native_incomplete_run_is_retained_but_never_labeled_as_draw(self):
        m = self.capability()
        with tempfile.TemporaryDirectory() as directory:
            roots, engine = self.setup_runs(directory, ('burn', 'elves', 'partial'))
            corpus = m.collect_corpus(roots, expected_engine_hash=engine)
            # Select actual matching families, not corpus list order.
            burn_groups = set(json.loads((roots[0] / 'episode-0000.jsonl').read_text().splitlines()[0])['groups'])
            train = [r['episode'] for r in corpus['episodes'] if burn_groups & set(r['groups'])]
            heldout = [r['episode'] for r in corpus['episodes'] if r['episode'] not in train]
            path = Path(directory) / 'split.json'
            path.write_text(json.dumps({'schema': 2, 'train': train, 'eval': heldout}) + '\n')
            samples, _, _, _ = m.load_samples(roots, path, expected_engine_hash=engine)
            self.assertEqual(len(samples['train']), 3)
            self.assertTrue(all(abs(r['return']) == 1 for r in samples['train']))

    def test_unknown_or_pending_run_members_are_not_silently_pruned(self):
        m = self.capability()
        with tempfile.TemporaryDirectory() as directory:
            roots, engine = self.setup_runs(directory)
            (roots[1] / '.pending-0001.jsonl').write_text('owned unfinished protocol\n')
            with self.assertRaises(ValueError):
                m.collect_corpus(roots, expected_engine_hash=engine)

    def test_expert_origin_cannot_be_manufactured_by_a_second_manifest(self):
        m = self.capability()
        with tempfile.TemporaryDirectory() as directory:
            roots, engine = self.setup_runs(directory)
            path = roots[1] / 'manifest.json'
            value = json.loads(path.read_text())
            value['origin'] = 'expert'
            path.write_text(json.dumps(value) + '\n')
            with self.assertRaises(ValueError):
                m.collect_corpus(roots, expected_engine_hash=engine)

    def test_collector_success_and_rejection_never_rewrite_any_input(self):
        m = self.capability()
        with tempfile.TemporaryDirectory() as directory:
            roots, engine = self.setup_runs(directory)
            before = [files(root) for root in roots]
            m.collect_corpus(roots, expected_engine_hash=engine)
            with self.assertRaises(ValueError):
                m.collect_corpus([*roots, roots[0]], expected_engine_hash=engine)
            self.assertEqual(before, [files(root) for root in roots])

    def test_exporter_context_is_optin_and_legacy_default_remains_v1(self):
        self.capability()
        exporter = importlib.import_module('scripts.export_training_trajectories')
        with tempfile.TemporaryDirectory() as directory:
            for name, flags, version in [('legacy', [], 'mtg.dataset.v1'),
                                         ('context', ['--decision-frame', '--public-context'], 'mtg.dataset.v2')]:
                root = Path(directory) / name
                try:
                    with redirect_stdout(io.StringIO()):
                        status = exporter.main(['--out', str(root), '--ci-temp', directory,
                                                '--seeds', '17', '--ticks', '1', *flags])
                except SystemExit as exc:
                    self.fail('Missing explicit exporter context opt-in: ' + str(exc.code))
                self.assertEqual(status, 0)
                self.assertEqual(json.loads((root / 'manifest.json').read_text())['version'], version)

    def test_collect_only_cli_never_trains_and_emits_no_game_or_card_text(self):
        m = self.capability()
        with tempfile.TemporaryDirectory() as directory:
            roots, engine = self.setup_runs(directory)
            output = io.StringIO()
            with patch.object(m, 'train_samples', side_effect=AssertionError('No fitting in collection')) as trainer:
                try:
                    with redirect_stdout(output):
                        status = m.main(['--dataset', str(roots[0]), '--dataset', str(roots[1]),
                                         '--engine-hash', engine, '--collect-only', '--split-out',
                                         str(Path(directory) / 'split.json')])
                except SystemExit as exc:
                    self.fail('Missing bounded corpus collection CLI: ' + str(exc.code))
            self.assertIn(status, (0, 2))  # Hash partition may honestly be unready.
            self.assertFalse(trainer.called)
            self.assertTrue((Path(directory) / 'split.json').is_file())
            self.assertNotIn('Lightning Bolt', output.getvalue())
            self.assertNotIn('Llanowar Elves', output.getvalue())
            report = json.loads(output.getvalue())
            self.assertEqual(report['runs'], 2)
            self.assertIs(type(report['partition_ready']), bool)
            self.assertEqual(status == 0, report['partition_ready'])

    def test_training_cli_uses_only_train_rows_then_aborts_without_checkpoint(self):
        m = self.capability()
        with tempfile.TemporaryDirectory() as directory:
            roots, engine = self.setup_runs(directory)
            corpus = m.collect_corpus(roots, expected_engine_hash=engine)
            split_path = Path(directory) / 'split.json'
            self.selection(corpus, split_path)
            expected, _, _, _ = m.load_samples(roots, split_path, expected_engine_hash=engine)
            before = [files(root) for root in roots]
            with patch.object(m, 'train_samples', side_effect=RuntimeError('PRIVATE protocol abort')) as trainer:
                output = io.StringIO()
                with redirect_stdout(output):
                    status = m.main(['--dataset', str(roots[0]), '--dataset', str(roots[1]),
                        '--split', str(split_path), '--engine-hash', engine,
                        '--out', str(Path(directory) / 'model.json'), '--seed', '31'])
            self.assertEqual(status, 2)
            self.assertEqual(trainer.call_count, 1)
            self.assertEqual(trainer.call_args.args, (expected['train'],))
            self.assertNotIn('PRIVATE', output.getvalue())
            self.assertFalse((Path(directory) / 'model.json').exists())
            self.assertEqual(before, [files(root) for root in roots])


if __name__ == '__main__':
    unittest.main()
