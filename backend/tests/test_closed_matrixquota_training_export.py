"""Synthetic closed110 protocol vectors, NOT games or approved training data.

Test-first STATIC/UNRUN. The additive parent-acceptance/index ABI below requires
parent review before the exporter is authored; no historical success is invented.
"""
from copy import deepcopy
from hashlib import sha256
import importlib
import json
from pathlib import Path

import pytest

from analytics.resource_budget import RESOURCE_LIMITS
from scripts import matchup_round_robin as rr
from tests.test_matchup_round_robin_protocol import roster


BACKEND = Path(__file__).resolve().parents[1]
PRODUCERS = ('scripts/matchup_round_robin.py',
             'scripts/regression_matrix_replay.py', 'scripts/build_ai_log_priors.py')
METRICS = ('missed_land_drops', 'unused_mana_passes', 'lethal_misses',
           'bad_blocks', 'stall_streaks', 'redundant_removal_casts')
CHECKS = ('role_inputs_equal', 'prepared_inputs_equal', 'setup_approval_equal',
          'source_equal', 'full_source_metadata_equal', 'F_equal',
          'full_F_metadata_equal', 'runtime_equal', 'system_equal',
          'parent_resources_equal', 'physical_closed', 'own_cgroup_quiet',
          'C_only_owned', 'data_fuser_empty', 'no_SQL_files', 'true_actor_OS_exit0',
          'not_stopped', 'actor_original_error_absent', 'actor_cli_exit0',
          'actor_native_denials_empty', 'actor_guard_not_sticky',
          'actor_resources_equal', 'actor_quota_bounded')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      allow_nan=False).encode('utf-8')


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value))
    return path


def digest_file(path):
    return sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def reseal(packet):
    """Seal labelled synthetic inputs, never an observed execution or authority."""
    role = packet['role_root']
    summary = read(role / 'actual/workspace/summary.json')
    acceptance = read(packet['parent_receipt'])
    acceptance['summary_sha256'] = digest_file(role / 'actual/workspace/summary.json')
    qualifier = read(packet['qualifier_report'])
    qualifier['summary_sha256'] = acceptance['summary_sha256']
    write(packet['qualifier_report'], qualifier)
    acceptance['strict_report']['sha256'] = digest_file(packet['qualifier_report'])
    write(packet['parent_receipt'], acceptance)
    contract = dict(schema_version=1, layout='matrixquota-closed110-v1',
                    role_root=str(role), measured_backend=str(packet['measured_backend']),
                    lineage=packet['expected_lineage'],
                    prepared_export={'path': str(packet['prepared_export']),
                                     'sha256': digest_file(packet['prepared_export'])},
                    parent_receipt={'path': str(packet['parent_receipt']),
                                    'sha256': digest_file(packet['parent_receipt'])})
    write(packet['contract'], contract)
    files = {str(path.relative_to(role)): dict(sha256=digest_file(path),
             bytes=path.stat().st_size, mode=path.stat().st_mode & 0o777)
             for path in sorted(role.rglob('*')) if path.is_file()}
    write(packet['inventory'], dict(schema_version=1, files=files))
    packet['expected_contract_sha256'] = digest_file(packet['contract'])
    packet['expected_inventory_sha256'] = digest_file(packet['inventory'])
    assert summary['manifest']['source_binding_sha256'] == packet['expected_lineage']['source_binding_sha256']


