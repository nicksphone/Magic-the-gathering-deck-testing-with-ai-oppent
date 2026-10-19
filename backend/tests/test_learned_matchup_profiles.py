"""Synthetic Task 3.1 protocol rows, NOT native matches or measured strength."""
from copy import deepcopy
import importlib
import json
from pathlib import Path

import pytest

from ai import matchup_profiles as consumer
from scripts import matchup_round_robin as rr
from analytics.resource_budget import RESOURCE_LIMITS
from tests.test_matchup_round_robin_protocol import roster

METRICS = ('missed_land_drops', 'unused_mana_passes', 'lethal_misses',
           'bad_blocks', 'stall_streaks', 'redundant_removal_casts')


def builder():
    path = Path(__file__).parents[1] / 'scripts/derive_matchup_profiles.py'
    assert path.is_file(), 'Missing deterministic learned matchup builder'
    module = importlib.import_module('scripts.derive_matchup_profiles')
    assert callable(getattr(module, 'derive_profiles', None))
    return module


@pytest.fixture
def protocol(tmp_path):
    # Explicit synthetic source-lineage domain, not an approved production epoch.
    backend = tmp_path / 'measured-backend'
    backend.mkdir()
    (backend / 'synthetic.py').write_text('synthetic_protocol = True\n')
    files = rr.collect_source_manifest(backend)
    binding = dict(schema_version=1, source_base_commit='a' * 40,
                   backend_files=files, backend_sha256=rr.digest(files))
    lineage = dict(source_base_commit=binding['source_base_commit'],
                   backend_sha256=binding['backend_sha256'], source_binding_sha256=rr.digest(binding))
    rows = roster()
    for n, row in enumerate(rows):
        row['archetype'] = 'Control' if n % 2 else 'Midrange'
    export = rr.make_export(rows, corpus_sha256='c' * 64)
    rows = rr.validate_export(export)
    schedule = rr.build_schedule(rows, list(range(5)))
    series = []
    for n, scheduled in enumerate(schedule):
        # 7/10 wins by deck_a, independent of its actual player seat.
        winner = scheduled['deck_a_seat'] if n % 10 < 7 else 3 - scheduled['deck_a_seat']
        quality = dict(counts={str(pid): {metric: (2 if metric == 'unused_mana_passes'
                            and pid != scheduled['deck_a_seat'] else 0) for metric in METRICS}
                            for pid in (1, 2)},
                       availability={str(pid): dict.fromkeys(METRICS, True) for pid in (1, 2)})
        games = [dict(winner=winner, timeout=False, seed=scheduled['root_seed'] + k,
                      starting_player=1 if k == 0 else 3-winner,
                      play_draw_chooser=1 if k == 0 else 3-winner, turn=8, ticks=40,
                      log_hash='d' * 64, quality=deepcopy(quality), evidence_complete=True,
                      evidence=dict(complete=True, bytes=1, raw_sha256='e' * 64,
                                    reference=f'game-{k+1:02d}.json')) for k in (0, 1)]
        series.append(dict(scheduled, status='resolved', winner=winner,
                           wins={'deck_a': 2 if winner == 1 else 0, 'deck_b': 2 if winner == 2 else 0},
                           games=games))
    # Deliberately reproduce real runner aggregation; Wilson bounds not authority.
    def wilson(wins, total):
        return dict(low=0.0, high=100.0)
    pairs = []
    for first in schedule[::2]:
        records = [s for s in series if (s['deck_a'], s['deck_b'], s['seed_token']) ==
                   (first['deck_a'], first['deck_b'], first['seed_token'])]
        quality = rr.quality_for_pair(records, metrics=METRICS)
        pairs.append(dict(deck_a=first['deck_a'], deck_b=first['deck_b'], seed=first['seed_token'],
                          **rr.summarize_pair(records, wilson=wilson),
                          decision_quality_a=quality['deck_a'], decision_quality_b=quality['deck_b']))
    manifest = dict(export_sha256=rr.digest(export), input_export_base_commit=export['source_commit'],
                    source_base_commit=binding['source_base_commit'], source_binding_sha256=rr.digest(binding),
                    backend_before_sha256=binding['backend_sha256'], difficulty='strong', max_ticks=400,
                    limits=dict(RESOURCE_LIMITS), seeds=list(range(5)), sideboard_mode='fixed_no_swaps',
                    planned_series=len(schedule), planned_pairs=55,
                    roster=[dict(name=row['name'], archetype=row['archetype'],
                                 classification_status=row['classification_status'], content_sha256=rr.digest(row),
                                 mainboard_cards=60, sideboard_cards=1) for row in rows])
    summary = dict(schema_version=1, manifest=manifest, measured_source=rr.source_closure(
        binding, backend, binding['backend_sha256']), complete=True, status='completed_schedule',
        attempted_series=len(series), not_run_series=0, pairs=pairs, series=series)
    return summary, export, binding, backend, lineage


