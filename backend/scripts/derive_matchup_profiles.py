"""Offline complete Task 3.1 evidence -> bounded advisory profiles, not strength proof."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import json
from pathlib import Path

from ai.matchup_profiles import EXPECTED_LINEAGE, advisory_profile, artifact_digest
from analytics.resource_budget import RESOURCE_LIMITS
from decks.selection import _ARCHETYPE_PRIORITY
from scripts import matchup_round_robin as rr

METRICS = ('missed_land_drops', 'unused_mana_passes', 'lethal_misses',
           'bad_blocks', 'stall_streaks', 'redundant_removal_casts')


def _require(ok, reason):
    if not ok:
        raise ValueError(reason)


def _integer(value, low=0, high=None):
    return type(value) is int and value >= low and (high is None or value <= high)


def _sha(value):
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def _key(row):
    return row['deck_a'], row['deck_b'], row['seed_token'], row['deck_a_seat']


def _admit(summary, export, binding, backend, lineage):
    rows = rr.validate_export(export)
    rr.verify_source_binding(binding, backend)
    actual = dict(source_base_commit=binding['source_base_commit'], backend_sha256=binding['backend_sha256'],
                  source_binding_sha256=rr.digest(binding))
    _require(rr.canonical_bytes(actual) == rr.canonical_bytes(lineage), 'Unexpected measurement lineage')
    _require(type(summary) is dict and type(summary.get('schema_version')) is int
             and summary['schema_version'] == 1 and summary.get('complete') is True
             and summary.get('status') == 'completed_schedule', 'Complete executed matrix required')
    manifest = summary.get('manifest')
    _require(type(manifest) is dict and manifest.get('source_base_commit') == actual['source_base_commit']
             and manifest.get('source_binding_sha256') == actual['source_binding_sha256']
             and manifest.get('backend_before_sha256') == actual['backend_sha256']
             and manifest.get('export_sha256') == rr.digest(export)
             and manifest.get('input_export_base_commit') == export['source_commit']
             and manifest.get('sideboard_mode') == 'fixed_no_swaps'
             and manifest.get('difficulty') in ('casual', 'strong', 'master')
             and _integer(manifest.get('max_ticks'), 1), 'Manifest/lineage mismatch')
    limits = manifest.get('limits')
    _require(type(limits) is dict and set(limits) == set(RESOURCE_LIMITS)
             and all(_integer(value, 0, RESOURCE_LIMITS[key]) for key, value in limits.items()),
             'Original complete resource contract required')
    closure = summary.get('measured_source')
    _require(type(closure) is dict and closure.get('equal') is True
             and closure.get('source_base_commit') == actual['source_base_commit']
             and closure.get('binding_sha256') == actual['source_binding_sha256']
             and closure.get('before_sha256') == closure.get('after_sha256') == actual['backend_sha256']
             and type(closure.get('ordinary_files')) is int
             and closure['ordinary_files'] == len(binding['backend_files']), 'Unclosed measurement source')
    allowed = {name.lower() for name in _ARCHETYPE_PRIORITY} - {'unknown'}
    _require(all(row['classification_status'] == 'resolved' and row['archetype'].strip().lower() in allowed
                 for row in rows), 'Unknown archetype classification')
    roster = [dict(name=row['name'], classification_status=row['classification_status'], archetype=row['archetype'],
                   content_sha256=rr.digest(row), mainboard_cards=sum(c['quantity'] for c in row['mainboard']),
                   sideboard_cards=sum(c['quantity'] for c in row['sideboard'])) for row in rows]
    _require(rr.canonical_bytes(manifest.get('roster')) == rr.canonical_bytes(roster), 'Full roster mismatch')
    schedule = rr.build_schedule(rows, manifest.get('seeds'))
    _require(_integer(manifest.get('planned_pairs')) and manifest['planned_pairs'] == len(rows)*(len(rows)-1)//2
             and _integer(manifest.get('planned_series')) and manifest['planned_series'] == len(schedule)
             and _integer(summary.get('attempted_series')) and summary['attempted_series'] == len(schedule)
             and type(summary.get('not_run_series')) is int and summary['not_run_series'] == 0,
             'Full planned matrix required')
    series = summary.get('series')
    _require(type(series) is list and len(series) == len(schedule), 'Incomplete series')
    expected = {_key(row): row for row in schedule}
    seen = set()
    for row in series:
        _require(type(row) is dict and row.get('status') == 'resolved'
                 and _integer(row.get('winner'), 1, 2) and _integer(row.get('deck_a_seat'), 1, 2)
                 and _integer(row.get('seed_token')), 'Unresolved/invalid series')
        key = _key(row)
        _require(key in expected and key not in seen and rr.canonical_bytes(
            {field: row.get(field) for field in expected[key]}) == rr.canonical_bytes(expected[key]),
            'Missing/duplicate/mismatched mirrored schedule')
        seen.add(key)
        games = row.get('games')
        _require(type(games) is list and 2 <= len(games) <= 6, 'Complete BO3 games required')
        wins, chooser = Counter(), 1
        for index, game in enumerate(games):
            _require(type(game) is dict and _integer(game.get('winner'), 0, 2)
                     and game.get('timeout') is False and game.get('stop_reason') is None
                     and game.get('quality_available', True) is True
                     and game.get('quality_unavailable_reason') is None
                     and _integer(game.get('ticks'), 0, manifest['max_ticks']) and _integer(game.get('turn'))
                     and type(game.get('seed')) is int and game['seed'] == row['root_seed'] + index
                     and type(game.get('starting_player')) is int and game['starting_player'] == chooser
                     and type(game.get('play_draw_chooser')) is int and game['play_draw_chooser'] == chooser
                     and _sha(game.get('log_hash')), 'Invalid/unresolved game')
            receipt = game.get('evidence')
            _require(game.get('evidence_complete') is True and type(receipt) is dict
                     and set(receipt) == {'complete', 'bytes', 'raw_sha256', 'reference'}
                     and receipt['complete'] is True and _integer(receipt['bytes'], 1)
                     and _sha(receipt['raw_sha256']) and receipt['reference'] == f'game-{index+1:02d}.json',
                     'Incomplete sanitized evidence receipt')
            quality = game.get('quality')
            _require(type(quality) is dict and type(quality.get('counts')) is dict
                     and type(quality.get('availability')) is dict, 'Quality evidence unavailable')
            for pid in ('1', '2'):
                counts, available = quality['counts'].get(pid), quality['availability'].get(pid)
                _require(type(counts) is dict and type(available) is dict
                         and all(_integer(counts.get(metric)) and available.get(metric) is True for metric in METRICS),
                         'Complete typed per-player quality required')
            if game['winner']:
                wins[game['winner']] += 1
                chooser = 3 - game['winner']
            _require(index == len(games)-1 or max(wins.values(), default=0) < 2, 'Game after terminal series')
        _require(wins[row['winner']] == 2 and rr.canonical_bytes(row.get('wins')) == rr.canonical_bytes(
            {'deck_a': wins[1], 'deck_b': wins[2]}), 'Player-indexed BO3 wins mismatch')
    pairs = summary.get('pairs')
    _require(type(pairs) is list and len(pairs) == len(schedule)//2, 'Missing pair summaries')
    pair_seen = set()
    for pair in pairs:
        _require(type(pair) is dict and _integer(pair.get('seed')), 'Invalid pair seed')
        key = pair.get('deck_a'), pair.get('deck_b'), pair['seed']
        records = [row for row in series if (row['deck_a'], row['deck_b'], row['seed_token']) == key]
        _require(len(records) == 2 and key not in pair_seen, 'Missing/duplicate pair summary')
        pair_seen.add(key)
        expected_pair = rr.summarize_pair(records, wilson=lambda *args: {})
        for field in ('wins_a', 'wins_b', 'resolved_series', 'attempted_series', 'timeouts',
                      'unresolved', 'unavailable_reason', 'inference'):
            _require(rr.canonical_bytes(pair.get(field)) == rr.canonical_bytes(expected_pair[field]), 'Pair count mismatch')
        quality = rr.quality_for_pair(records, metrics=METRICS)
        _require(rr.canonical_bytes(pair.get('decision_quality_a')) == rr.canonical_bytes(quality['deck_a'])
                 and rr.canonical_bytes(pair.get('decision_quality_b')) == rr.canonical_bytes(quality['deck_b']),
                 'Pair player-quality mismatch')
    return rows, series


def derive_profiles(summary, export, source_binding, *, measured_backend, expected_lineage):
    """All-or-nothing admission; never execute games or read private game records."""
    try:
        rows, series = _admit(summary, export, source_binding, measured_backend, expected_lineage)
    except (KeyError, TypeError, OverflowError) as error:
        raise ValueError('Malformed Task 3.1 input') from error
    archetypes = {row['name']: row['archetype'].strip().lower() for row in rows}
    samples = defaultdict(dict)
    for row in series:
        for own, opp, pid in ((row['deck_a'], row['deck_b'], row['deck_a_seat']),
                              (row['deck_b'], row['deck_a'], 3-row['deck_a_seat'])):
            key, other = archetypes[own], archetypes[opp]
            sample = samples[key].setdefault(other, dict(series=0, wins=0, games=0,
                    quality=dict.fromkeys(METRICS, 0), opponent_quality=dict.fromkeys(METRICS, 0)))
            sample['series'] += 1
            sample['wins'] += row['winner'] == pid
            sample['games'] += len(row['games'])
            for game in row['games']:
                for metric in METRICS:
                    sample['quality'][metric] += game['quality']['counts'][str(pid)][metric]
                    sample['opponent_quality'][metric] += game['quality']['counts'][str(3-pid)][metric]
    profiles = {}
    for own, pairs in sorted(samples.items()):
        profiles[own] = {}
        for opp, sample in sorted(pairs.items()):
            profiles[own][opp] = advisory_profile(own, opp, sample)
    # Pair/series ordering is not evidence identity; game chronology remains exact.
    normalized_summary = {**summary, 'series': sorted(summary['series'], key=_key),
                          'pairs': sorted(summary['pairs'], key=lambda row: (row['deck_a'], row['deck_b'], row['seed']))}
    output = dict(schema_version=1, qualified=True, lineage=deepcopy(expected_lineage),
                  export_sha256=rr.digest(export), summary_sha256=rr.digest(normalized_summary),
                  coverage=dict(builtin_decks=len(rows), builtin_pairs=len(rows)*(len(rows)-1)//2,
                                seed_tokens=len(summary['manifest']['seeds']),
                                roster_schema_version=1, roster_archetypes=archetypes),
                  counts=dict(resolved_series=len(series), resolved_games=sum(len(row['games']) for row in series)),
                  interpretation='descriptive advisory; mirrored seeds dependent; no causal/strength certification',
                  profiles=profiles, samples=dict(samples))
    output['artifact_sha256'] = artifact_digest(output)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('summary', 'deck-export', 'source-binding', 'measured-backend', 'output'):
        parser.add_argument('--'+name, required=True)
    args = parser.parse_args()
    read = lambda path: json.loads(Path(path).read_text(encoding='utf-8'))
    output, measured = Path(args.output), Path(args.measured_backend)
    if (output.resolve().is_relative_to(measured.resolve())
            or any(parent.is_symlink() for parent in output.absolute().parents)):
        raise ValueError('Output must be outside the readonly measured source, without symlink parents')
    # Reserve the original path before reading inputs. Never follow a dangling
    # output leaf by opening its resolved target, or erase a failed reservation.
    with output.open('xb') as handle:
        result = derive_profiles(read(args.summary), read(args.deck_export), read(args.source_binding),
                                 measured_backend=measured, expected_lineage=EXPECTED_LINEAGE)
        handle.write(rr.canonical_bytes(result) + b'\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
