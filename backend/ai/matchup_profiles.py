from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from functools import lru_cache
from itertools import combinations
from pathlib import Path
from decks.builtin_decks import BUILTIN_DECKS
from decks.selection import _ARCHETYPE_PRIORITY

PROFILE_PATH = Path(__file__).resolve().parent / 'data' / 'matchup_profiles.json'
PROFILE_KEYS = frozenset(('proactive_bias', 'holdup_bias', 'risk_tolerance'))
QUALITY_KEYS = ('missed_land_drops', 'unused_mana_passes', 'lethal_misses',
                'bad_blocks', 'stall_streaks', 'redundant_removal_casts')
# Reviewed measurement lineage, NOT a hash of the newly installed consumer.
EXPECTED_LINEAGE = {
    'source_base_commit': '7c5e933a73755b53da5efd50159c1bb248cf4906',
    'backend_sha256': '57b0b0e28dfa2896b14b52505e8b978da4a6cc3c65202a86b738419101c9003c',
    'source_binding_sha256': '7059b869b0a7693a8d4a463dffc44e39e45708280e56854c499218f2dedd59ce',
}


def artifact_digest(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def advisory_profile(own, opp, sample):
    """Typed descriptive transform shared by derivation and artifact validation."""
    if (type(sample) is not dict or set(sample) != {'series', 'wins', 'games', 'quality', 'opponent_quality'}
            or any(type(sample[k]) is not int for k in ('series', 'wins', 'games'))
            or sample['series'] <= 0 or not 0 <= sample['wins'] <= sample['series']
            or not 2*sample['series'] <= sample['games'] <= 6*sample['series']):
        raise ValueError('Malformed matchup sample')
    ours, theirs = sample['quality'], sample['opponent_quality']
    if any(type(q) is not dict or set(q) != set(QUALITY_KEYS)
           or any(type(value) is not int or value < 0 for value in q.values()) for q in (ours, theirs)):
        raise ValueError('Unavailable typed quality totals')
    def gap(metrics):
        a, b = sum(ours[m] for m in metrics), sum(theirs[m] for m in metrics)
        return (b-a)/(1+a+b)
    def clamp(value, bound):
        return max(-bound, min(bound, value))
    margin = sample['wins']/sample['series'] - 0.5
    delta = dict(proactive_bias=clamp(margin + 0.25*gap(('unused_mana_passes',)), 0.5),
                 holdup_bias=clamp(-0.25*gap(('redundant_removal_casts',)), 0.25),
                 risk_tolerance=clamp(0.25*gap(('bad_blocks', 'lethal_misses')), 0.25))
    legacy = _legacy_profile_for(own, opp)
    return {key: round(float(clamp(legacy[key]+value, 2.0)), 6) for key, value in delta.items()}


def load_profiles(path, *, expected_lineage=None):
    """Read an explicitly reviewed measurement epoch; malformed data falls back."""
    lineage = EXPECTED_LINEAGE if expected_lineage is None else expected_lineage
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        if (type(data) is not dict or data.get('schema_version') != 1
                or type(data['schema_version']) is not int or data.get('qualified') is not True
                or data.get('lineage') != lineage
                or type(data.get('coverage')) is not dict
                or type(data['coverage'].get('builtin_decks')) is not int or data['coverage']['builtin_decks'] != 11
                or type(data['coverage'].get('builtin_pairs')) is not int or data['coverage']['builtin_pairs'] != 55
                or type(data['coverage'].get('seed_tokens')) is not int
                or data['coverage']['seed_tokens'] < 1
                or data.get('artifact_sha256') != artifact_digest(
                    {key: value for key, value in data.items() if key != 'artifact_sha256'})):
            return {}
        profiles = data.get('profiles')
        samples, counts = data.get('samples'), data.get('counts')
        if (type(profiles) is not dict or not profiles or type(samples) is not dict or set(samples) != set(profiles)
                or type(counts) is not dict or set(counts) != {'resolved_series', 'resolved_games'}
                or any(type(value) is not int for value in counts.values())
                or counts['resolved_series'] != 110*data['coverage']['seed_tokens']
                or not 2*counts['resolved_series'] <= counts['resolved_games'] <= 6*counts['resolved_series']):
            return {}
        allowed = {name.lower() for name in _ARCHETYPE_PRIORITY} - {'unknown'}
        coverage = data['coverage']
        roster = coverage.get('roster_archetypes')
        if (type(coverage.get('roster_schema_version')) is not int or coverage['roster_schema_version'] != 1
                or type(roster) is not dict or set(roster) != set(BUILTIN_DECKS)
                or any(type(value) is not str or value not in allowed for value in roster.values())):
            return {}
        expected_pairs = Counter()
        for left, right in combinations(sorted(roster), 2):
            # Every physical mirrored series contributes both participant directions.
            expected_pairs[roster[left], roster[right]] += 2*coverage['seed_tokens']
            expected_pairs[roster[right], roster[left]] += 2*coverage['seed_tokens']
        if {(own, opp) for own, pairs in profiles.items() for opp in pairs} != set(expected_pairs):
            return {}
        totals = dict(series=0, wins=0, games=0)
        for own, pairs in profiles.items():
            if (type(own) is not str or own not in allowed or type(pairs) is not dict or not pairs
                    or type(samples[own]) is not dict or set(samples[own]) != set(pairs)):
                return {}
            for opp, values in pairs.items():
                if (type(opp) is not str or opp not in allowed
                        or type(values) is not dict or set(values) != PROFILE_KEYS
                        or any(type(value) is not float or not math.isfinite(value) or not -2 <= value <= 2
                               for value in values.values())):
                    return {}
                sample = samples[own][opp]
                if values != advisory_profile(own, opp, sample):
                    return {}
                if sample['series'] != expected_pairs[own, opp]:
                    return {}
                for key in totals:
                    totals[key] += sample[key]
        for own, pairs in samples.items():
            for opp, sample in pairs.items():
                reverse = samples[opp][own]
                if (sample['series'] != reverse['series'] or sample['games'] != reverse['games']
                        or sample['wins'] + reverse['wins'] != sample['series']
                        or sample['quality'] != reverse['opponent_quality']
                        or sample['opponent_quality'] != reverse['quality']
                        or own == opp and (sample['series'] % 2 or sample['games'] % 2)):
                    return {}
        if totals != dict(series=2*counts['resolved_series'], wins=counts['resolved_series'],
                          games=2*counts['resolved_games']):
            return {}
        return profiles
    except (OSError, UnicodeError, ValueError, KeyError, TypeError):
        return {}


@lru_cache(maxsize=1)
def _load_profile_table():
    # One immutable process-local data view, never DB/Git/source hashing in search.
    return load_profiles(PROFILE_PATH)


def profile_for(own_archetype: str, opp_archetype: str | None) -> dict[str, float]:
    own = (own_archetype or '').strip().lower()
    opp = (opp_archetype or '').strip().lower()
    learned = _load_profile_table().get(own, {}).get(opp)
    return dict(learned) if learned is not None else _legacy_profile_for(own_archetype, opp_archetype)


def _legacy_profile_for(own_archetype: str, opp_archetype: str | None) -> dict[str, float]:
    own = (own_archetype or "").strip().lower()
    opp = (opp_archetype or "").strip().lower()
    profile = {
        "proactive_bias": 0.0,
        "holdup_bias": 0.0,
        "risk_tolerance": 0.0,
    }
    if own in {"control", "counter-heavy"}:
        profile["holdup_bias"] += 0.8
        if opp in {"control", "counter-heavy"}:
            profile["proactive_bias"] += 0.8
        elif opp in {"tempo", "aggro", "burn"}:
            profile["holdup_bias"] += 0.5
            profile["risk_tolerance"] -= 0.1
        elif opp in {"tokens", "tribal", "drain", "aristocrats"}:
            profile["proactive_bias"] += 0.4
            profile["risk_tolerance"] += 0.2
    if own in {"aggro", "burn", "tribal", "tokens"}:
        profile["proactive_bias"] += 0.9
        profile["risk_tolerance"] += 0.5
    if own in {"ramp", "midrange"} and opp in {"control", "counter-heavy"}:
        profile["proactive_bias"] += 0.8
    if own in {"ramp", "midrange"} and opp in {"aggro", "burn", "tempo"}:
        profile["holdup_bias"] += 0.5
        profile["risk_tolerance"] -= 0.2
    if own in {"tempo"} and opp in {"ramp", "midrange"}:
        profile["holdup_bias"] += 0.3
        profile["proactive_bias"] += 0.4
    if own in {"tempo"} and opp in {"control", "counter-heavy"}:
        profile["proactive_bias"] += 0.5
        profile["risk_tolerance"] += 0.2
    if own in {"combo-lite"}:
        profile["proactive_bias"] += 0.6
        profile["risk_tolerance"] += 0.15
        if opp in {"control", "counter-heavy", "tempo"}:
            profile["proactive_bias"] += 0.4
            profile["risk_tolerance"] += 0.1
        if opp in {"aggro", "burn"}:
            profile["holdup_bias"] += 0.2
    return profile