@pytest.fixture
def packet(tmp_path):
    role, backend = tmp_path / 'closed-role', tmp_path / 'measured/backend'
    for relative in PRODUCERS:
        destination = backend / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((BACKEND / relative).read_bytes())
    files = rr.collect_source_manifest(backend)
    binding = dict(schema_version=1, source_base_commit='a' * 40,
                   backend_files=files, backend_sha256=rr.digest(files))
    lineage = dict(source_base_commit=binding['source_base_commit'],
                   backend_sha256=binding['backend_sha256'],
                   source_binding_sha256=rr.digest(binding))
    rows = roster()
    for index, row in enumerate(rows):
        row['archetype'] = 'Aggro' if index % 2 else 'Control'
    export = rr.make_export(rows, corpus_sha256='c' * 64)
    rows = rr.validate_export(export)
    schedule = rr.build_schedule(rows, [1])
    contexts = {row['name']: row['archetype'] for row in rows}
    series = []
    for index, planned in enumerate(schedule):
        games = []
        for ordinal in (1, 2):
            context = contexts[planned['seat_two']].lower()
            raw = []
            for action_index in range(3):
                trace = dict(pid=1, player_name='Player A', action_index=action_index,
                             turn=2, opponent_archetype=context,
                             action=dict(type='cast_spell', card_name='Protocol Cast'))
                raw.extend(['AI TRACE ' + canonical(trace).decode(),
                            'Player A casts/activates Protocol Cast.'])
            raw_bytes = json.dumps(raw, ensure_ascii=True, separators=(',', ':'),
                                   allow_nan=False).encode()
            result = dict(winner=1, turn=2, ticks=3, log=deepcopy(raw),
                          log_hash=sha256('\n'.join(raw).encode()).hexdigest(),
                          timeout=False, starting_player=1 if ordinal == 1 else 2,
                          resource_limit_dimension=None, game_elapsed_seconds=0.01)
            reference = f'game-{ordinal:02d}.json'
            write(role / f'actual/workspace/private/series-{index:05d}' / reference,
                  dict(schema_version=1, result=result, raw_log=raw,
                       raw_sha256=sha256(raw_bytes).hexdigest()))
            quality = dict(counts={str(pid): dict.fromkeys(METRICS, 0) for pid in (1, 2)},
                           availability={str(pid): dict.fromkeys(METRICS, True) for pid in (1, 2)})
            game = {key: value for key, value in result.items() if key != 'log'}
            game.update(seed=planned['root_seed'] + ordinal - 1,
                        play_draw_chooser=result['starting_player'], quality=quality,
                        evidence_complete=True, evidence=dict(reference=reference, complete=True,
                            bytes=len(raw_bytes), raw_sha256=sha256(raw_bytes).hexdigest()))
            games.append(game)
        series.append(dict(planned, status='resolved', winner=1,
                           wins=dict(deck_a=2, deck_b=0), games=games))
    pairs = []
    for first in schedule[::2]:
        records = [row for row in series if (row['deck_a'], row['deck_b'], row['seed_token']) ==
                   (first['deck_a'], first['deck_b'], first['seed_token'])]
        quality = rr.quality_for_pair(records, metrics=METRICS)
        pairs.append(dict(deck_a=first['deck_a'], deck_b=first['deck_b'], seed=1,
                          **rr.summarize_pair(records, wilson=lambda *args: {}),
                          decision_quality_a=quality['deck_a'], decision_quality_b=quality['deck_b']))
    manifest = dict(export_sha256=rr.digest(export), input_export_base_commit=export['source_commit'],
        source_base_commit=binding['source_base_commit'], source_binding_sha256=rr.digest(binding),
        backend_before_sha256=binding['backend_sha256'], difficulty='strong', max_ticks=6000,
        limits=dict(RESOURCE_LIMITS), seeds=[1], sideboard_mode='fixed_no_swaps',
        planned_pairs=55, planned_series=110, effective_archetypes=contexts,
        roster=[dict(name=row['name'], classification_status=row['classification_status'],
            archetype=row['archetype'], content_sha256=rr.digest(row), mainboard_cards=60,
            sideboard_cards=1) for row in rows])
    write(role / 'actual/workspace/summary.json', dict(schema_version=1, manifest=manifest,
        measured_source=rr.source_closure(binding, backend, binding['backend_sha256']),
        attempted_series=110, not_run_series=0, complete=True, status='completed_schedule',
        pairs=pairs, series=series))
    write(role / 'inputs/CURRENT_SOURCE_BINDING.json', binding)
    write(role / 'inputs/ROLE.json', dict(source=str(backend.parent), active_source=str(backend),
        source_commit=binding['source_base_commit'], productive_limits=dict(RESOURCE_LIMITS),
        difficulty='strong', max_ticks=6000, seed_tokens=[1], sideboard_mode='fixed_no_swaps'))
    actor = dict(source_cli_exit=0, original_error=None, native_denials=[], guard_sticky=False,
                 guard_refusals=[], resources_equal=True, source_database_absent=True,
                 configured_database_absent=True)
    write(role / 'actual/workspace/actor_receipt.json', actor)
    write(role / 'actual/TERMINAL.json', dict(exit=0, runtime_envelope_qualified=True,
        checks=dict.fromkeys(CHECKS, True), actor_receipt=actor,
        independent_all110_resolved_qualification='PENDING_PARENT_AFTER_PHYSICAL_CLOSURE'))
    write(role / 'actual/RELEASE.json', dict(physical_closed=True, C_fd_closed=True,
        runtime_envelope_qualified=True, failure=None))
    write(role / 'UNIT_EXIT.json', dict(SERVICE_RESULT='success', EXIT_CODE='exited',
        EXIT_STATUS='0', workload_members_absent_at_ExecStopPost=True))
    for name in ('SOURCE', 'FULL_SOURCE', 'F', 'FULL_F', 'RUNTIME', 'SYSTEM',
                 'PREPARED', 'ROLE', 'APPROVAL'):
        value = {'synthetic_protocol_metadata': name, 'sha256': 'd' * 64}
        write(role / f'actual/{name}_BEFORE.json', value)
        write(role / f'actual/{name}_AFTER.json', value)
    prepared = write(tmp_path / 'prepared/inputs/export.json', export)
    # PROPOSED additive parent ABI, not a recovered historical success receipt.
    reader = tmp_path / 'parent/qualifier.py'
    reader.parent.mkdir(parents=True)
    reader.write_text('SYNTHETIC_PROTOCOL_ONLY = True\n')
    qualifier = write(tmp_path / 'parent/QUALIFIED.json', dict(schema_version=1,
        qualified=True, summary_sha256='0' * 64, lineage=lineage,
        counts=dict(series=110, pairs=55, games=220), errors=[]))
    parent = write(tmp_path / 'parent/ACCEPTANCE.json', dict(schema_version=1,
        kind='matrixquota-parent-acceptance-v1', qualified=True, physical_closed=True,
        cancelled=False, lineage=lineage, strict_qualifier_exit=0,
        strict_reader=dict(path=str(reader), sha256=digest_file(reader)),
        strict_report=dict(path=str(qualifier), sha256=digest_file(qualifier)),
        summary_sha256='0' * 64))
    result = dict(role_root=role, measured_backend=backend, expected_lineage=lineage,
                  contract=tmp_path / 'contract.json', inventory=tmp_path / 'inventory.json',
                  destination=tmp_path / 'private-export', prepared_export=prepared,
                  parent_receipt=parent, qualifier_report=qualifier)
    reseal(result)
    return result


