"""Synthetic report/receipt protocol, not played games or AI strength evidence."""
from copy import deepcopy
import hashlib
import json

import pytest

from scripts import baseline_report as reporter
from analytics.resource_budget import RESOURCE_LIMITS

METRICS = ('missed_land_drops', 'unused_mana_passes', 'lethal_misses',
           'bad_blocks', 'stall_streaks', 'redundant_removal_casts')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def seal(record):
    record['measurement']['report_sha256'] = digest(record['report'])
    return record


@pytest.fixture
def records():
    # Complete declared fixed-game schedule, not a builtin/BO3/native certificate.
    roster = [dict(name='protocol-a', archetype='Control', content_sha256='a' * 64),
              dict(name='protocol-b', archetype='Ramp', content_sha256='b' * 64)]
    samples = [dict(deck_a='protocol-a', deck_b='protocol-b', seed_token=seed,
                    deck_a_seat=seat, evidence_complete=True, status='resolved', winner=1)
               for seed in range(10) for seat in (1, 2)]
    pair = dict(archetype_a='Control', archetype_b='Ramp', games=20, resolved_games=20,
                timeouts=0, wins_a=10, wins_b=10, win_rate_a=50.0, win_rate_b=50.0,
                wilson_ci_a=reporter.AnalyticsService._wilson_interval(10, 20),
                wilson_ci_b=reporter.AnalyticsService._wilson_interval(10, 20))
    report = dict(win_rates_by_archetype_pair={'Control vs Ramp': pair},
                  anomalies=dict.fromkeys(reporter.ANOMALY_KEYS, 0),
                  decision_quality_by_archetype={arch: dict.fromkeys(METRICS, 10)
                                                for arch in ('Control', 'Ramp')},
                  oracle_status_counts={'unique': {'structured_effect': 1},
                                        'weighted': {'structured_effect': 1}},
                  card_cache_completeness=dict(cached_cards=1, total_cards=1, missing_cards=0,
                                               completeness_percent=100.0),
                  log_priors=dict(cards=1, samples={'games': 1, 'logs': 1}), unavailable_metrics={})
    receipt = dict(schema_version=1, source_base_commit='a' * 40,
                   backend_before_sha256='a' * 64, backend_after_sha256='a' * 64,
                   corpus_sha256='c' * 64, export_sha256='d' * 64,
                   metric_definitions_sha256='e' * 64, difficulty='master', max_ticks=6000,
                   limits=dict(RESOURCE_LIMITS), sideboard_mode='fixed_no_swaps',
                   schedule_kind='fixed_games', roster=roster, seeds=list(range(10)), seats=[1, 2],
                   complete=True, status='completed_schedule', planned_games=20,
                   attempted_games=20, not_run_games=0, samples=samples)
    receipt.update(engine_rules_sha256='6' * 64, controlled_policy_sha256='7' * 64,
                   experimental_features={'task2.3': '8' * 64, 'task4.1': '9' * 64})
    before = seal(dict(report=report, measurement=receipt))
    seal_configuration(before)
    after = deepcopy(before)
    after['measurement'].update(source_base_commit='b' * 40, backend_before_sha256='b' * 64,
                                backend_after_sha256='b' * 64)
    after['measurement']['experimental_features'] = {'task2.3': 'a' * 64, 'task4.1': 'b' * 64}
    seal_configuration(after)
    for arch in ('Control', 'Ramp'):
        after['report']['decision_quality_by_archetype'][arch]['bad_blocks'] = 9
        after['report']['decision_quality_by_archetype'][arch]['lethal_misses'] = 9
    return before, seal(after)


def compare(records):
    return reporter.compare_reports(*records)


def test_complete_changed_source_is_comparable_without_mutating_inputs(records):
    saved = deepcopy(records)
    result = compare(records)
    assert result['status'] == 'comparable'
    assert result['criteria']['final_metrics'] is True
    assert result['criteria']['p2_nonregression'] is True
    assert result['criteria']['p3_nonregression'] is True
    assert result['criteria']['p4_lethal_decrease'] is True
    assert result['criteria']['p4_order_nonregression'] is True
    assert result['criteria']['p4_unexplained_pass_decrease'] is None
    assert result['scope'] == 'declared_fixed_game_schedule_only'
    assert records == saved
    assert result == compare(records)