def derive(protocol):
    summary, export, binding, backend, lineage = protocol
    return builder().derive_profiles(summary, export, binding, measured_backend=backend,
                                     expected_lineage=lineage)


def test_full_schema_and_mirrored_player_wins_produce_bounded_nonzero_profiles(protocol):
    output = derive(protocol)
    assert output['schema_version'] == 1 and output['lineage'] == protocol[4]
    assert output['coverage']['builtin_decks'] == 11 and output['coverage']['builtin_pairs'] == 55
    assert set(output['profiles']) == {'control', 'midrange'}
    assert output['profiles']['midrange']['control']['proactive_bias'] != 0
    assert output['counts']['resolved_series'] == 550
    assert output['counts']['resolved_games'] == 1100
    assert sum(row['wins'] for pairs in output['samples'].values() for row in pairs.values()) == 550
    for pairs in output['profiles'].values():
        for values in pairs.values():
            assert set(values) == {'proactive_bias', 'holdup_bias', 'risk_tolerance'}
            assert all(type(value) is float and -2 <= value <= 2 for value in values.values())


def test_deterministic_reordering_and_inputs_unchanged(protocol):
    before = deepcopy(protocol[:3])
    first = derive(protocol)
    shuffled = deepcopy(protocol[0])
    shuffled['series'].reverse()
    shuffled['pairs'].reverse()
    second = derive((shuffled, *protocol[1:]))
    assert rr.canonical_bytes(first) == rr.canonical_bytes(second)
    assert protocol[:3] == before


@pytest.mark.parametrize('bad', ['partial', 'planned', 'resource', 'timeout', 'draw_cap', 'boolwinner',
                                'gamewins', 'seat', 'duplicated', 'qualitymissing', 'qualitybool',
                                'qualityunavailable', 'evidence', 'stale', 'closure', 'paircounts',
                                'pairquality', 'roster', 'unknown', 'seeds', 'ticks', 'binding'])
def test_incomplete_invalid_or_stale_matrix_rejects_whole_admission(protocol, bad):
    summary, export, binding, backend, lineage = protocol
    summary, export, binding = deepcopy((summary, export, binding))
    row = summary['series'][0]
    if bad == 'partial': summary['not_run_series'] = 1
    elif bad == 'planned': summary['status'] = 'planned_not_executed'
    elif bad in {'resource', 'timeout', 'draw_cap'}: row['status'] = 'resource_limit' if bad == 'resource' else bad
    elif bad == 'boolwinner': row['winner'] = True
    elif bad == 'gamewins': row['wins'] = {'deck_a': 0, 'deck_b': 2}
    elif bad == 'seat': row['deck_a_seat'] = 3
    elif bad == 'duplicated': summary['series'][1] = deepcopy(row)
    elif bad == 'qualitymissing': row['games'][0]['quality'] = None
    elif bad == 'qualitybool': row['games'][0]['quality']['counts']['1']['bad_blocks'] = True
    elif bad == 'qualityunavailable': row['games'][0]['quality']['availability']['1']['bad_blocks'] = False
    elif bad == 'evidence': row['games'][0]['evidence_complete'] = False
    elif bad == 'stale': summary['manifest']['source_base_commit'] = 'b' * 40
    elif bad == 'closure': summary['measured_source']['equal'] = False
    elif bad == 'paircounts': summary['pairs'][0]['wins_a'] += 1
    elif bad == 'pairquality': summary['pairs'][0]['decision_quality_a']['bad_blocks'] += 1
    elif bad == 'roster': summary['manifest']['roster'].pop()
    elif bad == 'unknown': export['decks'][0]['classification_status'] = 'unknown'
    elif bad == 'seeds': summary['manifest']['seeds'] = [True]
    elif bad == 'ticks': row['games'][0]['ticks'] = True
    else: binding['backend_sha256'] = 'b' * 64
    with pytest.raises(ValueError):
        builder().derive_profiles(summary, export, binding, measured_backend=backend, expected_lineage=lineage)