def run_export(packet):
    path = BACKEND / 'scripts/export_closed_matrixquota_training.py'
    assert path.is_file(), 'Missing explicit closed MatrixQuota110 adapter'
    module = importlib.import_module('scripts.export_closed_matrixquota_training')
    return module.export_closed_matrixquota_training(**{key: packet[key] for key in (
        'role_root', 'contract', 'inventory', 'destination', 'measured_backend',
        'expected_lineage', 'expected_contract_sha256', 'expected_inventory_sha256')})


def assert_refused(packet):
    with pytest.raises((ValueError, OSError)):
        run_export(packet)
    assert not packet['destination'].exists()


def test_complete_synthetic_protocol_preserves_raw_and_cast_only_contexts(packet):
    report = run_export(packet)
    assert report['status'] == 'exported_private_training'
    assert report['games'] == 220 and report['qualified_casts'] == 660
    assert report['cast_context_eligible'] is True
    assert report['priors_saved'] is False and report['task33_complete'] is False
    actual = sorted(packet['destination'].glob('series-*/games.jsonl'))
    assert len(actual) == 110
    for index, path in enumerate(actual):
        games = [json.loads(line) for line in path.read_text().splitlines()]
        assert len(games) == 2
        for ordinal, game in enumerate(games, 1):
            capsule = read(packet['role_root'] /
                f'actual/workspace/private/series-{index:05d}/game-{ordinal:02d}.json')
            assert game['log'] == capsule['raw_log']
            assert game['game'] == f'game-{ordinal:02d}.json'


