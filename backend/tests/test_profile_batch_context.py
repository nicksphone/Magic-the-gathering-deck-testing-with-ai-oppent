"""Batch-local work reuse; PUBLIC canonical data, no Repository/SQL/game execution."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from knowledge import profiles
from scripts import sync_corpus_cards as sync

LEGACY_DERIVE = "def derive_profile(card, corpus=(), *, archetype=None):\n    raw = _raw(card)\n    corpus = tuple(corpus)\n    if len(corpus) > MAX_CORPUS: raise ValueError('Corpus limit exceeded')\n    deck = [{'quantity': item.get('quantity', 1), 'card_metadata': _raw(item.get('card_metadata') or item)} for item in corpus]\n    if any(type(item['quantity']) is not int or not 0 <= item['quantity'] <= 1000 for item in deck):\n        raise ValueError('Invalid corpus quantity')\n    analysis = analyze_deck(deck) if deck else None\n    costs = [(_cmc(item['card_metadata'].get('mana_cost') or ''), item['quantity']) for item in deck\n             if 'land' not in printed_card_types(item['card_metadata'].get('type_line', ''))]\n    count = sum(q for _, q in costs)\n    curve = sum(mv*q for mv,q in costs)/count if count else None\n    context = {'mode': 'supplied_archetype' if archetype and deck else 'supplied_corpus' if deck else 'printed_only',\n        'archetype': archetype, 'archetype_verification': 'caller_declared_not_verified',\n        'corpus_fingerprint': _hash(deck), 'curve_nonland_mean': curve,\n        'deck_analysis_primary_archetype_estimate': analysis['primary_archetype'] if analysis else None}\n    faces = tuple(_face(_raw(face), i, curve) for i,face in enumerate(raw.get('card_faces') or []))\n    root_types = printed_card_types(raw.get('type_line', ''), raw.get('types'))\n    combined_parent = '//' in (raw.get('type_line') or '')\n    main = faces[0] if faces and (combined_parent or not root_types) else _face(raw, None, curve)\n    return TacticalProfile(**vars(main), faces=faces, context=context, input_sha256=_hash(raw))"
LEGACY_CORPUS = 'def profile_corpus(repo: Repository, names, *, corpus=None, archetype=None) -> dict:\n    """Write estimates separately from preserved canonical facts and rulings."""\n    requested = sorted({str(name).strip().casefold(): str(name).strip()\n                        for name in names if str(name).strip()}.values(), key=str.casefold)\n    lookup = repo.get_card_knowledge_by_names(requested)\n    report = {"profiled": 0, "profiles_updated": 0, "errors": []}\n    valid, seen = [], set()\n    for name in requested:\n        row = lookup.get(name.casefold())\n        canonical = ScryfallSyncService.canonical_local_profile(row, name)\n        if canonical is None:\n            report["errors"].append({"name": name, "error": "Verified canonical knowledge is missing or invalid"})\n        elif row.name.casefold() not in seen:\n            seen.add(row.name.casefold())\n            valid.append((row, canonical))\n    context = deepcopy(corpus) if corpus is not None else [deepcopy(profile["card_data"]) for _, profile in valid]\n    for row, canonical in valid:\n        try:\n            derived = derive_profile(deepcopy(canonical["card_data"]), context, archetype=archetype)\n            merged = merge_profile_payload(canonical, derived)\n            answerable, windows = list(derived.answerable_by), list(derived.cast_windows)\n            unchanged = (row.play_value == derived.play_value and row.threat_level == derived.threat_level\n                         and row.etb_impact == derived.etb_impact and canonical == merged\n                         and json.loads(row.answerable_by_json) == answerable\n                         and json.loads(row.cast_windows_json) == windows)\n            if not unchanged:\n                repo.upsert_card_knowledge({\n                    "name": row.name, "scryfall_id": row.scryfall_id, "oracle_source": row.oracle_source,\n                    "play_value": derived.play_value, "threat_level": derived.threat_level,\n                    "answerable_by": answerable, "cast_windows": windows,\n                    "etb_impact": derived.etb_impact, "profiles": merged,\n                })\n                report["profiles_updated"] += 1\n            report["profiled"] += 1\n        except (ValueError, TypeError, KeyError) as exc:\n            report["errors"].append({"name": row.name, "error": str(exc)})\n    return report'


def canonical_rows():
    folder = Path(__file__).parent / 'fixtures/knowledge_profiles'
    data = (folder / 'seed155-scryfall.jsonl').read_bytes()
    assert hashlib.sha256(data).hexdigest() == json.loads((folder / 'PROVENANCE.json').read_text())['snapshot_sha256']
    cards = [json.loads(line) for line in data.splitlines()]
    assert len(cards) == 155
    return cards


class PublicMemoryRows:
    """Plain in-memory test storage; deliberately not a real SQL Repository."""
    def __init__(self, cards):
        self.rows = {raw['name'].casefold(): SimpleNamespace(
            name=raw['name'], scryfall_id=raw['id'], oracle_source='scryfall',
            play_value=None, threat_level=None, etb_impact=None,
            answerable_by_json='[]', cast_windows_json='[]',
            profiles_json=json.dumps({'card_data': deepcopy(raw), 'rulings_verified': True,
                                     'rulings': [], 'future_namespace': {'retained': [1, 2]}}))
                     for raw in cards}
        self.writes = []

    def get_card_knowledge_by_names(self, names):
        return {name.casefold(): self.rows[name.casefold()] for name in names if name.casefold() in self.rows}

    def upsert_card_knowledge(self, payload):
        self.writes.append(deepcopy(payload))
        row = self.rows[payload['name'].casefold()]
        for key in ('play_value', 'threat_level', 'etb_impact'):
            setattr(row, key, payload[key])
        for key in ('profiles', 'answerable_by', 'cast_windows'):
            setattr(row, key+'_json', json.dumps(payload[key]))
        return row


def legacy_corpus(repo, names, **kwargs):
    # Exact frozen8ad function bodies, using the unchanged real mechanics helpers.
    env = vars(profiles).copy()
    exec(compile(LEGACY_DERIVE, '<frozen8ad-derive>', 'exec'), env)
    ns = vars(sync).copy(); ns['derive_profile'] = env['derive_profile']
    exec(compile(LEGACY_CORPUS, '<frozen8ad-corpus>', 'exec'), ns)
    return ns['profile_corpus'](repo, names, **kwargs)


def small():
    folder = Path(__file__).parent / 'vraska_full/fixtures'
    pins = json.loads((folder / 'PROVENANCE.json').read_text())['fixture_bytes']
    cards = []
    for name in ('lightning-bolt.json', 'grizzly-bears-scryfall-raw.json'):
        data = (folder / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == pins[name]
        cards.append(json.loads(data))
    return cards


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def test_batch_normalizes_analyzes_and_fingerprints_corpus_once():
    cards = small(); repo = PublicMemoryRows(cards)
    fingerprints = []
    original = profiles._hash
    def digest(value):
        if isinstance(value, list): fingerprints.append(deepcopy(value))
        return original(value)
    with patch.object(profiles, 'analyze_deck', wraps=profiles.analyze_deck) as analysis, \
            patch.object(profiles, '_raw', wraps=profiles._raw) as raw, \
            patch.object(profiles, '_hash', side_effect=digest):
        assert sync.profile_corpus(repo, [c['name'] for c in cards])['profiled'] == 2
    assert analysis.call_count == 1
    assert len(fingerprints) == 1
    assert raw.call_count == 4  # Two card roots plus the two corpus metadata roots.


@pytest.mark.parametrize('archetype', [None, 'Control', {'caller': ['unverified']}])
def test_all155_outputs_match_frozen8ad_including_faces_and_future_metadata(archetype):
    cards = canonical_rows(); names = [c['name'] for c in cards]
    context = [{'quantity': 1+(i % 4), 'card_metadata': c} for i, c in enumerate(cards)]
    before = deepcopy((cards, context, archetype))
    old, new = PublicMemoryRows(cards), PublicMemoryRows(cards)
    assert encoded(legacy_corpus(old, names, corpus=context, archetype=archetype)) == encoded(
        sync.profile_corpus(new, names, corpus=context, archetype=archetype))
    assert encoded(old.writes) == encoded(new.writes)
    assert (cards, context, archetype) == before
    assert sync.profile_corpus(new, names, corpus=context, archetype=archetype) == {
        'profiled': 155, 'profiles_updated': 0, 'errors': []}


def test_derived_context_and_nested_mutables_are_not_shared_or_exposed_to_caller(monkeypatch):
    cards = small(); repo = PublicMemoryRows(cards); captured = []
    archetype = {'caller_declared': ['Control']}
    original = sync.merge_profile_payload
    def merge(existing, derived):
        captured.append(derived)
        return original(existing, derived)
    monkeypatch.setattr(sync, 'merge_profile_payload', merge)
    sync.profile_corpus(repo, [c['name'] for c in cards], archetype=archetype)
    assert captured[0].context is not captured[1].context
    captured[0].context['archetype']['caller_declared'].append('mutation')
    assert captured[1].context['archetype'] == {'caller_declared': ['Control']}
    assert archetype == {'caller_declared': ['Control']}
    captured[0].context['corpus_fingerprint'] = 'mutation'
    assert captured[1].context['corpus_fingerprint'] != 'mutation'
    repo.writes[0]['profiles']['card_data']['keywords'].append('mutation')
    assert all('mutation' not in c['keywords'] for c in cards)


def test_new_batch_recomputes_context_and_does_not_reuse_previous_deck():
    cards = small(); contexts = [
        [{'quantity': 1, 'card_metadata': cards[0]}, {'quantity': 4, 'card_metadata': cards[1]}],
        [{'quantity': 4, 'card_metadata': cards[0]}, {'quantity': 1, 'card_metadata': cards[1]}]]
    fingerprints = []
    with patch.object(profiles, 'analyze_deck', wraps=profiles.analyze_deck) as analysis:
        for context in contexts:
            repo = PublicMemoryRows(cards)
            sync.profile_corpus(repo, [c['name'] for c in cards], corpus=context)
            fingerprints.append(repo.writes[0]['profiles']['tactical_profile']['context']['corpus_fingerprint'])
    assert analysis.call_count == 2
    assert fingerprints[0] != fingerprints[1]


@pytest.mark.parametrize('quantity', [True, -1, 1001])
def test_invalid_shared_context_keeps_exact_per_row_errors_and_no_writes(quantity):
    cards = small(); context = [{'quantity': quantity, 'card_metadata': cards[0]}]
    old, new = PublicMemoryRows(cards), PublicMemoryRows(cards)
    assert sync.profile_corpus(new, [c['name'] for c in cards], corpus=context) == legacy_corpus(
        old, [c['name'] for c in cards], corpus=context)
    assert not old.writes and not new.writes


def test_missing_rows_do_not_eagerly_prepare_or_admit_invalid_context():
    context = [{'quantity': True, 'card_metadata': small()[0]}]
    with patch.object(profiles, 'analyze_deck', wraps=profiles.analyze_deck) as analysis:
        report = sync.profile_corpus(PublicMemoryRows([]), ['Missing'], corpus=context)
    assert report['profiled'] == 0 and len(report['errors']) == 1
    assert not analysis.called


def test_single_derive_payload_and_public_signature_match_frozen8ad():
    import inspect
    env = vars(profiles).copy(); exec(compile(LEGACY_DERIVE, '<frozen8ad-derive>', 'exec'), env)
    cards = small()
    assert str(inspect.signature(profiles.derive_profile)) == str(inspect.signature(env['derive_profile']))
    for card in cards:
        assert encoded(profiles.profile_payload(profiles.derive_profile(card, cards, archetype='Burn'))) == encoded(
            profiles.profile_payload(env['derive_profile'](card, cards, archetype='Burn')))