def test_actual_measured_source_drift_rejects_before_derivation(protocol):
    (protocol[3] / 'synthetic.py').write_text('changed = True\n')
    with pytest.raises(ValueError):
        derive(protocol)


def test_consumer_uses_explicit_lineage_not_changed_current_module_hash(protocol, tmp_path, monkeypatch):
    payload = derive(protocol)
    path = tmp_path / 'matchup_profiles.json'
    path.write_bytes(rr.canonical_bytes(payload))
    assert callable(getattr(consumer, 'load_profiles', None)), 'Missing typed generated-data consumer'
    monkeypatch.setattr(consumer, 'PROFILE_PATH', path)
    monkeypatch.setattr(consumer, 'EXPECTED_LINEAGE', protocol[4])
    consumer._load_profile_table.cache_clear()
    try:
        assert consumer.profile_for('Midrange', 'Control') == payload['profiles']['midrange']['control']
        assert consumer.profile_for('foreign', 'Control') == consumer._legacy_profile_for('foreign', 'Control')
        assert consumer.profile_for('Control', None) == consumer._legacy_profile_for('Control', None)
    finally:
        consumer._load_profile_table.cache_clear()


@pytest.mark.parametrize('fault', ['absent', 'malformed', 'stale', 'bool', 'nan', 'unknownkey', 'unqualified'])
def test_unknown_or_unqualified_consumer_preserves_exact_legacy_values(protocol, tmp_path, monkeypatch, fault):
    payload = derive(protocol)
    path = tmp_path / 'matchup_profiles.json'
    if fault == 'stale': payload['lineage']['source_base_commit'] = 'b' * 40
    elif fault in {'bool', 'nan'}: payload['profiles']['control']['control']['proactive_bias'] = True if fault == 'bool' else float('nan')
    elif fault == 'unknownkey': payload['profiles']['control']['control']['secret'] = 1
    elif fault == 'unqualified': payload['qualified'] = False
    if fault != 'absent':
        path.write_text('not json' if fault == 'malformed' else json.dumps(payload))
    assert callable(getattr(consumer, 'load_profiles', None))
    monkeypatch.setattr(consumer, 'PROFILE_PATH', path)
    monkeypatch.setattr(consumer, 'EXPECTED_LINEAGE', protocol[4])
    consumer._load_profile_table.cache_clear()
    try:
        for own in ('Control', 'Midrange', 'Aggro', 'Tempo', 'Combo-lite', 'unknown', ''):
            for opp in ('Control', 'Midrange', 'Burn', 'Counter-heavy', 'Tokens', None):
                assert consumer.profile_for(own, opp) == consumer._legacy_profile_for(own, opp)
    finally:
        consumer._load_profile_table.cache_clear()


@pytest.mark.parametrize('fault', ['missingpair', 'unknownpair', 'alterednumeric', 'boolcount',
                                 'incompletecounts', 'alteredwins', 'qualitybool'])
def test_resealed_invalid_generated_table_is_not_a_qualified_pair(protocol, tmp_path, fault):
    payload = derive(protocol)
    if fault == 'missingpair': del payload['profiles']['control']['control']
    elif fault == 'unknownpair': payload['profiles']['foreign'] = deepcopy(payload['profiles']['control'])
    elif fault == 'alterednumeric': payload['profiles']['control']['control']['risk_tolerance'] += 0.1
    elif fault == 'boolcount': payload['counts']['resolved_games'] = True
    elif fault == 'incompletecounts': payload['counts']['resolved_series'] -= 1
    elif fault == 'alteredwins': payload['samples']['control']['control']['wins'] += 1
    else: payload['samples']['control']['control']['quality']['bad_blocks'] = True
    payload['artifact_sha256'] = consumer.artifact_digest(
        {key: value for key, value in payload.items() if key != 'artifact_sha256'})
    path = tmp_path / 'invalid.json'
    path.write_bytes(rr.canonical_bytes(payload))
    assert consumer.load_profiles(path, expected_lineage=protocol[4]) == {}


@pytest.mark.parametrize('fault', ['crossquality', 'crosswins', 'crossgames', 'selfquality',
                                 'selfwins', 'selfoddgames', 'foldbothcross', 'foreignroster', 'missingroster'])