def test_equal_is_nonregression_but_not_required_strict_improvement(records):
    before, after = records
    after['report'] = deepcopy(before['report'])
    seal(after)
    result = compare(records)
    assert result['status'] == 'comparable'
    assert result['criteria']['p2_nonregression'] is True
    assert result['criteria']['final_metrics'] is False
    assert result['criteria']['p4_lethal_decrease'] is False


def test_every_quality_and_anomaly_counter_is_diffed_and_regressions_are_not_hidden(records):
    before, after = records
    after['report']['decision_quality_by_archetype']['Control']['redundant_removal_casts'] += 1
    after['report']['anomalies']['cost_failures'] = 1
    seal(after)
    result = compare(records)
    assert len(result['counter_deltas']) == 18
    assert len(result['regressions']) == 2
    assert result['criteria']['final_metrics'] is False


@pytest.mark.parametrize('points,flagged', [(15, False), (20, True)])
def test_pair_threshold_is_strictly_greater_than_fifteen_points(records, points, flagged):
    before, after = records
    samples = after['measurement']['samples']
    pair = after['report']['win_rates_by_archetype_pair']['Control vs Ramp']
    # Select exactly the requested number of previously deck-b wins.
    for row in samples:
        row['winner'] = row['deck_a_seat']
    for row in samples[10 + points // 5:]:
        row['winner'] = 3 - row['deck_a_seat']
    wins = 10 + points // 5
    pair.update(wins_a=wins, wins_b=20-wins, win_rate_a=50.0+points, win_rate_b=50.0-points,
                wilson_ci_a=reporter.AnalyticsService._wilson_interval(wins, 20),
                wilson_ci_b=reporter.AnalyticsService._wilson_interval(20-wins, 20))
    seal(after)
    result = compare(records)
    assert result['status'] == 'comparable'
    assert bool(result['pair_flags']) is flagged
    assert result['criteria']['final_metrics'] is (not flagged)


@pytest.mark.parametrize('side', [0, 1])
@pytest.mark.parametrize('field', ['schema_version', 'source_base_commit', 'backend_before_sha256',
                                 'backend_after_sha256', 'corpus_sha256', 'export_sha256',
                                 'metric_definitions_sha256', 'report_sha256', 'roster', 'seeds',
                                 'seats', 'limits', 'samples', 'complete', 'status', 'planned_games',
                                 'attempted_games', 'not_run_games', 'schedule_kind'])
def test_missing_required_binding_never_admits_a_comparison(records, side, field):
    del records[side]['measurement'][field]
    assert compare(records)['status'] == 'unavailable'


@pytest.mark.parametrize('field,value', [('corpus_sha256', 'f'*64), ('export_sha256', 'f'*64),
    ('metric_definitions_sha256', 'f'*64), ('difficulty', 'strong'), ('max_ticks', 5000),
    ('sideboard_mode', 'unknown'), ('seeds', list(range(9)))])
def test_different_data_definition_or_measurement_contract_is_incomparable(records, field, value):
    records[1]['measurement'][field] = value
    assert compare(records)['status'] == 'unavailable'


@pytest.mark.parametrize('fault', ['partial', 'resource', 'duplicate', 'unknownoutcome', 'drift',
    'boolseat', 'floatseed', 'falsecomplete', 'missingwinner', 'boolwinner', 'wrongpair',
    'boolcount', 'negativecount', 'nullcount', 'floatcount', 'nan', 'infinity', 'unavailable',
    'badpairtotal', 'badpairrate', 'badci', 'foreignquality', 'foreignanomaly', 'wrongarchetype',
    'widenedlimit', 'duplicate_seed', 'duplicate_roster', 'unknownreceiptfield'])
def test_corrupt_or_incomplete_reports_fail_closed_even_when_resealed(records, fault):
    after = records[1]
    m, report = after['measurement'], after['report']
    sample = m['samples'][0]
    counts = report['decision_quality_by_archetype']['Control']
    if fault == 'partial': m['samples'].pop()
    elif fault == 'resource': sample['status'] = 'resource_limit'
    elif fault == 'duplicate': m['samples'][1] = deepcopy(sample)
    elif fault == 'unknownoutcome': sample['winner'] = None
    elif fault == 'drift': m['backend_after_sha256'] = 'f'*64
    elif fault == 'boolseat': sample['deck_a_seat'] = True
    elif fault == 'floatseed': sample['seed_token'] = 0.0
    elif fault == 'falsecomplete': sample['evidence_complete'] = False
    elif fault == 'missingwinner': del sample['winner']
    elif fault == 'boolwinner': sample['winner'] = True
    elif fault == 'wrongpair': sample['deck_a'] = 'foreign'
    elif fault == 'boolcount': counts['bad_blocks'] = True
    elif fault == 'negativecount': counts['bad_blocks'] = -1
    elif fault == 'nullcount': counts['bad_blocks'] = None
    elif fault == 'floatcount': counts['bad_blocks'] = 1.0
    elif fault == 'nan': counts['bad_blocks'] = float('nan')
    elif fault == 'infinity': counts['bad_blocks'] = float('inf')
    elif fault == 'unavailable': report['unavailable_metrics']['bad_blocks'] = 'unknown'
    elif fault == 'badpairtotal': report['win_rates_by_archetype_pair']['Control vs Ramp']['games'] += 1
    elif fault == 'badpairrate': report['win_rates_by_archetype_pair']['Control vs Ramp']['win_rate_a'] = 55.0
    elif fault == 'badci': report['win_rates_by_archetype_pair']['Control vs Ramp']['wilson_ci_a']['games'] = True
    elif fault == 'foreignquality': counts['new_metric'] = 1
    elif fault == 'foreignanomaly': report['anomalies']['new_metric'] = 1
    elif fault == 'wrongarchetype': m['roster'][0]['archetype'] = 'Tempo'
    elif fault == 'widenedlimit': m['limits']['game_log_utf8_bytes'] = 2**60
    elif fault == 'duplicate_seed': m['seeds'][1] = m['seeds'][0]
    elif fault == 'duplicate_roster': m['roster'].append(deepcopy(m['roster'][0]))
    else: m['threshold'] = 99
    if fault not in ('nan', 'infinity'):
        seal(after)
    assert compare(records)['status'] == 'unavailable'


def test_unknown_historical_bad_blocks_and_zero_lethal_are_not_fabricated(records):
    before, after = records
    before['report']['decision_quality_by_archetype']['Control']['bad_blocks'] = None
    before['report']['unavailable_metrics']['bad_blocks'] = 'not measured'
    seal(before)
    assert compare(records)['status'] == 'unavailable'
    before['report']['decision_quality_by_archetype']['Control']['bad_blocks'] = 0
    before['report']['unavailable_metrics'].clear()
    for record in records:
        for row in record['report']['decision_quality_by_archetype'].values():
            row['lethal_misses'] = 0
        seal(record)
    assert compare(records)['criteria']['p4_lethal_decrease'] is False


def test_output_does_not_echo_untrusted_metadata_or_payloads(records):
    records[1]['measurement']['unexpected'] = '/private/SECRET/body?id=opaque'
    result = compare(records)
    assert result['status'] == 'unavailable'
    assert 'SECRET' not in json.dumps(result)
    assert 'opaque' not in json.dumps(result)


def test_comparison_cli_reads_only_two_packages_and_returns_nonzero_if_unavailable(records, tmp_path, capsys):
    paths = [tmp_path / 'before.json', tmp_path / 'after.json']
    for path, row in zip(paths, records):
        path.write_text(json.dumps(row))
    assert reporter.main(['compare', '--before', str(paths[0]), '--after', str(paths[1])]) == 0
    assert json.loads(capsys.readouterr().out)['status'] == 'comparable'
    paths[1].write_text('{}')
    assert reporter.main(['compare', '--before', str(paths[0]), '--after', str(paths[1])]) == 2
    assert json.loads(capsys.readouterr().out)['status'] == 'unavailable'


@pytest.mark.parametrize('payload', ['{"report":{},"report":{}}', '{"x":NaN}', '{"x":Infinity}',
                                    '{}'*600000], ids=['duplicate', 'nan', 'infinity', 'oversize'])
def test_comparison_cli_rejects_duplicate_nonfinite_and_oversize_json(payload, tmp_path, capsys):
    path = tmp_path / 'bad.json'
    path.write_text(payload)
    assert reporter.main(['compare', '--before', str(path), '--after', str(path)]) == 2
    assert 'bad.json' not in capsys.readouterr().out


@pytest.mark.parametrize('fault', ['changedpriors', 'changedoracle', 'changedcache', 'nullpriors',
    'nulloracle', 'nullcache', 'boolcache', 'inconsistentcache', 'boolpriorcount'])
def test_report_data_summaries_cannot_contradict_matched_data_bindings(records, fault):
    report = records[1]['report']
    if fault == 'changedpriors': report['log_priors']['samples']['games'] = 2
    elif fault == 'changedoracle': report['oracle_status_counts']['unique']['missing_oracle'] = 1
    elif fault == 'changedcache': report['card_cache_completeness'].update(cached_cards=0,
                                                missing_cards=1, completeness_percent=0.0)
    elif fault == 'nullpriors': report['log_priors'] = None
    elif fault == 'nulloracle': report['oracle_status_counts']['unique'] = None
    elif fault == 'nullcache': report['card_cache_completeness']['cached_cards'] = None
    elif fault == 'boolcache': report['card_cache_completeness']['cached_cards'] = True
    elif fault == 'inconsistentcache': report['card_cache_completeness']['completeness_percent'] = 50.0
    else: report['log_priors']['samples']['games'] = True
    seal(records[1])
    assert compare(records)['status'] == 'unavailable'


def test_explicit_complete_timeout_is_measured_not_resource_stop_or_invented_zero(records):
    for record in records:
        record['measurement']['samples'][0].update(status='timeout', winner=None)
        report = record['report']
        report['anomalies']['timeouts'] = 1
        pair = report['win_rates_by_archetype_pair']['Control vs Ramp']
        pair.update(resolved_games=19, timeouts=1, wins_a=9, win_rate_a=47.37, win_rate_b=52.63,
                    wilson_ci_a=reporter.AnalyticsService._wilson_interval(9, 19),
                    wilson_ci_b=reporter.AnalyticsService._wilson_interval(10, 19))
        seal(record)
    result = compare(records)
    assert result['status'] == 'comparable'
    row = next(row for row in result['counter_deltas']
               if row['group'] == 'anomalies' and row['metric'] == 'timeouts')
    assert row == dict(group='anomalies', metric='timeouts', before=1, after=1, delta=0)
    records[1]['measurement']['samples'][0]['status'] = 'resource_limit'
    assert compare(records)['status'] == 'unavailable'


def test_reordering_samples_does_not_change_evidence_or_comparison(records):
    first = compare(records)
    records[0]['measurement']['samples'].reverse()
    records[1]['measurement']['samples'].reverse()
    assert compare(records) == first


def seal_configuration(record):
    m = record['measurement']
    m['policy_configuration_sha256'] = digest({key: m[key] for key in
                                  ('controlled_policy_sha256', 'experimental_features')})
    return record


def test_legitimate_multi_feature_ab_retains_different_source_and_configuration_provenance(records):
    result = compare(records)
    assert result['status'] == 'comparable'
    provenance = result['provenance']
    assert provenance['before']['source_base_commit'] == 'a' * 40
    assert provenance['after']['source_base_commit'] == 'b' * 40
    assert provenance['before']['backend_sha256'] != provenance['after']['backend_sha256']
    assert provenance['before']['policy_configuration_sha256'] != provenance['after']['policy_configuration_sha256']
    assert set(provenance['before']['experimental_features']) == {'task2.3', 'task4.1'}


def test_legacy_unpartitioned_packages_cannot_certify_an_ai_experiment(records):
    for record in records:
        for key in ('engine_rules_sha256', 'controlled_policy_sha256',
                    'experimental_features', 'policy_configuration_sha256'):
            del record['measurement'][key]
    assert compare(records)['status'] == 'unavailable'


@pytest.mark.parametrize('key', ['engine_rules_sha256', 'controlled_policy_sha256'])
def test_explicit_experiment_never_waives_changed_engine_or_controlled_policy(records, key):
    records[1]['measurement'][key] = '0' * 64
    seal_configuration(records[1])
    assert compare(records)['status'] == 'unavailable'


@pytest.mark.parametrize('key', ['engine_rules_sha256', 'controlled_policy_sha256',
                               'experimental_features', 'policy_configuration_sha256'])
def test_missing_controlled_input_or_configuration_identity_is_unavailable(records, key):
    del records[1]['measurement'][key]
    assert compare(records)['status'] == 'unavailable'


@pytest.mark.parametrize('features', [{}, {'engine_rules_sha256': 'c' * 64},
                                    {'task4.1': True}, {'task9.9': 'c' * 64}])
def test_arbitrary_feature_mismatch_overrides_are_not_supported(records, features):
    for record in records:
        record['measurement']['experimental_features'] = deepcopy(features)
        seal_configuration(record)
    assert compare(records)['status'] == 'unavailable'


def test_different_declared_feature_sets_are_not_comparable(records):
    del records[1]['measurement']['experimental_features']['task2.3']
    seal_configuration(records[1])
    assert compare(records)['status'] == 'unavailable'


def test_unbound_full_configuration_digest_is_not_provenance(records):
    records[1]['measurement']['policy_configuration_sha256'] = '0' * 64
    assert compare(records)['status'] == 'unavailable'


def set_oracle_coverage(records, unique, weighted, total):
    for record in records:
        record['report']['oracle_status_counts'] = dict(unique=deepcopy(unique), weighted=deepcopy(weighted))
        record['report']['card_cache_completeness'].update(cached_cards=total, total_cards=total,
                                                          missing_cards=0, completeness_percent=100.0 if total else None)
        seal(record)


@pytest.mark.parametrize('unique,weighted,total', [
    ({}, {}, 1),
    ({}, {'structured_effect': 4}, 1),
    ({'structured_effect': 1}, {}, 1),
    ({'structured_effect': 2}, {'structured_effect': 2}, 1),
    ({'structured_effect': 1}, {'structured_effect': 4}, 2),
    ({'structured_effect': 1}, {'structured_effect': 2, 'static_or_noop': 4}, 2),
    ({'structured_effect': 1, 'static_or_noop': 1}, {'structured_effect': 2}, 2),
    ({'structured_effect': 1}, {'static_or_noop': 1}, 1),
    ({'structured_effect': 0, 'static_or_noop': 1}, {'structured_effect': 0, 'static_or_noop': 2}, 1),
    ({'structured_effect': 1}, {'structured_effect': 0}, 1),
    ({'structured_effect': 2, 'static_or_noop': 1}, {'structured_effect': 1, 'static_or_noop': 9}, 3),
], ids=['both_empty_nonzero_corpus', 'missing_unique', 'missing_weighted', 'overcounted_unique',
        'undercounted_unique', 'partial_unique_support', 'partial_weighted_support', 'wrong_weighted_status',
        'zero_unique_status', 'zero_weighted_status', 'nonzero_weighted_status_undercount'])
def test_matching_resealed_oracle_coverage_must_still_be_internally_consistent(records, unique, weighted, total):
    set_oracle_coverage(records, unique, weighted, total)
    assert compare(records)['status'] == 'unavailable'


@pytest.mark.parametrize('unique,weighted,total', [
    ({'structured_effect': 1}, {'structured_effect': 1}, 1),
    ({'structured_effect': 1}, {'structured_effect': 7}, 1),
    ({'structured_event': 1, 'static_or_noop': 2}, {'structured_event': 3, 'static_or_noop': 9}, 3),
    ({'future_supported_status': 2}, {'future_supported_status': 5}, 2),
])
def test_complete_single_and_multiple_statuses_keep_real_copy_weighting_and_dynamic_names(records, unique, weighted, total):
    set_oracle_coverage(records, unique, weighted, total)
    result = compare(records)
    assert result['status'] == 'comparable'
    assert result['criteria']['final_metrics'] is True


def test_empty_diagnostic_corpus_is_not_nonempty_comparison_evidence(records):
    set_oracle_coverage(records, {}, {}, 0)
    for record in records:
        record['report']['unavailable_metrics']['card_cache_completeness.completeness_percent'] = 'no cards in measured corpus'
        seal(record)
    assert compare(records)['status'] == 'unavailable'
