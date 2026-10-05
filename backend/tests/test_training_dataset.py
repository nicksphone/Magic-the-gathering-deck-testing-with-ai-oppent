"""DB-free dataset gates over the actual adapter and canonical existing cards."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from rules_engine.action_validation import ActionRejected
from tests.test_training_environment import env, position, cast
from training.dataset import (DatasetRun, EpisodeAliases, HeuristicTeacher, VERSION,
    canonical, digest, episode_groups, episode_records, grouped_split, grouped_split_report, model_input,
    validate_episode)


def records(environment, teacher=lambda environment: {'type': 'keep_hand'}, **kwargs):
    return episode_records(environment, teacher, episode='episode-0000', groups=['position:' + digest('test')],
                           tick_budget=kwargs.pop('tick_budget', 3), **kwargs)


def manifest():
    return {'configuration_hash': digest('config'), 'engine_hash': digest('engine'),
            'deck_hashes': [digest('a'), digest('b')], 'policy_hash': digest('script'),
            'origin': 'unverified'}


@pytest.mark.parametrize('seat', [1, 2])
def test_hidden_identity_order_seed_and_opposing_list_permutation_byte_input_equality(seat):
    environment = env()
    environment.step({'type': 'keep_hand'})
    environment.step({'type': 'keep_hand'})
    environment._state.priority_player = seat  # Trusted tactical test setup only.
    observation = environment.observe(seat)
    before = canonical(EpisodeAliases().observation(observation))
    state = environment._state
    for ids in (state.players[3-seat].hand, state.players[1].library, state.players[2].library):
        a, b = ids[:2]
        one, two = deepcopy(state.cards[a]), deepcopy(state.cards[b])
        one.id, two.id = b, a
        state.cards[a], state.cards[b] = two, one
        ids.reverse()
    state.starting_decks[3-seat] = deepcopy(state.starting_decks[seat])
    state.rng.random()
    state.log.append('PRIVATE future opponent identity must never be exported')
    assert canonical(EpisodeAliases().observation(environment.observe(seat))) == before
    assert not {'seed', 'snapshot', 'rng_state', 'starting_decks', 'provenance'} & observation.keys()


def test_aliases_are_independent_of_internal_deck_ids_and_round_trip_full_atomic_action():
    environment, cid = position(1)
    observed = environment.observe(1)
    aliases = EpisodeAliases()
    public = aliases.observation(observed)
    action = environment.lookup(cast(environment, cid, target_player=2))['action']
    mapped = aliases.action(action, 1)
    assert mapped['card_id'].startswith('card:')
    assert aliases.actual_action(mapped, 1) == action
    assert 'p1-' not in canonical(public) and 'p2-' not in canonical(public)
    renamed = deepcopy(observed)
    mapping = {key: 'arbitrary-object-' + str(index) for index, key in enumerate(observed['known_cards'])}
    renamed = aliases._replace(renamed, mapping)
    assert canonical(EpisodeAliases().observation(renamed)) == canonical(public)
    with pytest.raises(ActionRejected):
        aliases.action({'type': 'play_land', 'card_id': 'p1-999'}, 1)


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_canonical_bolt_complete_episode_terminal_rewards_and_no_next_input(seat):
    environment, cid = position(seat)
    environment._state.players[3-seat].life = 3
    # Canonical existing instance; no card/Oracle definition is invented.
    card = environment._state.cards[cid]
    assert card.name == 'Lightning Bolt' and '3 damage' in card.oracle_text
    first = cast(environment, cid, target_player=3-seat)
    actions = iter([first, {'type': 'pass_priority'}, {'type': 'pass_priority'}])
    rows = list(records(environment, lambda environment: next(actions), origin='scripted'))
    end = rows[-1]
    assert end['complete'] and end['reason'] == 'terminal' and end['steps'] == 3
    assert end['terminal_rewards'] == {str(seat): 1, str(3-seat): -1}
    for row in rows[1:-1]:
        assert row['accepted'] is True
        assert model_input(row)['winner'] is None
        assert not {'next_observation', 'terminal_rewards', 'seed', 'snapshot'} & row.keys()
        assert 'p1-' not in row['action_id'] and 'p2-' not in row['action_id']


@pytest.mark.parametrize('reason', ['tick_budget', 'cancelled', 'interrupted', 'rejected_action', 'teacher_or_engine_error'])
def test_nonterminal_episode_never_gets_a_terminal_draw_label(reason):
    environment = env()
    def teacher(environment):
        if reason == 'interrupted':
            raise KeyboardInterrupt()
        if reason == 'teacher_or_engine_error':
            raise RuntimeError('PRIVATE failure with raw seed/opponent state')
        if reason == 'rejected_action':
            return {'type': 'not_an_actual_action'}
        return {'type': 'keep_hand'}
    rows = list(records(environment, teacher, tick_budget=1,
                        cancelled=lambda: reason == 'cancelled'))
    assert rows[-1]['reason'] == reason
    assert rows[-1]['complete'] is False and rows[-1]['terminal_rewards'] is None
    assert 'PRIVATE' not in canonical(rows)
    if reason == 'rejected_action':
        assert len(rows) == 2


def test_current_heuristic_teacher_is_not_expert_and_untrusted_origin_cannot_be_upgraded():
    environment = env()
    teacher = HeuristicTeacher()
    assert teacher.provenance(environment)['origin'] == 'heuristic'
    assert 'seed' not in teacher.provenance(environment)
    rows = list(records(environment, teacher, tick_budget=2, origin='heuristic'))
    assert rows[0]['origin'] == 'heuristic' and rows[-1]['steps'] == 2
    for origin in ('expert', 'heuristic'):
        with pytest.raises(ValueError):
            list(records(env(), lambda env: {'type': 'not_an_action'}, origin=origin))
    bad = manifest() | {'origin': 'expert'}
    with pytest.raises(ValueError):
        DatasetRun(Path('/not-created'), bad)


def test_model_features_cannot_include_future_reward_or_provenance():
    row = list(records(env(), tick_budget=1))[1]
    features = model_input(row)
    row['terminal_rewards'] = {'1': -1, '2': 1}
    row['next_observation'] = {'PRIVATE': 'future'}
    row['engine_hash'] = 'changed'
    assert model_input(row) == features
    for field in ('seed', 'snapshot', 'next_observation', 'provenance'):
        corrupted = deepcopy(row)
        corrupted['input'][field] = 'PRIVATE'
        with pytest.raises(ValueError):
            model_input(corrupted)


def test_grouped_splits_keep_seed_family_deck_position_and_episode_duplicates_together():
    items = [
        {'episode': 'a', 'groups': episode_groups(1, ['red'], ['one', 'two'])},
        {'episode': 'b', 'groups': episode_groups(2, ['red'], ['three', 'four'])},
        {'episode': 'c', 'groups': episode_groups(1, ['blue'], ['five', 'six'])},
        {'episode': 'd', 'groups': episode_groups(3, ['green'], ['five', 'seven'])},
        {'episode': 'e', 'groups': episode_groups(4, ['other'], ['eight', 'nine'], position_group='same')},
        {'episode': 'f', 'groups': episode_groups(5, ['else'], ['ten', 'eleven'], position_group='same')},
        {'episode': 'a', 'groups': ['independent-token']},
    ]
    split = grouped_split(items, eval_fraction=.5)
    lookup = {episode: part for part, episodes in split.items() for episode in episodes}
    assert lookup['a'] == lookup['b'] == lookup['c'] == lookup['d']
    assert lookup['e'] == lookup['f']
    assert not set(split['train']) & set(split['eval'])
    assert grouped_split(list(reversed(items)), eval_fraction=.5) == split
    with pytest.raises(ValueError):
        grouped_split([{'episode': 'unknown'}])


def test_stream_deterministic_bytes_and_verified_episode_boundary_resume(tmp_path):
    for name in ('one', 'two'):
        run = DatasetRun(tmp_path / name, manifest())
        run.write_episode(records(env(), tick_budget=2))
        run.close()
    assert (tmp_path / 'one/episode-0000.jsonl').read_bytes() == (tmp_path / 'two/episode-0000.jsonl').read_bytes()
    before = {p.name: p.read_bytes() for p in (tmp_path / 'one').iterdir()}
    run = DatasetRun(tmp_path / 'one', manifest(), resume=True)
    assert len(run.completed) == 1
    run.close()
    assert {p.name: p.read_bytes() for p in (tmp_path / 'one').iterdir()} == before


@pytest.mark.parametrize('corruption', ['partial', 'changed', 'extra', 'pending', 'symlink'])
def test_malformed_resume_refuses_without_overwriting_or_truncating_user_files(tmp_path, corruption):
    root = tmp_path / 'run'
    run = DatasetRun(root, manifest())
    run.write_episode(records(env(), tick_budget=1))
    run.close()
    shard = root / 'episode-0000.jsonl'
    if corruption == 'partial':
        shard.write_bytes(shard.read_bytes()[:-1])
    elif corruption == 'changed':
        shard.write_bytes(shard.read_bytes().replace(b'"life":20', b'"life":19', 1))
    elif corruption == 'extra':
        (root / 'user-notes.txt').write_text('KEEP ME')
    elif corruption == 'pending':
        (root / '.pending-0001.jsonl').write_text('INTERRUPTED, NOT A DRAW')
    else:
        shard.rename(tmp_path / 'foreign.jsonl')
        shard.symlink_to(tmp_path / 'foreign.jsonl')
    before = {p.name: p.read_bytes() for p in root.iterdir()}
    with pytest.raises((ValueError, KeyError)):
        DatasetRun(root, manifest(), resume=True)
    assert {p.name: p.read_bytes() for p in root.iterdir()} == before
    with pytest.raises(FileExistsError):
        DatasetRun(root, manifest())


def test_output_bytes_bounded_and_incomplete_explicit(tmp_path):
    run = DatasetRun(tmp_path / 'limited', manifest(), max_bytes=4096)
    end = run.write_episode(records(env(), tick_budget=1))
    run.close()
    assert end['reason'] == 'output_budget' and end['terminal_rewards'] is None
    assert sum(p.stat().st_size for p in (tmp_path / 'limited').iterdir()) <= 4096
    validate_episode(tmp_path / 'limited/episode-0000.jsonl', 'episode-0000')


def test_no_database_or_network_needed(monkeypatch, tmp_path):
    import sqlite3
    import socket
    def forbidden(*args, **kwargs):
        raise AssertionError('No database or network allowed')
    monkeypatch.setattr(sqlite3, 'connect', forbidden)
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    environment = env()
    teacher = HeuristicTeacher()
    run = DatasetRun(tmp_path / 'offline',
                     {'configuration_hash': digest('offline'), **teacher.provenance(environment)})
    run.write_episode(records(environment, teacher, tick_budget=2, origin='heuristic'))
    run.close()


def test_cli_small_seeded_run_and_resume_no_overwrite(tmp_path):
    script = Path(__file__).resolve().parents[1] / 'scripts/export_training_trajectories.py'
    args = [sys.executable, str(script), '--out', str(tmp_path / 'cli'),
            '--ci-temp', str(tmp_path), '--seeds', '17', '18', '--ticks', '3']
    first = subprocess.run(args, capture_output=True, text=True, timeout=90)
    assert first.returncode == 0, first.stderr
    report = json.loads(first.stdout.splitlines()[-1])
    assert report['status'] == 'NOT evaluation-ready' and not report['partition_ready']
    metadata = json.loads((tmp_path / 'cli/manifest.json').read_text())
    assert metadata['teacher_config']['mode'] == 'baseline_generic'
    assert metadata['teacher_config']['archetype'] == 'Midrange'
    assert metadata['teacher_config']['opponent_archetype'] is None
    shards = sorted((tmp_path / 'cli').glob('episode-*.jsonl'))
    assert len(shards) == 2
    before = [path.read_bytes() for path in shards]
    again = subprocess.run(args + ['--resume'], capture_output=True, text=True, timeout=90)
    assert again.returncode == 0, again.stderr
    assert [path.read_bytes() for path in shards] == before
    refused = subprocess.run(args, capture_output=True, text=True, timeout=90)
    assert refused.returncode != 0
    assert [path.read_bytes() for path in shards] == before


def test_manifest_cannot_smuggle_seed_snapshot_opposing_list_or_expert_origin(tmp_path):
    for key in ('seed', 'snapshot', 'opposing_deck_list', 'expert'):
        with pytest.raises(ValueError):
            DatasetRun(tmp_path / key, manifest() | {key: 'PRIVATE'})
        assert not (tmp_path / key).exists()


def test_unknown_rejected_action_shard_remains_unverified_not_expert(tmp_path):
    run = DatasetRun(tmp_path / 'unknown', manifest())
    end = run.write_episode(records(env(), lambda env: {'type': 'unmodeled_choice'}))
    run.close()
    assert end['reason'] == 'rejected_action' and end['steps'] == 0
    assert end['terminal_rewards'] is None
    text = (tmp_path / 'unknown/episode-0000.jsonl').read_text()
    assert 'unmodeled_choice' not in text and '"origin":"unverified"' in text


def test_incomplete_actions_are_not_completed_by_dataset_exporter():
    environment, cid = position(1)
    before = environment.snapshot()
    rows = list(records(environment, lambda env: {'type': 'cast_spell', 'card_id': cid,
                                                  'targets': {'target_player': 2}}))
    assert rows[-1]['reason'] == 'rejected_action' and rows[-1]['steps'] == 0
    assert environment.snapshot() == before


def test_full_ordered_atomic_action_mapping_preserves_all_selections():
    environment = env()
    aliases = EpisodeAliases()
    aliases.observation(environment.observe(1))
    hand = environment.observe(1)['players']['1']['hand']
    action = {'type': 'choose_mechanic', 'card_ids': hand[:3]}
    mapped = aliases.action(action, 1)
    assert mapped['card_ids'] != action['card_ids']
    assert aliases.actual_action(mapped, 1) == action


@pytest.mark.parametrize('during_lookup', [False, True])
def test_cancellation_during_teacher_or_lookup_does_not_commit_an_extra_action(during_lookup):
    environment = env()
    before = environment.snapshot()
    cancelled = False
    def teacher(environment):
        nonlocal cancelled
        cancelled = not during_lookup
        return {'type': 'keep_hand'}
    if during_lookup:
        lookup = environment.lookup
        def cancelling_lookup(*args, **kwargs):
            nonlocal cancelled
            result = lookup(*args, **kwargs)
            cancelled = True
            return result
        environment.lookup = cancelling_lookup
    rows = list(records(environment, teacher, cancelled=lambda: cancelled))
    assert rows[-1]['reason'] == 'cancelled' and rows[-1]['steps'] == 0
    assert environment.snapshot() == before


def test_raw_private_group_data_and_heuristic_origin_downgrade_are_rejected():
    with pytest.raises(ValueError):
        list(episode_records(env(), lambda env: {'type': 'keep_hand'}, episode='episode-0000',
                             groups=['seed:17'], tick_budget=1))
    with pytest.raises(ValueError):
        list(records(env(), HeuristicTeacher(), origin='scripted', tick_budget=1))


@pytest.mark.parametrize('relative', ['knowledge/mechanic_metadata.py', 'scripts/export_training_trajectories.py',
                                    'training/dataset.py'])
def test_policy_hash_covers_composed_metadata_runner_and_teacher_without_editing_them(monkeypatch, relative):
    before = HeuristicTeacher().policy_hash
    target = Path(__file__).resolve().parents[1] / relative
    read_bytes = Path.read_bytes
    def changed_bytes(path):
        value = read_bytes(path)
        return value + b'\n# synthetic hash dependency probe\n' if path == target else value
    monkeypatch.setattr(Path, 'read_bytes', changed_bytes)
    assert HeuristicTeacher().policy_hash != before


@pytest.mark.parametrize('difficulty', ['strong', 'master'])
def test_teacher_provenance_matches_explicit_generic_agents_and_is_not_model_input(difficulty):
    teacher = HeuristicTeacher(difficulty)
    metadata = teacher.provenance(env())
    assert metadata['teacher_config'] == {
        'implementation': 'AIAgent', 'mode': 'baseline_generic',
        'difficulty': difficulty, 'archetype': 'Midrange',
        'opponent_archetype': None, 'deck_identity_analysis': False}
    assert all(agent.archetype == 'Midrange' and agent.opponent_archetype is None
               and agent.difficulty == difficulty for agent in teacher.agents.values())
    assert HeuristicTeacher('strong').policy_hash != HeuristicTeacher('master').policy_hash
    row = list(records(env(), tick_budget=1))[1]
    row.update(metadata)
    assert 'teacher_config' not in model_input(row)
    metadata['teacher_config']['archetype'] = 'Aggro'
    assert teacher.provenance(env())['teacher_config']['archetype'] == 'Midrange'


@pytest.mark.parametrize('config', [None, {'mode': 'expert'},
    {'implementation': 'AIAgent', 'mode': 'baseline_generic', 'difficulty': 'strong',
     'archetype': 'Midrange', 'opponent_archetype': 'Control', 'deck_identity_analysis': False}])
def test_heuristic_manifest_requires_accurate_bounded_config_without_opponent_facts(tmp_path, config):
    metadata = HeuristicTeacher().provenance(env())
    metadata['configuration_hash'] = digest('config')
    if config is None:
        del metadata['teacher_config']
    else:
        metadata['teacher_config'] = config
    with pytest.raises(ValueError):
        DatasetRun(tmp_path / 'refused', metadata)
    assert not (tmp_path / 'refused').exists()


@pytest.mark.parametrize('eval_fraction,reason', [(0, 'empty_heldout_split'), (1, 'empty_training_split')])
def test_round_robin_component_is_explicitly_not_evaluation_ready(eval_fraction, reason):
    items = [
        {'episode': 'red-blue', 'groups': episode_groups(1, ['red', 'blue'], ['r', 'b'])},
        {'episode': 'blue-green', 'groups': episode_groups(2, ['blue', 'green'], ['b', 'g'])},
        {'episode': 'green-red', 'groups': episode_groups(3, ['green', 'red'], ['g', 'r'])},
    ]
    report = grouped_split_report(items, eval_fraction=eval_fraction)
    assert not report['partition_ready'] and report['status'] == 'NOT evaluation-ready'
    assert reason in report['reasons']
    assert len(report['train']) + len(report['eval']) == 3


def test_nonempty_partitions_do_not_claim_policy_qualification():
    items = [{'episode': str(i), 'groups': ['independent:' + digest(i)]} for i in range(40)]
    report = grouped_split_report(items, eval_fraction=.5)
    assert report['train'] and report['eval'] and report['partition_ready']
    assert report['status'] == 'partitions_available' and not report['reasons']
    assert 'evaluation_ready' not in report
