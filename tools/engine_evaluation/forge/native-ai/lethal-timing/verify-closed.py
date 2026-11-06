#!/usr/bin/env python3
"""Offline case00 evidence verification. No engine queries, playback or state repair."""
import hashlib
import json
import re
import sys
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def prefix(a, b):
    return next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))


def elapsed_only(a, b):
    assert len(a) == len(b)
    differences = []
    for i, (x, y) in enumerate(zip(a, b), 1):
        if x == y:
            continue
        assert x['type'] == y['type'] == 'GAME_OUTCOME' and x['game'] == y['game']
        assert all(re.fullmatch(r'Match Duration \d+m : \d+s', row['message']) for row in (x, y))
        differences.append({'line': i, 'before': x['message'], 'after': y['message']})
    return differences


original, root = (Path(value).resolve() for value in sys.argv[1:])
baseline, candidate = root/'natural-baseline', root/'natural-final'
for run in [original, baseline, candidate]:
    result = json.loads((run/'RESULT.json').read_text())
    assert result['exit'] == 0 and result['qualified_completed_series'] is True
    assert sha(run/'SPEC.json') == sha(original/'SPEC.json')
    for name in ['seat0.dck', 'seat1.dck']:
        assert sha(run/'decks'/name) == sha(original/'decks'/name)
    if run != original:
        pins = json.loads((run/'INPUT-PINS.json').read_text())
        assert all(sha(Path(path)) == digest for path, digest in pins.items())
        events = [json.loads(line[len('@@MTG_PROBE_JSON '):])
                  for line in (run/'stdout.private.log').read_text().splitlines()
                  if line.startswith('@@MTG_PROBE_JSON ')]
        assert events[-1]['kind'] == 'native_match_complete'
        started = next(event for event in events if event['kind'] == 'match_started')
        assert started['filtered_hands'] is False and started['corrected_naming'] is True
        assert started['seed'] == 2026110602 and started['open_decklists'] is True
        assert all(event['enabled'] is False and event['decisions'] == event['rollouts'] == 0
                   for event in events if event['kind'] == 'native_search_stats')
        assert not re.search(r'TimeoutException|AI eval thread at timeout|AITimeoutTracker\$Expired',
                             (run/'stderr.private.log').read_text())

original_logs = rows(original/'game-logs.private.jsonl')
baseline_logs = rows(baseline/'game-logs.private.jsonl')
candidate_logs = rows(candidate/'game-logs.private.jsonl')
original_views = rows(original/'actor-observations.private.jsonl')
baseline_views = rows(baseline/'actor-observations.private.jsonl')
candidate_views = rows(candidate/'actor-observations.private.jsonl')
assert original_views == baseline_views
baseline_elapsed = elapsed_only(original_logs, baseline_logs)
log_prefix = prefix(baseline_logs, candidate_logs)
view_prefix = prefix(baseline_views, candidate_views)
assert log_prefix == 360 and view_prefix == 348
decision = candidate_views[view_prefix - 1]
assert decision['actor'] == 0 and decision['game'] == 0
assert decision['view']['turn'] == 16 and decision['phase'] == 'UPKEEP'
players = {player['player_id']: player for player in decision['view']['players']}
assert players[0]['life'] == 6 and players[1]['life'] == 4
assert any(card['card_id'] == 28 and card['face']['name'] == 'Boros Charm'
           for card in players[0]['zones']['Hand']['visible_cards'])
expected = [
    ('MANA', 'Plateau (36) - {T}: Add {R}.'),
    ('MANA', 'Plains (40) - {T}: Add {W}.'),
    ('STACK_ADD', 'Burn cast Boros Charm'),
    ('DAMAGE', 'Boros Charm (28) deals 4 non-combat damage to White Weenie.'),
    ('LIFE', 'Life: White Weenie 4 > 0'),
    ('STACK_RESOLVE', 'Boros Charm (28) -  Boros Charm deals 4 damage to target player or planeswalker. (Targeting: White Weenie)'),
]
assert [(row['type'], row['message']) for row in candidate_logs[log_prefix:log_prefix+6]] == expected
candidate_result = json.loads((candidate/'RESULT.json').read_text())
assert [game['turns'] for game in candidate_result['games']] == [16, 12]
assert all(game['outcomes'] == ['Burn has won because all opponents have lost',
                               'White Weenie has lost because life total reached 0']
           for game in candidate_result['games'])
manifest = json.loads((root/'infect-guarded/MANIFEST.json').read_text())
payload = manifest['identity']['payload']
assert sha(root/'infect-guarded/shadow'/payload['path']) == payload['sha256']
origins = {}
for line in (candidate/'class-load.log').read_text().splitlines():
    found = re.search(r'\] (forge\.[\w.$]+) source: file:(.*)$', line)
    if found:
        origins[found[1]] = found[2].rstrip('/')
cohort = json.loads((original.parent/'COHORT.json').read_text())
for item in cohort['native_classes']:
    origin = Path(origins[item['class_name']])
    assert origin == Path(cohort['CP'][1])
    assert sha(origin/item['path']) == item['sha256']
assert Path(origins['forge.ai.ability.DamageDealAi']) == root/'infect-guarded/shadow'
assert Path(origins['forge.evaluation.NativeNameMatchProbe']) == original.parent/'classes'
assert Path(origins['forge.evaluation.PublicNameController']) == Path(cohort['CP'][2])
report = {
    'scope': 'One declared natural case00 series, not broad quality or coupled app qualification',
    'baseline_original_actor_observations_equal': len(baseline_views),
    'baseline_original_elapsed_only_differences': baseline_elapsed,
    'candidate_exact_common_log_prefix': log_prefix,
    'candidate_exact_common_actor_prefix': view_prefix,
    'first_changed_decision': {'game': 0, 'native_turn': 16, 'phase': 'UPKEEP', 'actor': 0,
                               'life': 6, 'enemy_life': 4, 'card_id': 28},
    'old_turn18_position_not_reached': True,
    'payment_resolution_evidence': [{'line': log_prefix+i+1, **row}
                                    for i, row in enumerate(candidate_logs[log_prefix:log_prefix+6])],
    'natural_games': [{'turns': game['turns'], 'outcomes': game['outcomes']}
                      for game in candidate_result['games']],
    'product_identity': manifest,
    'loaded_class_origins': {name: origins[name] for name in ['forge.ai.ability.DamageDealAi',
        'forge.ai.ComputerUtil', 'forge.ai.ComputerUtilCost', 'forge.ai.ComputerUtilMana',
        'forge.evaluation.NativeNameMatchProbe', 'forge.evaluation.PublicNameController']},
    'snapshot_limit': 'No mana-pool or log-index field: payment is proved by native mana/cast/damage logs, not invented snapshot alignment.',
}
intermediate = root/'natural-candidate'
if intermediate.exists():
    assert rows(intermediate/'actor-observations.private.jsonl') == candidate_views
    report['pre_infect_guard_natural_trace_elapsed_only_differences'] = elapsed_only(
        rows(intermediate/'game-logs.private.jsonl'), candidate_logs)
(root/'evidence/VERIFIED-NATURAL.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({key: report[key] for key in ['candidate_exact_common_log_prefix',
    'candidate_exact_common_actor_prefix', 'first_changed_decision', 'natural_games']}, indent=2))
