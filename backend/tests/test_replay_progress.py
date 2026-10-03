"""Runner progress contracts; mocked outcomes are not gameplay evidence."""
import json
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from scripts import regression_matrix_replay as replay


def summary(matches=0):
    return {'matches': matches, 'determinism_failures': 0, 'anomaly_counts': {}}


def test_progress_reports_logical_samples_not_duplicate_executions(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(replay.time, 'monotonic', lambda: 130.0)
    output = tmp_path / 'matrix.json'
    record = replay._report_progress(output, summary(2), 6, 100.0)
    assert record['completed_samples'] == 2
    assert record['repeatability_runs_per_sample'] == 2
    assert record['estimated_remaining_seconds'] == 60.0
    assert not record['resume_supported']
    assert json.loads(capsys.readouterr().out) == record
    assert json.loads((tmp_path / 'matrix.json.progress.json').read_text()) == record
    assert not list(tmp_path.glob('*.tmp'))


@pytest.mark.parametrize('total,eta', [(0, 0.0), (6, None)])
def test_initial_progress_does_not_invent_an_eta(tmp_path, total, eta):
    record = replay._report_progress(tmp_path / 'matrix.json', summary(), total, replay.time.monotonic())
    assert record['estimated_remaining_seconds'] == eta


def test_failed_atomic_replace_preserves_last_progress_and_cleans_temp(tmp_path, monkeypatch, capsys):
    output = tmp_path / 'matrix.json'
    replay._report_progress(output, summary(), 2, replay.time.monotonic())
    previous = (tmp_path / 'matrix.json.progress.json').read_bytes()
    capsys.readouterr()
    def fail(*args):
        raise OSError('fixture replace failure')
    monkeypatch.setattr(replay.Path, 'replace', fail)
    with pytest.raises(OSError):
        replay._report_progress(output, summary(1), 2, replay.time.monotonic())
    assert (tmp_path / 'matrix.json.progress.json').read_bytes() == previous
    assert not list(tmp_path.glob('*.tmp'))
    assert not capsys.readouterr().out


def mock_runner(monkeypatch, tmp_path, *, progress=True, fail=False):
    output = tmp_path / 'matrix.json'
    monkeypatch.setattr('sys.argv', ['replay', '--matches-per-pair', '1', '--output', str(output)]
                        + (['--progress'] if progress else []))
    monkeypatch.setattr(replay, 'init_db', lambda: None)
    monkeypatch.setattr(replay, 'Session', lambda _: nullcontext(None))
    monkeypatch.setattr(replay, 'Repository', lambda _: SimpleNamespace(list_decks=lambda: []))
    for name in ('ensure_builtin_decks', 'ensure_expansion_top_decks'):
        monkeypatch.setattr(replay, name, lambda _: None)
    monkeypatch.setattr(replay, 'select_representative_decks', lambda *a, **k:
                        [{'name': name, 'mainboard': []} for name in ('left_fixture', 'right_fixture')])
    monkeypatch.setattr(replay, 'hydrate_deck_cards', lambda _, cards: cards)
    def match(*args):
        if fail:
            raise ValueError('fixture match failure')
        return {'winner': 1, 'timeout': False, 'turns': 3, 'games_played': 1,
                'wins': {'deck_a': 1, 'deck_b': 0}, 'log': ['fixture only'],
                'games': [{'seed': args[2], 'starting_player': 1, 'play_draw_chooser': 1}]}
    monkeypatch.setattr(replay, 'run_match', match)
    return output


def test_main_emits_start_each_completed_sample_and_terminal_record(tmp_path, monkeypatch, capsys):
    output = mock_runner(monkeypatch, tmp_path)
    replay.main()
    rows = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    progress = rows[:-1]
    assert [row['completed_samples'] for row in progress] == [0, 1, 2, 2]
    assert [row['status'] for row in progress] == ['running'] * 3 + ['completed']
    assert progress[1]['last_sample']['deck_a_seat'] == 1
    assert progress[2]['last_sample']['deck_a_seat'] == 2
    assert json.loads(output.read_text())['matches'] == 2
    assert json.loads((tmp_path / 'matrix.json.progress.json').read_text()) == progress[-1]


def test_main_failure_is_terminal_without_fabricating_completed_samples(tmp_path, monkeypatch, capsys):
    output = mock_runner(monkeypatch, tmp_path, fail=True)
    with pytest.raises(ValueError, match='fixture match failure'):
        replay.main()
    rows = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert rows[-1]['status'] == 'failed'
    assert rows[-1]['completed_samples'] == 0
    assert rows[-1]['last_sample']['seed'] is not None
    assert not output.exists()


def test_default_mode_remains_quiet_except_final_summary(tmp_path, monkeypatch, capsys):
    mock_runner(monkeypatch, tmp_path, progress=False)
    replay.main()
    rows = capsys.readouterr().out.splitlines()
    assert len(rows) == 1 and json.loads(rows[0])['matches'] == 2
    assert not list(tmp_path.glob('*.progress.json'))