@pytest.mark.parametrize('fault', ['cancelled', 'unqualified', 'physical_unknown',
    'missing_terminal', 'actor_cli1', 'manager_signal', 'runtime_drift', 'qualifier_failed'])
def test_parent_or_runtime_refusal_precedes_any_private_capsule_read(packet, monkeypatch, fault):
    role = packet['role_root']
    if fault in ('cancelled', 'unqualified', 'physical_unknown'):
        value = read(packet['parent_receipt'])
        value[{'cancelled': 'cancelled', 'unqualified': 'qualified',
               'physical_unknown': 'physical_closed'}[fault]] = fault == 'cancelled'
        write(packet['parent_receipt'], value)
    elif fault == 'missing_terminal':
        (role / 'actual/TERMINAL.json').unlink()
    elif fault == 'actor_cli1':
        value = read(role / 'actual/workspace/actor_receipt.json')
        value['source_cli_exit'] = 1
        write(role / 'actual/workspace/actor_receipt.json', value)
    elif fault == 'manager_signal':
        write(role / 'UNIT_EXIT.json', dict(SERVICE_RESULT='success', EXIT_CODE='killed',
            EXIT_STATUS='TERM', workload_members_absent_at_ExecStopPost=True))
    elif fault == 'runtime_drift':
        write(role / 'actual/RUNTIME_AFTER.json', {'changed': True})
    else:
        value = read(packet['qualifier_report'])
        value['qualified'] = False
        write(packet['qualifier_report'], value)
    reseal(packet)
    delegate, opened = Path.read_bytes, []

    def observed(path):
        if path.is_relative_to(role / 'actual/workspace/private'):
            opened.append(path)
            raise AssertionError('Refused envelope must not read private capsules')
        return delegate(path)

    monkeypatch.setattr(Path, 'read_bytes', observed)
    assert_refused(packet)
    assert opened == []


@pytest.mark.parametrize('fault', ['empty', 'incomplete', 'resource_limit', 'duplicate',
                                 'reordered', 'seed', 'seat', 'one_game'])
def test_matrix_admission_refuses_incomplete_or_misindexed_protocol(packet, fault):
    path = packet['role_root'] / 'actual/workspace/summary.json'
    summary = read(path)
    if fault == 'incomplete':
        summary.update(complete=False, status='stopped', not_run_series=1)
    elif fault == 'resource_limit':
        summary['series'][0]['games'][0]['stop_reason'] = 'resource_limit'
    elif fault == 'duplicate':
        summary['series'][1] = deepcopy(summary['series'][0])
    elif fault == 'reordered':
        summary['series'][:2] = reversed(summary['series'][:2])
    elif fault == 'seed':
        summary['series'][0]['games'][0]['seed'] += 1
    elif fault == 'seat':
        summary['series'][0]['seat_one'] = summary['series'][0]['seat_two']
    elif fault == 'one_game':
        summary['series'][0]['games'].pop()
    write(path, summary)
    reseal(packet)
    if fault == 'empty':
        path.write_bytes(b'')
    assert_refused(packet)


@pytest.mark.parametrize('fault', ['contract_pin', 'inventory_pin', 'lineage',
                                 'capsule_bytes', 'missing_game', 'extra_game', 'symlink'])