def test_rederived_resealed_impossible_directional_samples_reject_whole_table(protocol, tmp_path, fault):
    """Consistent local transforms/checksums cannot substitute for matrix integrity."""
    payload = derive(protocol)
    payload['coverage']['roster_schema_version'] = 1
    payload['coverage']['roster_archetypes'] = {row['name']: row['archetype'].strip().lower()
                                               for row in protocol[1]['decks']}
    cross = payload['samples']['midrange']['control']
    same = payload['samples']['control']['control']
    if fault == 'crossquality': cross['quality']['bad_blocks'] += 1
    elif fault == 'crosswins':
        cross['wins'] += 1
        same['wins'] -= 1  # Keep the whole-table win total exact.
    elif fault == 'crossgames':
        cross['games'] += 2
        payload['counts']['resolved_games'] += 1
    elif fault == 'selfquality': same['quality']['bad_blocks'] += 1
    elif fault == 'selfwins':
        same['wins'] += 1
        cross['wins'] -= 1
    elif fault == 'selfoddgames':
        same['games'] += 1
        cross['games'] += 1
        payload['counts']['resolved_games'] += 1
    elif fault == 'foldbothcross':
        target = payload['samples']['midrange']['midrange']
        for own, opp in (('midrange', 'control'), ('control', 'midrange')):
            moved = payload['samples'][own].pop(opp)
            del payload['profiles'][own][opp]
            for key in ('series', 'wins', 'games'):
                target[key] += moved[key]
            for key in ('quality', 'opponent_quality'):
                for metric in METRICS:
                    target[key][metric] += moved[key][metric]
    elif fault == 'foreignroster':
        roster = payload['coverage']['roster_archetypes']
        name = next(iter(roster))
        roster['foreign-deck'] = roster.pop(name)
    else:
        del payload['coverage']['roster_archetypes']
    for own, pairs in payload['samples'].items():
        for opp, sample in pairs.items():
            payload['profiles'][own][opp] = consumer.advisory_profile(own, opp, sample)
    payload['artifact_sha256'] = consumer.artifact_digest(
        {key: value for key, value in payload.items() if key != 'artifact_sha256'})
    path = tmp_path / 'impossible-resealed.json'
    path.write_bytes(rr.canonical_bytes(payload))
    assert consumer.load_profiles(path, expected_lineage=protocol[4]) == {}


@pytest.mark.parametrize('grouping', ['one_shared_archetype', 'eleven_distinct_archetypes'])
def test_complete_matrix_bucket_counts_do_not_assume_archetype_arity(protocol, tmp_path, grouping):
    from decks.selection import _ARCHETYPE_PRIORITY
    summary, export, binding, backend, lineage = protocol
    summary, export = deepcopy((summary, export))
    labels = [label for label in _ARCHETYPE_PRIORITY if label != 'unknown']
    for index, row in enumerate(export['decks']):
        row['archetype'] = 'Control' if grouping == 'one_shared_archetype' else labels[index]
    export = rr.make_export(export['decks'], corpus_sha256=export['corpus_sha256'])
    summary['manifest']['export_sha256'] = rr.digest(export)
    summary['manifest']['roster'] = [dict(name=row['name'], archetype=row['archetype'],
        classification_status='resolved', content_sha256=rr.digest(row),
        mainboard_cards=60, sideboard_cards=1) for row in export['decks']]
    output = derive((summary, export, binding, backend, lineage))
    path = tmp_path / 'complete-aggregation.json'
    path.write_bytes(rr.canonical_bytes(output))
    assert consumer.load_profiles(path, expected_lineage=lineage) == output['profiles']
    assert sum(len(pairs) for pairs in output['profiles'].values()) == (1 if grouping == 'one_shared_archetype' else 110)
    if grouping == 'one_shared_archetype':
        sample = output['samples']['control']['control']
        assert sample['series'] == 1100 and sample['wins'] == 550 and sample['games'] == 2200
        assert sample['quality'] == sample['opponent_quality']
    else:
        assert all(own not in pairs for own, pairs in output['profiles'].items())


def cli_inputs(protocol, tmp_path, monkeypatch):
    """Actual CLI, explicitly synthetic expected-lineage injection; no native grant."""
    import sys
    module = builder()
    monkeypatch.setattr(module, 'EXPECTED_LINEAGE', protocol[4])
    directory = tmp_path / 'cli-inputs'
    directory.mkdir()
    inputs = {}
    for name, value in zip(('summary', 'deck-export', 'source-binding'), protocol[:3]):
        path = directory / (name + '.json')
        path.write_bytes(rr.canonical_bytes(value))
        inputs[name] = path
    def invoke(output):
        argv = ['derive-profiles', '--measured-backend', str(protocol[3]), '--output', str(output)]
        for name, path in inputs.items():
            argv += ['--'+name, str(path)]
        monkeypatch.setattr(sys, 'argv', argv)
        return module.main()
    return module, inputs, invoke


