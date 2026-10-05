"""Offline classifier evidence, never effects certification or learned quality."""
from __future__ import annotations

try:
    from . import _bootstrap
except ImportError:
    import _bootstrap

import argparse
from collections import Counter
from contextlib import closing
import importlib
import hashlib
import json
from pathlib import Path

from card_data.tactical import printed_card_types
from knowledge.mechanic_metadata import mechanic_metadata, SCHEMA_VERSION, EXTRACTOR_VERSION
from rules_engine.coverage import known_unsupported_mechanics
from scripts import corpus_knowledge_readiness as corpus

MAX_DATABASE_BYTES = 2 * 1024**3
MAX_ROWS = 100000
MAX_PROFILE_BYTES = 2 * 1024**2
MAX_TEXT_BYTES = 16384
MAX_FACES = 32
MAX_FAMILIES = 256
MAX_EXAMPLES = 10


def input_path(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('SQLite input cannot contain symlinks')
    path = corpus.local_path(path)
    if not path.is_file() or path.name == 'mtg_lab.db' or path.stat().st_nlink != 1:
        raise ValueError('Supply an independent named local offline copy')
    if path.stat().st_size > MAX_DATABASE_BYTES:
        raise ValueError('SQLite input exceeds byte cap')
    if any(p.exists() or p.is_symlink() for p in (Path(str(path) + s) for s in ('-wal', '-shm', '-journal'))):
        raise ValueError('SQLite input has active/recovery sidecars')
    return path


def surface_status(raw):
    faces = raw.get('card_faces', [])
    if not isinstance(faces, list) or any(not isinstance(f, dict) for f in faces):
        return 'malformed_faces'
    if len(faces) > MAX_FACES:
        raise ValueError('Face count exceeds resource cap')
    for surface in [raw, *faces]:
        for key in ('name', 'type_line', 'oracle_text'):
            if key in surface and not isinstance(surface[key], str):
                return 'malformed_surface'
            if len(surface.get(key, '').encode()) > MAX_TEXT_BYTES:
                raise ValueError('Surface text exceeds resource cap')
        for key in ('keywords', 'types'):
            if key in surface and (not isinstance(surface[key], list) or any(not isinstance(v, str) for v in surface[key])):
                return 'malformed_surface'
            if len(surface.get(key, [])) > 256 or any(len(v.encode()) > 256 for v in surface.get(key, [])):
                raise ValueError('Surface field exceeds resource cap')
    return 'valid'


def module_hashes():
    # Include all engine modules: the classifier delegates to many parsers.
    root = Path(importlib.import_module('rules_engine.coverage').__file__).parent
    paths = list(root.rglob('*.py')) + [Path(importlib.import_module(name).__file__) for name in
            ('knowledge.mechanic_metadata', 'card_data.tactical', 'scripts.corpus_knowledge_readiness', 'knowledge.ingest')]
    backend = root.parent
    return {str(p.relative_to(backend)): corpus.file_hash(p) for p in sorted(paths)}


def coverage_report(conn, *, examples=3):
    if type(examples) is not int or not 0 <= examples <= MAX_EXAMPLES:
        raise ValueError('Representative limit must be 0..10')
    rows, size = conn.execute('SELECT count(*),coalesce(max(length(CAST(profiles_json AS BLOB))),0) FROM cardknowledge').fetchone()
    if rows > MAX_ROWS or size > MAX_PROFILE_BYTES:
        raise ValueError('Knowledge row/profile resource cap exceeded before payload reads')
    totals, states, types = Counter(), Counter(), Counter()
    groups = {'unsupported': {}, 'unknown': {}}
    ledger = {}
    snapshot = hashlib.sha256()

    def add(status, family, example):
        group = groups[status]
        if family not in group:
            if len(group) >= MAX_FAMILIES:
                raise ValueError('Classifier family cap exceeded')
            group[family] = {'cards': 0, 'representatives': []}
        group[family]['cards'] += 1
        if len(group[family]['representatives']) < examples:
            group[family]['representatives'].append(example)

    for row in conn.execute('SELECT * FROM cardknowledge ORDER BY id'):
        totals['rows'] += 1
        snapshot.update(f"{row['id']}:{corpus.canonical_hash(dict(row))}\n".encode())
        value = row['profiles_json']
        # Defensive per-row check also handles a growing/non-snapshot test source.
        if not isinstance(value, str):
            states['profile_missing'] += 1
            totals['unclassifiable_cards'] += 1
            continue
        if len(value.encode()) > MAX_PROFILE_BYTES:
            raise ValueError('Profile resource cap exceeded')
        try:
            profile = json.loads(value)
        except (ValueError, RecursionError):
            profile = None
        if not isinstance(profile, dict):
            states['profile_malformed'] += 1
            totals['unclassifiable_cards'] += 1
            continue
        raw = profile.get('card_data')
        if not isinstance(raw, dict) or not raw:
            states['card_data_missing_or_malformed'] += 1
            totals['unclassifiable_cards'] += 1
            continue
        raw_sha = corpus.canonical_hash(raw)
        states['nested_' + corpus.mechanic_status(profile, raw_sha)] += 1
        shape = surface_status(raw)
        canonical = (row['oracle_source'] == 'scryfall' and raw.get('object') == 'card'
                     and bool(raw.get('name')) and raw.get('id') == row['scryfall_id']
                     and isinstance(raw.get('oracle_id'), str) and bool(raw['oracle_id'])
                     and raw.get('oracle_id') == profile.get('oracle_id'))
        if shape != 'valid' or not canonical:
            states[shape if shape != 'valid' else 'canonical_identity_unverified'] += 1
            totals['unclassifiable_cards'] += 1
            continue
        totals['canonical_identity_cards'] += 1
        surfaces = [raw, *raw.get('card_faces', [])]
        for kind in sorted(set().union(*(printed_card_types(s.get('type_line', ''), s.get('types')) for s in surfaces))):
            types[kind] += 1
        if not any(isinstance(s.get('oracle_text'), str) and s['oracle_text'].strip() for s in surfaces):
            states['empty_or_missing_text_not_absence_of_abilities'] += 1
        facts = corpus.fact_gaps(raw)
        totals['card_fact_metadata_gaps'] += bool(facts)
        provenance = raw_sha == (profile.get('card_data_provenance') or {}).get('record_sha256') if isinstance(profile.get('card_data_provenance'), dict) else False
        totals['record_digest_matches'] += provenance
        example = {'id': row['id'], 'name': row['name'], 'scryfall_id': raw['id'], 'oracle_id': raw['oracle_id'],
                   'card_data_sha256': raw_sha, 'canonical_identity': True, 'record_digest_matches': provenance}
        for key in ('card_data_provenance', 'rulings_provenance'):
            packet = profile.get(key)
            if isinstance(packet, dict):
                public = {k: packet[k] for k in ('source', 'archive_sha256', 'updated_at', 'source_uri', 'jsonl_download_uri') if k in packet}
                ledger[corpus.canonical_hash(public)] = public
                if len(ledger) > MAX_FAMILIES:
                    raise ValueError('Source provenance ledger cap exceeded')
        reasons = sorted(set(known_unsupported_mechanics(raw.get('oracle_text', ''), raw.get('card_faces'), card_name=raw['name'])))
        totals['known_gap_cards'] += bool(reasons)
        totals['no_known_gap_not_certified_cards'] += not reasons
        for reason in reasons:
            add('unsupported', reason, example)
        # Transient surface extraction; never materialize or replace stored tags.
        detected = mechanic_metadata(raw)
        for family, data in sorted(detected['coverage'].items()):
            if data['status'] == 'detected':
                add('unknown', family, example)
        totals['surface_semantics_unknown_cards'] += bool(detected['evidence'])
    return {'schema_version': 1, 'knowledge_snapshot_sha256': snapshot.hexdigest(),
            'totals': {key: totals[key] for key in ('rows', 'canonical_identity_cards', 'unclassifiable_cards', 'card_fact_metadata_gaps',
                       'record_digest_matches', 'known_gap_cards', 'no_known_gap_not_certified_cards', 'surface_semantics_unknown_cards')},
            'metadata_states': dict(sorted(states.items())), 'card_type_metadata_counts_not_semantic_support': dict(sorted(types.items())),
            'mechanics': {'supported': {'cards': None, 'families': {}, 'reason': 'Existing classifier emits known gaps only; affirmative support unavailable.'},
                         'unsupported': dict(sorted(groups['unsupported'].items())), 'unknown': dict(sorted(groups['unknown'].items()))},
            'source_provenance_ledger': [ledger[k] for k in sorted(ledger)],
            'classifier': {'function': 'rules_engine.coverage.known_unsupported_mechanics', 'scope': 'known_gaps_only',
                           'source_module_sha256': module_hashes()},
            'surface_extractor': {'schema_version': SCHEMA_VERSION, 'extractor_version': EXTRACTOR_VERSION,
                                  'scope': 'transient_surface_detection_only', 'execution_support': 'unknown'},
            'resource_caps': {'database_bytes': MAX_DATABASE_BYTES, 'rows': MAX_ROWS, 'profile_bytes': MAX_PROFILE_BYTES,
                              'surface_field_bytes': MAX_TEXT_BYTES, 'faces': MAX_FACES, 'families_per_status': MAX_FAMILIES,
                              'representatives_per_family': examples},
            'limitations': ['Known gap labels may be conservative despite existing handlers; not gameplay test results.',
                            'Unsupported reason sets and unknown surface families overlap; counts are not additive.',
                            'No gap, empty text, missing metadata and non-detection are never correctness evidence.',
                            'Identity and record digests are consistency evidence, not publisher authentication or freshness.',
                            'Card types and surface roles are metadata, not executable mechanic support.'],
            'rules_support_certified': False, 'trained_competence': 'unknown', 'database_writes': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--database-sha256', required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--examples', type=int, default=3)
    args = parser.parse_args()
    corpus.new_outputs(args.out, args.out.with_name(args.out.name + '.part'))
    path = input_path(args.database)
    before = corpus.file_hash(path)
    if before != args.database_sha256:
        raise ValueError('Offline source digest mismatch')
    with closing(corpus.readonly(path)) as conn:
        result = coverage_report(conn, examples=args.examples)
    if corpus.file_hash(path) != before:
        raise ValueError('Offline source changed; report refused')
    result['database_sha256'] = before
    corpus.publish_json(args.out, result)


if __name__ == '__main__':
    main()