def test_hash_lineage_and_exact_capsule_inventory_are_mandatory(packet, fault):
    game = packet['role_root'] / 'actual/workspace/private/series-00000/game-01.json'
    if fault == 'contract_pin':
        packet['expected_contract_sha256'] = '0' * 64
    elif fault == 'inventory_pin':
        packet['expected_inventory_sha256'] = '0' * 64
    elif fault == 'lineage':
        packet['expected_lineage'] = dict(packet['expected_lineage'], backend_sha256='0' * 64)
    elif fault == 'capsule_bytes':
        game.write_bytes(game.read_bytes() + b' ')
    elif fault == 'missing_game':
        game.unlink()
    elif fault == 'extra_game':
        write(game.with_name('game-03.json'), read(game))
        reseal(packet)
    else:
        target = game.with_name('retained.json')
        game.rename(target)
        game.symlink_to(target)
    assert_refused(packet)


def test_existing_destination_is_never_modified(packet):
    packet['destination'].mkdir()
    marker = packet['destination'] / 'retained.txt'
    marker.write_bytes(b'unchanged')
    with pytest.raises((ValueError, OSError)):
        run_export(packet)
    assert marker.read_bytes() == b'unchanged'


def rewrite_actions(packet, change):
    """Edit synthetic protocol lines and all dependent hashes, not real data."""
    role = packet['role_root']
    summary_path = role / 'actual/workspace/summary.json'
    summary = read(summary_path)
    for index, series in enumerate(summary['series']):
        for ordinal, game in enumerate(series['games'], 1):
            path = role / f'actual/workspace/private/series-{index:05d}/game-{ordinal:02d}.json'
            capsule = read(path)
            raw = capsule['raw_log']
            for offset in range(0, len(raw), 2):
                trace = json.loads(raw[offset].removeprefix('AI TRACE '))
                change(trace, index)
                raw[offset] = 'AI TRACE ' + canonical(trace).decode()
                name = trace['action'].get('card_name', 'Protocol Cast')
                raw[offset + 1] = ('Player A casts/activates ' + name + '.'
                    if trace['action']['type'] in ('cast_spell', 'activate_ability')
                    else 'Player A passes priority.')
            raw_bytes = json.dumps(raw, ensure_ascii=True, separators=(',', ':'),
                                   allow_nan=False).encode()
            capsule['raw_sha256'] = sha256(raw_bytes).hexdigest()
            capsule['result']['log'] = deepcopy(raw)
            capsule['result']['log_hash'] = sha256('\n'.join(raw).encode()).hexdigest()
            write(path, capsule)
            game['log_hash'] = capsule['result']['log_hash']
            game['evidence'].update(bytes=len(raw_bytes), raw_sha256=capsule['raw_sha256'])
    write(summary_path, summary)
    reseal(packet)


@pytest.mark.parametrize('fault', ['activation_only', 'one_context_per_card',
                                 'two_casts_per_context', 'duplicate_action',
                                 'wrong_physical_context', 'missing_announced_name'])
def test_ineligible_or_conflicting_cast_provenance_never_exports(packet, fault):
    kept = {}

    def change(trace, index):
        if fault == 'activation_only':
            trace['action'] = dict(type='activate_ability', card_name='Protocol Activation ability')
        elif fault == 'one_context_per_card':
            trace['action']['card_name'] = f'Protocol Cast {index}'
        elif fault == 'two_casts_per_context':
            context = trace['opponent_archetype']
            kept[context] = kept.get(context, 0) + 1
            if kept[context] > 2:
                trace['action'] = dict(type='activate_ability', card_name='Protocol Activation ability')
        elif fault == 'duplicate_action':
            trace['action_index'] = 0
        elif fault == 'wrong_physical_context':
            trace['opponent_archetype'] = 'ramp'
        else:
            trace['action'].pop('card_name')

    rewrite_actions(packet, change)
    assert_refused(packet)