@pytest.mark.parametrize('alias', ['direct', 'symlink_parent'])
def test_actual_main_cannot_add_new_ordinary_file_to_measured_source(protocol, tmp_path, monkeypatch, alias):
    module, _, invoke = cli_inputs(protocol, tmp_path, monkeypatch)
    parent = protocol[3]
    if alias == 'symlink_parent':
        parent = tmp_path / 'measured-alias'
        parent.symlink_to(protocol[3], target_is_directory=True)
    output = parent / 'new_source.py'
    before = rr.collect_source_manifest(protocol[3])
    original = module.derive_profiles
    calls = []
    def observe(*args, **kwargs):
        calls.append('derive')
        return original(*args, **kwargs)
    monkeypatch.setattr(module, 'derive_profiles', observe)
    caught = None
    try:
        invoke(output)
    except ValueError as error:
        caught = error
    after = rr.collect_source_manifest(protocol[3])
    print('CLI_SOURCE_GUARD=' + json.dumps(dict(alias=alias, caught=type(caught).__name__,
                                               source_equal=after == before,
                                               output_exists=output.exists(), derive_calls=len(calls))))
    assert isinstance(caught, ValueError), 'Reject measured-source output before computation'
    assert after == before and not output.exists() and calls == []


@pytest.mark.parametrize('input_name', ['summary', 'deck-export', 'source-binding'])
def test_actual_main_existing_input_alias_stops_before_compute(protocol, tmp_path, monkeypatch, input_name):
    module, inputs, invoke = cli_inputs(protocol, tmp_path, monkeypatch)
    before = {name: path.read_bytes() for name, path in inputs.items()}
    original, calls = module.derive_profiles, []
    def observe(*args, **kwargs):
        calls.append('derive')
        return original(*args, **kwargs)
    monkeypatch.setattr(module, 'derive_profiles', observe)
    with pytest.raises(FileExistsError):
        invoke(inputs[input_name])
    assert {name: path.read_bytes() for name, path in inputs.items()} == before
    assert calls == [], 'Exclusive output reservation must precede input processing'


def test_actual_main_never_follows_dangling_output_leaf(protocol, tmp_path, monkeypatch):
    _, _, invoke = cli_inputs(protocol, tmp_path, monkeypatch)
    target, output = tmp_path / 'uncreated-target.json', tmp_path / 'dangling.json'
    output.symlink_to(target)
    before = rr.collect_source_manifest(protocol[3])
    with pytest.raises(FileExistsError):
        invoke(output)
    assert output.is_symlink() and not target.exists()
    assert rr.collect_source_manifest(protocol[3]) == before


def test_actual_main_valid_external_output_is_reserved_and_source_stays_equal(protocol, tmp_path, monkeypatch):
    module, _, invoke = cli_inputs(protocol, tmp_path, monkeypatch)
    output = tmp_path / 'outside-source.json'
    before, original = rr.collect_source_manifest(protocol[3]), module.derive_profiles
    calls = []
    def observe(*args, **kwargs):
        assert output.is_file() and output.read_bytes() == b'', 'Reserve before derive'
        calls.append('derive')
        return original(*args, **kwargs)
    monkeypatch.setattr(module, 'derive_profiles', observe)
    assert invoke(output) == 0 and calls == ['derive']
    assert rr.collect_source_manifest(protocol[3]) == before
    payload = json.loads(output.read_bytes())
    assert consumer.load_profiles(output, expected_lineage=protocol[4]) == payload['profiles']


def test_actual_main_bad_input_keeps_empty_reservation_without_source_mutation(protocol, tmp_path, monkeypatch):
    _, inputs, invoke = cli_inputs(protocol, tmp_path, monkeypatch)
    inputs['summary'].write_bytes(b'not-json')
    output = tmp_path / 'failed-reserved.json'
    before = rr.collect_source_manifest(protocol[3])
    with pytest.raises(ValueError):
        invoke(output)
    assert output.is_file() and output.read_bytes() == b''
    assert inputs['summary'].read_bytes() == b'not-json'
    assert rr.collect_source_manifest(protocol[3]) == before
