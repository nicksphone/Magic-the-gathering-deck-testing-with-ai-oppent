"""Synthetic protocol records only; these are not invented Magic fixtures."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from analytics.decision_comparison import compare_decision_views


def records(count=2):
    return [dict(kind='private_reconstruction_start', schema_version=1,
                 input_provenance={'manifest_sha256': 'synthetic'},
                 reverse_seats=False, games_expected=1),
            *[dict(kind='decision_state', game=0, seed=1, starting_player=1,
                   decision=i, trace={'action': {'type': 'pass_priority'}},
                   players={}, stack=[], attackers=[], blocks={}, attack_bands=[])
              for i in range(count)],
            dict(kind='private_reconstruction_end', matched=True, games_verified=1)]


def write(path, rows):
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    return path


def test_identical_streams_and_different_lengths(tmp_path):
    a = write(tmp_path / 'a', records())
    b = write(tmp_path / 'b', records())
    assert compare_decision_views(a, b)['matched']
    write(b, records(3))
    report = compare_decision_views(a, b)
    assert not report['matched']
    assert report['first_divergence']['index'] == 2
    assert report['first_divergence']['fields'] == ['sequence_length']


def test_first_changed_decision_is_checked_even_with_unequal_lengths(tmp_path):
    a = write(tmp_path / 'a', records())
    changed = records(3)
    changed[1]['trace']['action'] = {'type': 'keep'}
    b = write(tmp_path / 'b', changed)
    assert compare_decision_views(a, b)['first_divergence']['index'] == 0


@pytest.mark.parametrize('field', ['players', 'stack', 'attackers', 'blocks', 'attack_bands'])
def test_private_state_differences_not_hidden(tmp_path, field):
    original = records()
    changed = deepcopy(original)
    changed[2][field] = {'different': True}
    result = compare_decision_views(write(tmp_path / 'a', original), write(tmp_path / 'b', changed))
    assert result['first_divergence']['fields'] == [field]


def test_metadata_exception_is_explicit_one_sided_and_never_drops_declarations(tmp_path):
    a = write(tmp_path / 'a', records())
    changed = records()
    changed[1]['trace']['action']['banding_attackers'] = []
    b = write(tmp_path / 'b', changed)
    assert not compare_decision_views(a, b)['matched']
    result = compare_decision_views(a, b, allow_added_combat_metadata=True)
    assert result['matched'] and len(result['ignored_added_combat_metadata']) == 1
    changed[1]['trace']['action']['bands'] = [['a', 'b']]
    write(b, changed)
    assert not compare_decision_views(a, b, allow_added_combat_metadata=True)['matched']
    assert not compare_decision_views(b, a, allow_added_combat_metadata=True)['matched']


@pytest.mark.parametrize('mutation', ['no_footer', 'failed', 'wrong_games', 'after_footer', 'wrong_version', 'missing_field'])
def test_reject_incomplete_evidence_even_after_known_difference(tmp_path, mutation):
    a = write(tmp_path / 'a', records())
    changed = records()
    changed[1]['trace']['action']['type'] = 'keep'
    if mutation == 'no_footer': changed.pop()
    if mutation == 'failed': changed[-1]['matched'] = False
    if mutation == 'wrong_games': changed[-1]['games_verified'] = 0
    if mutation == 'after_footer': changed.append(changed[1])
    if mutation == 'wrong_version': changed[0]['schema_version'] = 2
    if mutation == 'missing_field': del changed[2]['players']
    with pytest.raises(ValueError):
        compare_decision_views(a, write(tmp_path / 'b', changed))


def test_provenance_and_unterminated_stream_rejected(tmp_path):
    a = write(tmp_path / 'a', records())
    changed = records()
    changed[0]['reverse_seats'] = True
    b = write(tmp_path / 'b', changed)
    with pytest.raises(ValueError, match='provenance'):
        compare_decision_views(a, b)
    b.write_text(a.read_text().rstrip('\n'))
    with pytest.raises(ValueError, match='Unterminated'):
        compare_decision_views(a, b)


@pytest.mark.parametrize('field,value', [('decision', 4), ('game', 2),
                                         ('seed', 2), ('starting_player', 2)])
def test_reject_missing_or_inconsistent_decision_sequence(tmp_path, field, value):
    a = write(tmp_path / 'a', records())
    changed = records()
    changed[2][field] = value
    with pytest.raises(ValueError):
        compare_decision_views(a, write(tmp_path / 'b', changed))


def test_cli_private_output_and_non_overwrite(tmp_path):
    a = write(tmp_path / 'a', records())
    out = tmp_path / 'out'
    command = [sys.executable, str(Path(__file__).parents[1] / 'scripts/compare_decision_views.py'),
               '--baseline', str(a), '--candidate', str(a), '--output', str(out)]
    assert subprocess.run(command, capture_output=True).returncode == 0
    assert out.stat().st_mode & 0o777 == 0o600
    saved = out.read_bytes()
    assert subprocess.run(command, capture_output=True).returncode == 2
    assert out.read_bytes() == saved
