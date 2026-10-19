"""Actual private writer/packager protocols with inert games, not gameplay."""
import json

import pytest

from scripts import baseline_report as report
from scripts import matchup_round_robin as runner
from tests.test_baseline_measurement_package import protocol_run


def reseal(production, directory):
    # Negative tests alter only producer metadata, never the actual raw/row outcomes.
    (directory / 'producer.json').write_bytes(runner.canonical_bytes(production))


def test_balanced_mirror_winner_substitution_rejects_even_when_aggregate_equal(tmp_path, monkeypatch):
    package = report.package_measurement

    def substituted(production, **kwargs):
        assert len({row['archetype'] for row in production['configuration']['roster']}) == 2
        assert [game['winner'] for game in production['games']] == [1, 1]
        assert [game['result']['winner'] for game in production['games']] == [1, 1]
        assert [json.loads((kwargs['directory'] / f'game-{i:02d}.json').read_bytes())['result']['winner']
                for i in (1, 2)] == [1, 1]
        assert [row['winner'] for row in production['rows']] == [1, 1]
        # Both vectors win exactly one mirror for each deck, but change each sample.
        assert sum(winner == game['deck_a_seat'] for winner, game in
                   zip([1, 1], production['games'])) == 1
        for game in production['games']:
            game['winner'] = 2
        assert sum(game['winner'] == game['deck_a_seat'] for game in production['games']) == 1
        reseal(production, kwargs['directory'])
        return package(production, **kwargs)

    monkeypatch.setattr(report, 'package_measurement', substituted)
    with pytest.raises(ValueError):
        protocol_run(tmp_path, monkeypatch, outcomes=(1, 1))


SUBSTITUTIONS = [
    ('deck_a', 'foreign public protocol deck'), ('deck_b', 'foreign public protocol deck'),
    ('seed_token', 99), ('deck_a_seat', 2), ('evidence_complete', 1),
    ('status', 'timeout'), ('winner', 2),
]


@pytest.mark.parametrize(('field', 'value'), SUBSTITUTIONS)
def test_each_complete_published_sample_field_is_joined(tmp_path, monkeypatch, field, value):
    package = report.package_measurement

    def substituted(production, **kwargs):
        assert production['games'][0][field] != value or type(value) is not bool
        production['games'][0][field] = value
        reseal(production, kwargs['directory'])
        return package(production, **kwargs)

    monkeypatch.setattr(report, 'package_measurement', substituted)
    with pytest.raises(ValueError):
        protocol_run(tmp_path, monkeypatch, outcomes=(1, 1))


@pytest.mark.parametrize(('field', 'value'), SUBSTITUTIONS)
def test_receiptless_failure_cannot_export_an_invented_sample(tmp_path, monkeypatch, field, value):
    package = report.package_measurement

    def substituted(production, **kwargs):
        assert production['game_records'] == [] and production['rows'] == []
        sample = production['games'][0]
        assert sample['status'] == 'resource_limit' and sample['winner'] is None
        assert sample['evidence_complete'] is False and 'result' not in sample
        sample[field] = value
        reseal(production, kwargs['directory'])
        return package(production, **kwargs)

    monkeypatch.setattr(report, 'package_measurement', substituted)
    with pytest.raises(ValueError):
        protocol_run(tmp_path, monkeypatch, pre_encode_stop=True)


@pytest.mark.parametrize('kind', ['resolved', 'draw', 'resource', 'writer', 'pre_encode', 'action'])
def test_genuine_outcomes_and_unavailable_failures_remain_truthful(tmp_path, monkeypatch, kind):
    options = {}
    if kind == 'resolved': options['outcomes'] = (1, 1)
    if kind == 'draw': options['outcomes'] = (0, 2)
    if kind in ('resource', 'action'):
        options.update(outcomes=(None, 2), stop='resource_limit' if kind == 'resource' else 'action_error')
    if kind == 'writer': options['fail_writer'] = True
    if kind == 'pre_encode': options['pre_encode_stop'] = True
    result, calls, _, _ = protocol_run(tmp_path, monkeypatch, **options)
    production, measurement = result['production'], result['package']['package']['measurement']
    assert result['package']['eligible'] is (kind == 'resolved')
    assert len(measurement['samples']) == len(production['games']) == len(calls)
    for index, sample in enumerate(measurement['samples']):
        assert sample == {key: production['games'][index][key] for key in sample}
        if 'result' in production['games'][index]:
            actual = production['games'][index]['result']
            assert sample['winner'] == actual['winner']
            assert sample['status'] == (actual.get('stop_reason') or (
                'timeout' if actual['winner'] is None else 'draw' if actual['winner'] == 0 else 'resolved'))
        else:
            assert sample['winner'] is None and sample['evidence_complete'] is False
            assert sample['status'] == 'resource_limit'
    if kind != 'resolved':
        assert production['complete'] is False
        assert all(sample['status'] != 'timeout' for sample in measurement['samples'])