def test_exact_three_casts_in_each_of_two_contexts_excludes_activation_counts(packet):
    kept = {}

    def change(trace, index):
        context = trace['opponent_archetype']
        kept[context] = kept.get(context, 0) + 1
        if kept[context] > 3:
            trace['action'] = dict(type='activate_ability', card_name='Protocol Activation ability')

    rewrite_actions(packet, change)
    report = run_export(packet)
    assert report['qualified_casts'] == 6 and report['cast_context_eligible'] is True
    assert report['eligible_card_context_counts'] == {'protocol cast': {'aggro': 3, 'control': 3}}
    assert report['priors_saved'] is False and report['task33_complete'] is False


# Additive synthetic protocol controls; append to the sealed draft test module.
# STATIC/UNRUN. These fixtures are not authentic execution or training evidence.
@pytest.mark.parametrize('field', ['expected_contract_sha256',
                                 'expected_inventory_sha256', 'expected_lineage'])
def test_untrusted_self_described_success_without_caller_anchor_refuses(packet, monkeypatch, field):
    packet[field] = None
    private = packet['role_root'] / 'actual/workspace/private'
    delegate, opened = Path.read_bytes, []

    def observed(path):
        if path.is_relative_to(private):
            opened.append(path)
            raise AssertionError('Missing trust anchor must precede private payload reads')
        return delegate(path)

    monkeypatch.setattr(Path, 'read_bytes', observed)
    assert_refused(packet)
    assert opened == []


def test_changed_parent_receipt_is_not_reapproved_by_its_qualified_flag(packet, monkeypatch):
    value = read(packet['parent_receipt'])
    value.update(qualified=True, physical_closed=False)
    write(packet['parent_receipt'], value)
    # Deliberately do not reseal the contract: the reader cannot approve its own input.
    private = packet['role_root'] / 'actual/workspace/private'
    delegate, opened = Path.read_bytes, []

    def observed(path):
        if path.is_relative_to(private):
            opened.append(path)
            raise AssertionError('Stale parent seal must precede private payload reads')
        return delegate(path)

    monkeypatch.setattr(Path, 'read_bytes', observed)
    assert_refused(packet)
    assert opened == []


def test_actual_measured_source_bytes_must_match_approved_binding(packet):
    path = packet['measured_backend'] / PRODUCERS[0]
    path.write_bytes(path.read_bytes() + b'\n# Synthetic protocol source drift.\n')
    assert_refused(packet)


@pytest.mark.parametrize('fault', ['missing_action_index', 'missing_player_name',
                                 'action_index_beyond_ticks'])
def test_native_identity_is_not_inferred_or_accepted_outside_game_ticks(packet, fault):
    def change(trace, index):
        if fault == 'missing_action_index':
            trace.pop('action_index')
        elif fault == 'missing_player_name':
            trace.pop('player_name')
        else:
            # Three distinct indices, all outside this protocol game's ticks=3.
            trace['action_index'] += 3

    rewrite_actions(packet, change)
    assert_refused(packet)


def test_success_preserves_all_inputs_and_does_not_save_source_priors(packet):
    paths = [path for path in packet['role_root'].rglob('*') if path.is_file()]
    paths.extend(path for path in packet['measured_backend'].rglob('*') if path.is_file())
    acceptance = read(packet['parent_receipt'])
    paths.extend([packet['contract'], packet['inventory'], packet['prepared_export'],
                  packet['parent_receipt'], packet['qualifier_report'],
                  Path(acceptance['strict_reader']['path']), BACKEND / 'ai/data/log_priors.json'])
    before = {str(path): (digest_file(path), path.stat().st_mode & 0o777) for path in paths}
    report = run_export(packet)
    after = {str(path): (digest_file(path), path.stat().st_mode & 0o777) for path in paths}
    assert before == after
    assert report['priors_saved'] is False and report['task33_complete'] is False
    assert packet['destination'].stat().st_mode & 0o777 == 0o700
    outputs = list(packet['destination'].rglob('*.jsonl'))
    assert outputs and all(path.stat().st_mode & 0o777 == 0o600 for path in outputs)
