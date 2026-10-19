"""Mocked runner checks: output aliases must never destroy pinned inputs."""
import json
import os

import pytest

from scripts import regression_matrix_replay as replay


def inputs(tmp_path):
    path = tmp_path / 'decks.json'
    decks = [{'name': name, 'mainboard': [{'quantity': 60, 'card_name': 'Island',
              'type_line': 'Basic Land - Island', 'mana_cost': '',
              'oracle_text': '{T}: Add {U}.'}]} for name in ('First', 'Second')]
    replay._write_deck_manifest(str(path), decks, {'fixture': 'runner-only'})
    return path


def match(*args, **kwargs):
    return {'winner': 1, 'turns': 3, 'games_played': 1,
            'wins': {'deck_a': 1, 'deck_b': 0}, 'timeout': False, 'log': [],
            'games': [{'seed': args[2], 'starting_player': 1, 'play_draw_chooser': 1}]}


@pytest.mark.parametrize('alias', ['same', 'symlink', 'hardlink'])
@pytest.mark.parametrize('collision', ['input-summary', 'input-progress', 'input-export',
                                     'summary-export', 'progress-export'])
def test_cli_rejects_aliases_before_any_simulation_or_evidence_write(tmp_path, monkeypatch, alias, collision):
    source = inputs(tmp_path)
    output, export = tmp_path / 'results.json', None
    progress = collision in {'input-progress', 'progress-export'}
    if collision.startswith('input-'):
        original = source
    else:
        original = tmp_path / ('results.json.progress.json' if progress else 'results.json')
        original.write_bytes(b'previous evidence\n')
    candidate = original if alias == 'same' else tmp_path / 'alias.json'
    if alias == 'symlink':
        candidate.symlink_to(original)
    elif alias == 'hardlink':
        os.link(original, candidate)
    if collision == 'input-summary':
        output = candidate
    elif collision == 'input-progress':
        # The progress filename is derived from the summary, not an independent flag.
        output = tmp_path / 'alias'
        derived = tmp_path / 'alias.progress.json'
        if alias == 'same':
            source.rename(derived)
            source = derived
            original = derived
        elif alias == 'symlink':
            derived.symlink_to(source)
        else:
            os.link(source, derived)
    else:
        export = candidate
    arguments = ['replay', '--deck-manifest', str(source), '--output', str(output),
                 '--trace-output', str(tmp_path / 'trace.jsonl')]
    if progress:
        arguments.append('--progress')
    if export is not None:
        arguments += ['--write-deck-manifest', str(export)]
    before = {p: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    monkeypatch.setattr('sys.argv', arguments)
    calls = []
    def simulate(*args, **kwargs):
        calls.append(args)
        return match(*args, **kwargs)
    monkeypatch.setattr(replay, 'run_match', simulate)
    with pytest.raises(SystemExit) as error:
        replay.main()
    assert error.value.code == 2
    assert calls == []
    assert {p: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()} == before


def test_distinct_manifest_summary_progress_export_and_traces_remain_usable(tmp_path, monkeypatch):
    source = inputs(tmp_path)
    before = source.read_bytes()
    output, export = tmp_path / 'results.json', tmp_path / 'selected.json'
    arguments = ['replay', '--deck-manifest', str(source), '--output', str(output),
                 '--write-deck-manifest', str(export), '--progress', '--matches-per-pair', '1',
                 '--trace-output', str(tmp_path / 'trace.jsonl'),
                 '--decision-metrics', str(tmp_path / 'metrics.jsonl')]
    monkeypatch.setattr('sys.argv', arguments)
    monkeypatch.setattr(replay, 'run_match', match)
    replay.main()
    assert source.read_bytes() == before
    result = json.loads(output.read_text())
    assert result['matches'] == 2 and result['determinism_failures'] == 0
    assert replay._load_deck_manifest(str(export), 2)[0] == replay._load_deck_manifest(str(source), 2)[0]
    assert json.loads((tmp_path / 'results.json.progress.json').read_text())['status'] == 'completed'
    assert len((tmp_path / 'trace.jsonl').read_text().splitlines()) == 5
