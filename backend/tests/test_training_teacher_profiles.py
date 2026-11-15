"""Declared public-matchup teacher profiles, not hidden opponent-list features."""
from copy import deepcopy
import json

import pytest

from ai.deck_analysis import guess_archetype
from game_state.state import Zone
from scripts import export_training_trajectories as exporter
from scripts.train_qv import _read_run
from tests.test_training_environment import env, position
from training.dataset import (DatasetRun, HeuristicTeacher, baseline_teacher_config,
                              digest, episode_groups, episode_records, validate_teacher_config)
from training.environment import _deck


@pytest.mark.parametrize('difficulty', ['strong', 'master'])
def test_default_teacher_remains_exact_generic(difficulty):
    teacher = HeuristicTeacher(difficulty)
    assert teacher.config == baseline_teacher_config(difficulty)
    assert all(agent.archetype == 'Midrange' and agent.opponent_archetype is None
               for agent in teacher.agents.values())


@pytest.mark.parametrize('difficulty', ['strong', 'master'])
@pytest.mark.parametrize('reverse', [False, True])
def test_explicit_public_profiles_match_native_per_deck_configuration(difficulty, reverse):
    names = ['Burn', 'Dimir Control'][::(-1 if reverse else 1)]
    styles = {seat: guess_archetype(_deck(name)) for seat, name in enumerate(names, 1)}
    teacher = HeuristicTeacher(difficulty, archetypes=styles)
    assert styles[1] != styles[2]
    for seat, agent in teacher.agents.items():
        assert agent.archetype == styles[seat]
        assert agent.opponent_archetype == styles[3-seat]
        assert agent.difficulty == difficulty
    assert teacher.config['mode'] == 'public_matchup'
    assert teacher.config['archetypes'] == {str(seat): style for seat, style in styles.items()}
    assert teacher.config['opponent_archetypes'] == {str(seat): styles[3-seat] for seat in styles}
    assert teacher.policy_hash != HeuristicTeacher(difficulty).policy_hash
    metadata = teacher.provenance(env())
    metadata['teacher_config']['archetypes']['1'] = 'Ramp'
    assert teacher.config['archetypes']['1'] == styles[1]
    styles[1] = 'Tokens'
    assert teacher.agents[1].archetype != 'Tokens'


@pytest.mark.parametrize('styles', [{}, {1: 'Burn'}, {1: 'Burn', 2: 'unknown'},
                                    {True: 'Burn', 2: 'Control'}, ['Burn', 'Control']])
def test_public_profile_configuration_rejects_unknown_or_malformed_styles(styles):
    with pytest.raises(ValueError):
        HeuristicTeacher('strong', archetypes=styles)


def test_public_opponent_profile_requires_exact_string_seats():
    config = HeuristicTeacher('strong', archetypes={1: 'Burn', 2: 'Control'}).config
    config['opponent_archetypes'] = {1: 'Control', 2: 'Burn'}
    with pytest.raises(ValueError):
        validate_teacher_config(config)


def terminal_run(path):
    """Controlled canonical lethal Bolt, with real heuristic choices and paid resolution."""
    environment, cid = position(1)
    state = environment._state
    player = state.players[1]
    for other in list(player.hand):
        if other != cid:
            player.hand.remove(other)
            player.library.append(other)
            state.cards[other].move_to_zone(Zone.LIBRARY)
    state.players[2].life = 3
    teacher = HeuristicTeacher('strong', archetypes={1: 'Burn', 2: 'Control'})
    metadata = {**teacher.provenance(environment), 'configuration_hash': digest('public profile fixture')}
    groups = episode_groups(17, ['burn', 'control'], metadata['deck_hashes'])
    run = DatasetRun(path, metadata, dataset_version='mtg.dataset.v2')
    try:
        end = run.write_episode(episode_records(environment, teacher, episode='episode-0000',
            groups=groups, tick_budget=3, origin='heuristic', decision_frame=True, public_context=True))
    finally:
        run.close()
    assert end['complete'] is True and end['terminal_rewards'] == {'1': 1, '2': -1}
    return metadata


def test_real_terminal_public_profile_dataset_is_accepted_by_trainer(tmp_path):
    path = tmp_path / 'run'
    metadata = terminal_run(path)
    _, episodes, contract, _ = _read_run(path, metadata['engine_hash'])
    assert len(episodes) == 1 and episodes[0]['end']['complete'] is True
    assert len(episodes[0]['transitions']) == 3
    assert contract['dataset_version'] == 'mtg.dataset.v2'
    assert contract['decision_version'] == 'mtg.decision.v2'
    assert contract['engine_hash'] == metadata['engine_hash']


@pytest.mark.parametrize('change', ['opponent', 'extra', 'unknown'])
def test_trainer_rejects_altered_public_profile_provenance(tmp_path, change):
    path = tmp_path / 'run'
    metadata = terminal_run(path)
    manifest_path = path / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    config = manifest['teacher_config']
    if change == 'opponent':
        config['opponent_archetypes']['1'] = 'Ramp'
    elif change == 'extra':
        config['opponent_hand'] = ['not authorized provenance']
    else:
        config['archetypes']['1'] = 'unknown'
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        _read_run(path, metadata['engine_hash'])


@pytest.mark.parametrize('reverse', [False, True])
def test_exporter_detected_profiles_are_optin_and_recreated_per_episode(tmp_path, monkeypatch, reverse):
    names = ['Burn', 'Dimir Control'][::(-1 if reverse else 1)]
    expected = {str(seat): guess_archetype(_deck(name)) for seat, name in enumerate(names, 1)}
    seen = []

    class ObservedTeacher(HeuristicTeacher):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            seen.append(deepcopy(self.config))

    monkeypatch.setattr(exporter, 'HeuristicTeacher', ObservedTeacher)
    root = tmp_path / 'run'
    status = exporter.main(['--out', str(root), '--ci-temp', str(tmp_path),
        '--deck-a', names[0], '--deck-b', names[1], '--seeds', '17', '29', '--ticks', '1',
        '--decision-frame', '--public-context', '--deck-aware-teacher'])
    assert status == 0 and len(seen) == 3
    assert all(config['archetypes'] == expected for config in seen)
    manifest = json.loads((root / 'manifest.json').read_text())
    assert manifest['teacher_config'] == seen[0]
    assert manifest['origin'] == 'heuristic' and manifest['version'] == 'mtg.dataset.v2'
    for shard in sorted(root.glob('episode-*.jsonl')):
        rows = [json.loads(line) for line in shard.read_text().splitlines()]
        assert rows[-1]['complete'] is False and rows[-1]['terminal_rewards'] is None
        for row in rows[1:-1]:
            assert row['accepted'] is True
            assert 'teacher_config' not in row['input']
            assert not {'seed', 'rng_state', 'starting_decks', 'opp_hand'} & row['input'].keys()
