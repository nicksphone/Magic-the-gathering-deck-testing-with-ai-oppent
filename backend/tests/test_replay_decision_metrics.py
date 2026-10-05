"""Private timing observations must not become nondeterministic game state."""
import json
from pathlib import Path

import pytest

from scripts import regression_matrix_replay as replay
from tests.test_replay_progress import mock_runner


def canonical_land_deck():
    raw = json.loads((Path(__file__).parent / 'fixtures/nested_mana_life/snow-covered-swamp.json').read_text())
    return [{'quantity': 60, 'card_name': raw['name'], 'mana_cost': raw['mana_cost'],
             'type_line': raw['type_line'], 'oracle_text': raw['oracle_text']}]


@pytest.mark.parametrize('starting_player', [1, 2])
def test_actual_game_timing_observations_preserve_exact_replay_result(starting_player):
    deck = canonical_land_deck()
    original = replay.run_game(deck, deck, 73, 'master', 24, starting_player=starting_player)
    records = []
    measured = replay.run_game(deck, deck, 73, 'master', 24, starting_player=starting_player, observer=records.append)
    assert measured == original
    assert len(records) == 24 * 6
    assert {row['stage'] for row in records} == {'legal_moves', 'choose_action', 'apply_action'}
    assert all(row['duration_seconds'] >= 0 for row in records if row['status'] == 'completed')
    assert records[0]['pid'] == starting_player and records[0]['status'] == 'started'
    assert records[-1]['tick'] == 24 and records[-1]['stage'] == 'apply_action'
    assert all('duration_seconds' not in line for line in measured['log'])


def test_stage_failure_is_recorded_and_propagated(monkeypatch):
    records = []
    clock = iter([10.0, 12.0])
    monkeypatch.setattr(replay.time, 'perf_counter', lambda: next(clock))
    def operation():
        raise ValueError('observed failure')
    with pytest.raises(ValueError, match='observed failure'):
        replay._timed_stage(records.append, {'tick': 9}, 'choose_action', operation)
    assert records == [{'tick': 9, 'stage': 'choose_action', 'status': 'started'},
                       {'tick': 9, 'stage': 'choose_action', 'status': 'failed', 'duration_seconds': 2.0}]


def test_series_observer_preserves_game_identity(monkeypatch):
    def game(*args, **kwargs):
        kwargs['observer']({'game_seed': args[2]})
        return {'winner': 1, 'turn': 3, 'log_hash': 'fixture', 'log': [], 'timeout': False}
    monkeypatch.setattr(replay, 'run_game', game)
    records = []
    result = replay.run_match([], [], 22, 'master', 100, 3, observer=records.append)
    assert records == [{'game_seed': 22, 'game_index': 1}, {'game_seed': 23, 'game_index': 2}]
    assert result['games_played'] == 2 and 'duration_seconds' not in result


def test_cli_metric_runs_remain_distinct_from_samples(tmp_path, monkeypatch):
    output = mock_runner(monkeypatch, tmp_path, progress=False)
    original = replay.run_match
    def match(*args, observer):
        observer({'event': 'decision_stage', 'stage': 'choose_action', 'tick': 1, 'status': 'completed', 'duration_seconds': 1.5})
        return original(*args)
    monkeypatch.setattr(replay, 'run_match', match)
    metrics = tmp_path / 'timing.jsonl'
    monkeypatch.setattr('sys.argv', ['replay', '--matches-per-pair', '1', '--output', str(output), '--decision-metrics', str(metrics)])
    replay.main()
    rows = [json.loads(line) for line in metrics.read_text().splitlines()]
    assert rows[0]['event'] == 'decision_metrics_manifest'
    assert [(row['deck_a_seat'], row['repeatability_run']) for row in rows[1:]] == [(1, 1), (1, 2), (2, 1), (2, 2)]
    assert json.loads(output.read_text())['matches'] == 2
    assert json.loads(output.read_text())['determinism_failures'] == 0


@pytest.mark.parametrize('collision', ['trace', 'summary', 'progress', 'input'])
def test_metrics_path_collisions_reject_before_creating_files(tmp_path, monkeypatch, collision):
    output = mock_runner(monkeypatch, tmp_path)
    path = tmp_path / ('matrix.json' if collision == 'summary' else 'matrix.json.progress.json' if collision == 'progress' else 'diagnostic.json')
    args = ['replay', '--output', str(output), '--decision-metrics', str(path)]
    if collision == 'trace':
        args += ['--trace-output', str(path)]
    if collision == 'input':
        args += ['--deck-manifest', str(path)]
    monkeypatch.setattr('sys.argv', args)
    with pytest.raises(SystemExit):
        replay.main()
    assert not path.exists()


def test_existing_metrics_file_is_preserved(tmp_path, monkeypatch):
    mock_runner(monkeypatch, tmp_path)
    path = tmp_path / 'existing.jsonl'
    path.write_text('existing evidence')
    monkeypatch.setattr('sys.argv', ['replay', '--decision-metrics', str(path)])
    with pytest.raises(SystemExit):
        replay.main()
    assert path.read_text() == 'existing evidence'
