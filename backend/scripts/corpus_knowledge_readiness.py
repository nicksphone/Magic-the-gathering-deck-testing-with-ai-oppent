"""Read-only corpus audit and offline, preconditioned knowledge import artifacts.

No app import/lifespan, implicit database, broad sync, numeric estimates, or live
writes. Bulk files are supplied with explicit SHA256 expectations. A hash proves
byte identity, not publisher authenticity; preserve official fetch manifests.
"""
from __future__ import annotations

try:
    from . import _bootstrap
except ImportError:
    import _bootstrap

import argparse
import errno
from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime, timezone
import gzip
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import sqlite3
import time
import tempfile
from types import SimpleNamespace
from urllib.parse import urlparse

import httpx

from card_data.hydration import ready_for_match, is_playable_deck_card
from card_data.sync import ScryfallSyncService
from card_data.tactical import tactical_tags
from knowledge.ingest import canonical_hash, validate_rulings_page
from card_data.http_utils import get_with_backoff
from rules_engine.coverage import known_unsupported_mechanics
from scripts.sync_all_card_knowledge import read_cards

VERSION = 1
MECHANIC_SCHEMA = 1
MECHANIC_EXTRACTOR = 'canonical-tactical-surface-v1'
TAG_HASH = hashlib.sha256(Path(importlib.import_module('card_data.tactical').__file__).read_bytes()).hexdigest()

# Application-only ceilings, not values supplied by an untrusted index.
MAX_INDEX_BYTES = 2 * 1024 * 1024
MAX_RECEIPT_BYTES = 64 * 1024
MAX_COMPRESSED_ARTIFACT_BYTES = 16 * 1024 * 1024
MAX_ARTIFACT_LINE_BYTES = 2 * 1024 * 1024
MAX_ARTIFACT_EXPANDED_BYTES = 64 * 1024 * 1024
MAX_TOTAL_EXPANDED_BYTES = 1024 * 1024 * 1024
MAX_STAGE_BYTES = 2 * 1024 * 1024 * 1024
MAX_REFRESH_BYTES = 2 * 1024 * 1024
MAX_SOURCE_PROFILE_BYTES = 2 * 1024 * 1024
MAX_SOURCE_ROWS = 100000
MAX_INDEX_ENTRIES = 256


def new_outputs(*paths):
    for path in paths:
        path = Path(path)
        if path.exists() or path.is_symlink():
            raise FileExistsError(f'Refusing existing output: {path}')


def publish_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.part')
    new_outputs(path, temporary)
    owned = False
    try:
        with temporary.open('x', encoding='utf-8') as stream:
            owned = True
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write('\n')
        os.link(temporary, path)  # Atomic no-clobber publication, including on NFS.
    finally:
        if owned:
            temporary.unlink(missing_ok=True)


def legacy_tags(raw):
    # Do not call the additive canonical wrapper: B's nested extraction is large.
    result = {'tactical_tags': sorted(tactical_tags(raw.get('oracle_text', ''), raw.get('type_line', '')))}
    faces = raw.get('card_faces') or []
    if faces:
        result['face_tactical_tags'] = [sorted(tactical_tags(face.get('oracle_text', ''), face.get('type_line', ''))) for face in faces if isinstance(face, dict)]
    return result


def mechanic_status(profile, raw_sha):
    metadata = profile.get('mechanic_metadata')
    if metadata is None:
        return 'missing'
    if not isinstance(metadata, dict):
        return 'invalid_shape'
    if metadata.get('schema_version') != MECHANIC_SCHEMA or metadata.get('extractor_version') != MECHANIC_EXTRACTOR:
        return 'stale_version'
    provenance = metadata.get('provenance')
    if not isinstance(provenance, dict) or provenance.get('input_sha256') != raw_sha:
        return 'stale_input'
    return 'current_input_version_not_semantics'


def fetch_rulings(directory):
    """One official metadata request and one bulk download, never per card."""
    directory.mkdir(parents=True, exist_ok=True)
    with httpx.Client(headers={'User-Agent': 'MTGDeckTestingLab/0.1 (knowledge corpus readiness)', 'Accept': 'application/json'}, follow_redirects=False) as client:
        # Fail closed on 429; do not use the legacy helper's shorter retries.
        response = get_with_backoff(client, 'https://api.scryfall.com/bulk-data/rulings', timeout=30, retries=0)
        response.raise_for_status()
        metadata = response.json()
        uri = metadata.get('jsonl_download_uri')
        parsed = urlparse(uri or '')
        if metadata.get('type') != 'rulings' or not metadata.get('updated_at') or parsed.scheme != 'https' or parsed.netloc not in {'data.scryfall.io', 'data.scryfall.com'} or not parsed.path.endswith('.jsonl.gz'):
            raise ValueError('Invalid official ruling bulk endpoint')
        target = directory / Path(parsed.path).name
        temporary = target.with_name(target.name + '.part')
        manifest_path = target.with_name(target.name + '.manifest.json')
        new_outputs(target, temporary, manifest_path, manifest_path.with_name(manifest_path.name + '.part'))
        owned = False
        try:
            with client.stream('GET', uri, timeout=120) as download:
                download.raise_for_status()
                with temporary.open('xb') as output:
                    owned = True
                    for chunk in download.iter_bytes():
                        output.write(chunk)
            count = 0
            for ruling in read_cards_gzip(temporary):
                validate_rulings_page({'object': 'list', 'data': [ruling], 'has_more': False}, ruling.get('oracle_id'))
                count += 1
            os.link(temporary, target)
        finally:
            if owned:
                temporary.unlink(missing_ok=True)
    metadata.update({'archive_sha256': file_hash(target), 'fetched_at': datetime.now(timezone.utc).isoformat(), 'records': count, 'api_metadata_url': 'https://api.scryfall.com/bulk-data/rulings'})
    publish_json(manifest_path, metadata)
    return {'archive': str(target), 'sha256': metadata['archive_sha256'], 'records': count, 'updated_at': metadata['updated_at']}


def read_cards_gzip(path):
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def file_hash(path):
    for attempt in range(4):
        try:
            with Path(path).open('rb') as stream:
                return hashlib.file_digest(stream, 'sha256').hexdigest()
        except OSError as exc:
            if exc.errno != errno.ESTALE or attempt == 3:
                raise
            time.sleep(0.1 * 2 ** attempt)


def publish_artifact(path, config, patches):
    temporary = path.with_name(path.name + '.part')
    new_outputs(path, temporary)
    owned = False
    try:
        with temporary.open('xb') as raw:
            owned = True
            with gzip.open(raw, 'wt', encoding='utf-8') as output:
                output.write(json.dumps({'manifest': config}, sort_keys=True) + '\n')
                for patch in patches:
                    output.write(patch + '\n')
        os.link(temporary, path)
    finally:
        if owned:
            temporary.unlink(missing_ok=True)
    return file_hash(path)


def fetch_card(conn, out, row_id):
    row = conn.execute('SELECT * FROM cardknowledge WHERE id=?', (row_id,)).fetchone()
    if not row or row['oracle_source'] != 'scryfall':
        raise ValueError('Refresh requires an existing canonical row')
    before = load_profile(row)['card_data']
    uri = f"https://api.scryfall.com/cards/{row['scryfall_id']}"
    response_path = out.with_name(out.name + '.response.json')
    new_outputs(out, out.with_name(out.name + '.part'), response_path, response_path.with_name(response_path.name + '.part'))
    with httpx.Client(headers={'User-Agent': 'MTGDeckTestingLab/0.1 (one canonical mismatch verification)', 'Accept': 'application/json'}, follow_redirects=False) as client:
        response = get_with_backoff(client, uri, timeout=30, retries=0)
        response.raise_for_status()
        raw = response.json()
    if (raw.get('object') != 'card' or raw.get('id') != before['id'] or raw.get('oracle_id') != before['oracle_id']
            or raw.get('name') != before['name'] or not raw.get('type_line')):
        raise ValueError('Current API response changes the requested printing/Oracle/name identity')
    # Preserve the exact official response bytes, not just a parsed JSON hash.
    with response_path.open('xb') as stream:
        stream.write(response.content)
    provenance = {'source': 'scryfall', 'type': 'card_api_refresh', 'archive_sha256': file_hash(response_path), 'download_uri': uri,
                  'updated_at': datetime.now(timezone.utc).isoformat(), 'publisher_fetch_evidence': 'official_card_response',
                  'record_sha256': canonical_hash(raw)}
    packet = {'row_id': row_id, 'oracle_id': raw['oracle_id'], 'scryfall_id': raw['id'], 'previous_card_sha256': canonical_hash(before),
              'card_data': raw, 'response_archive': str(response_path.resolve()), 'provenance': provenance,
              'differing_fields': sorted(key for key in before.keys() | raw.keys() if before.get(key) != raw.get(key))}
    publish_json(out, packet)
    return packet


def checked_refresh(args, *, packet_bytes=None, response_bytes=None):
    path = getattr(args, 'card_refresh', None)
    if not path:
        return None
    packet_sha = hashlib.sha256(packet_bytes).hexdigest() if packet_bytes is not None else file_hash(path)
    if packet_sha != args.card_refresh_sha256:
        raise ValueError('Canonical refresh packet hash mismatch')
    packet = json.loads(packet_bytes if packet_bytes is not None else path.read_text())
    raw, prov = packet['card_data'], packet['provenance']
    parsed = urlparse(prov['download_uri'])
    if (prov.get('source') != 'scryfall' or prov.get('type') != 'card_api_refresh'
            or parsed.scheme != 'https' or parsed.netloc != 'api.scryfall.com' or parsed.path != f"/cards/{packet['scryfall_id']}"
            or raw.get('id') != packet['scryfall_id'] or raw.get('oracle_id') != packet['oracle_id']
            or canonical_hash(raw) != prov['record_sha256']
            or (hashlib.sha256(response_bytes).hexdigest() if response_bytes is not None else file_hash(packet['response_archive'])) != prov['archive_sha256']):
        raise ValueError('Canonical refresh evidence mismatch')
    response = json.loads(response_bytes if response_bytes is not None else Path(packet['response_archive']).read_text())
    if response != raw:
        raise ValueError('Refresh response archive differs from packet')
    return packet


def readonly(path):
    conn = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA query_only=ON')
    conn.execute('BEGIN')
    return conn


def local_path(path):
    """Keep SQLite state local, including paths outside the normal NFS mount."""
    import subprocess
    if Path(path).is_symlink():
        raise ValueError('Writable SQLite paths cannot be symlinks')
    path = Path(path).resolve()
    parent = path if path.exists() else path.parent
    kind = subprocess.check_output(['findmnt', '-n', '-o', 'FSTYPE', '-T', str(parent)], text=True).strip()
    if any(item in kind for item in ('nfs', 'cifs', 'autofs')):
        raise ValueError('SQLite scratch/state must be on a local filesystem')
    return path


def load_profile(row):
    try:
        value = json.loads(row['profiles_json'])
        return value if isinstance(value, dict) else {}
    except (ValueError, TypeError):
        return {}


def fact_gaps(raw):
    gaps = []
    for key in ('id', 'oracle_id', 'name', 'layout'):
        if not raw.get(key):
            gaps.append(key)
    if raw.get('object') != 'card':
        gaps.append('object')
    for key, kind in (('cmc', (float, int)), ('color_identity', list), ('keywords', list), ('legalities', dict)):
        if not isinstance(raw.get(key), kind):
            gaps.append(key)
    faces = raw.get('card_faces', [])
    if not isinstance(faces, list) or any(not isinstance(face, dict) for face in faces):
        return gaps + ['card_faces_shape']
    if raw.get('layout') in {'modal_dfc', 'transform', 'adventure', 'split', 'reversible_card', 'double_faced_token', 'art_series', 'flip'} and len(faces) < 2:
        gaps.append('card_faces_count')
    for index, face in enumerate(faces or [raw]):
        prefix = f'face:{index}:' if faces else ''
        for key in ('name', 'type_line'):
            if not face.get(key):
                gaps.append(prefix + key)
        # Empty oracle_text/mana_cost is valid; absent fields are unknown.
        for key in ('oracle_text', 'mana_cost'):
            if key not in face or not isinstance(face[key], str):
                gaps.append(prefix + key)
        types = str(face.get('type_line', '')).split(' // ')[0].split(' — ')[0].split()
        for key in (('power', 'toughness') if 'Creature' in types else ('loyalty',) if 'Planeswalker' in types else ('defense',) if 'Battle' in types else ()):
            if face.get(key) is None:
                gaps.append(prefix + key)
    return gaps


def raw_metadata(raw):
    # Dummy art avoids placeholder filesystem writes in the existing normalizer.
    payload = ScryfallSyncService._normalize_payload(raw, 'https://invalid.example/no-fetch')
    payload['card_faces'] = json.loads(payload.pop('card_faces_json'))
    payload['card_name'] = raw['name']
    return payload


def audit(conn):
    cards, totals, aliases = [], Counter(), {}
    tag_versions = Counter()
    digest = hashlib.sha256()
    for row in conn.execute('SELECT * FROM cardknowledge ORDER BY id'):
        profile = load_profile(row)
        raw = profile.get('card_data')
        raw = raw if isinstance(raw, dict) else {}
        sha = canonical_hash(raw)
        digest.update(f"{row['id']}:{canonical_hash(dict(row))}\n".encode())
        gaps = fact_gaps(raw)
        identity = row['oracle_source'] == 'scryfall' and raw.get('object') == 'card' and bool(raw.get('name')) and raw.get('id') == row['scryfall_id'] and profile.get('oracle_id') == raw.get('oracle_id') and bool(raw.get('oracle_id'))
        admitted = bool(identity and ScryfallSyncService.canonical_local_profile(SimpleNamespace(**dict(row)), row['name']))
        metadata = raw_metadata(raw) if identity and not any('shape' in gap for gap in gaps) else {}
        playable = bool(metadata and is_playable_deck_card(metadata))
        match_ready = bool(admitted and playable and ready_for_match(metadata))
        mechanics = known_unsupported_mechanics(str(raw.get('oracle_text') or ''), raw.get('card_faces') if isinstance(raw.get('card_faces'), list) else [], card_name=str(raw.get('name') or '')) if identity else []
        tags = legacy_tags(raw) if not any('shape' in gap for gap in gaps) else {}
        nested_state = mechanic_status(profile, sha)
        tag_state = 'current' if tags and all(profile.get(key) == value for key, value in tags.items()) and ('face_tactical_tags' in tags or 'face_tactical_tags' not in profile) else 'missing_or_stale'
        tag_provenance = profile.get('tactical_provenance') or {}
        tag_versions[json.dumps(tag_provenance, sort_keys=True)] += 1
        rulings = profile.get('rulings')
        rp = profile.get('rulings_provenance', {})
        rp = rp if isinstance(rp, dict) else {}
        verified = profile.get('rulings_verified') is True and isinstance(rulings, list)
        evidence = verified and rp.get('complete') is True and rp.get('sha256') == canonical_hash(rulings) and rp.get('oracle_id', raw.get('oracle_id')) == raw.get('oracle_id') and bool(rp.get('archive_sha256') or rp.get('fetched_at'))
        status = ('verified_empty' if not rulings else 'verified_nonempty') if evidence else 'legacy_verified_without_evidence' if verified else 'pending'
        cp = profile.get('card_data_provenance', {})
        cp = cp if isinstance(cp, dict) else {}
        provenance = bool(cp.get('record_sha256') == sha and cp.get('archive_sha256') and cp.get('source') == 'scryfall')
        card = {'id': row['id'], 'name': row['name'], 'oracle_id': raw.get('oracle_id'), 'canonical_identity': bool(identity), 'payload_sha256': sha, 'fact_gaps': gaps, 'face_count': len(raw.get('card_faces', [])) if isinstance(raw.get('card_faces', []), list) else None, 'source_record_evidence': provenance, 'canonical_admissible': admitted, 'match_metadata_ready': match_ready, 'playable': playable, 'rulings_status': status, 'rulings_count': len(rulings) if isinstance(rulings, list) else None, 'tactical_tags': tag_state, 'engine_support': 'known_gaps' if mechanics else 'not_certified', 'known_engine_gaps': mechanics, 'trained_competence': 'unknown'}
        cards.append(card)
        card['mechanic_metadata'] = nested_state
        totals['mechanic_metadata_' + nested_state] += 1
        totals['rows'] += 1
        totals['canonical_identity'] += bool(identity)
        totals['facts_complete'] += not gaps
        totals['source_record_evidence'] += provenance
        totals['match_metadata_ready'] += match_ready
        totals['nonplayable'] += not playable
        totals['canonical_not_admissible'] += not admitted
        totals['playable_but_not_admissible'] += playable and not admitted
        totals['known_engine_gaps'] += bool(mechanics)
        totals['rulings_' + status] += 1
        totals['tactical_tags_' + tag_state] += 1
        for alias in [row['name'], raw.get('name'), *(face.get('name') for face in raw.get('card_faces', []) if isinstance(face, dict))] if isinstance(raw.get('card_faces', []), list) else [row['name']]:
            if alias and admitted and playable:
                aliases.setdefault(alias.casefold(), card)
    decks, priority = [], set()
    has_decks = conn.execute("SELECT 1 FROM sqlite_master WHERE name='deckrecord'").fetchone()
    if has_decks:
        for deck in conn.execute('SELECT id,mainboard_json,sideboard_json FROM deckrecord ORDER BY id'):
            names = {item['card_name'] for key in ('mainboard_json', 'sideboard_json') for item in json.loads(deck[key]) if item.get('card_name')}
            missing = sorted(name for name in names if name.casefold() not in aliases)
            selected = [aliases[name.casefold()] for name in names if name.casefold() in aliases]
            eligible = not missing and all(c['match_metadata_ready'] and not c['known_engine_gaps'] for c in selected)
            if eligible:
                priority.update(c['id'] for c in selected)
            decks.append({'deck_id': deck['id'], 'card_count': len(names), 'missing_canonical_names': missing, 'metadata_and_known_gap_screen_pass': eligible, 'rules_certified': False})
    for card in cards:
        card['supported_deck_first_candidate'] = card['id'] in priority
    table_counts = {table: conn.execute(f'SELECT count(*) FROM {table}').fetchone()[0] if conn.execute('SELECT 1 FROM sqlite_master WHERE name=?', (table,)).fetchone() else None for table in ('cardknowledge', 'cardcache', 'deckrecord')}
    return {'version': VERSION, 'snapshot_at': datetime.now(timezone.utc).isoformat(), 'knowledge_rows_sha256': digest.hexdigest(), 'totals': dict(totals), 'table_counts': table_counts, 'cards': cards, 'decks': decks, 'priority_rows': len(priority), 'audit_tag_implementation_sha256': TAG_HASH, 'stored_tag_provenance_counts': dict(tag_versions), 'rules_support_certified': False, 'trained_competence': 'unknown', 'limitations': ['No runtime effect qualification or AI training is inferred.', 'Known-gap screen is not exhaustive.', 'Characteristic gaps are diagnostics against generic expectations, not proof of corrupt source data; unusual/minigame/back-face exceptions require review.', 'Tag consistency compares only the reported audit implementation; a differing independent metadata version is not automatically wrong.', 'CardCache can override canonical knowledge during live hydration; this audits canonical knowledge, not cache parity.', 'Bulk ruling absence means no ruling in that dated snapshot, not proof there can never be rulings.', 'Hash evidence verifies identity, not publisher authenticity or latest upstream freshness.']}


def checked_source(path, expected, source_type, manifest_path=None):
    actual = file_hash(path)
    if actual != expected:
        raise ValueError(f'{source_type} archive SHA256 mismatch')
    manifest = json.loads(Path(manifest_path).read_text()) if manifest_path else {}
    uri = manifest.get('jsonl_download_uri') or manifest.get('download_uri')
    parsed = urlparse(uri or '')
    if manifest and (manifest.get('type') != source_type or not manifest.get('updated_at') or parsed.scheme != 'https' or parsed.netloc not in {'data.scryfall.io', 'data.scryfall.com'}):
        raise ValueError('Invalid official bulk metadata manifest')
    if manifest.get('archive_sha256') not in (None, actual):
        raise ValueError('Manifest archive hash mismatch')
    if source_type == 'rulings' and not manifest:
        raise ValueError('Complete ruling snapshot requires an official bulk metadata manifest')
    return {'source': 'scryfall', 'type': source_type, 'archive_sha256': actual, 'download_uri': uri, 'updated_at': manifest.get('updated_at'), 'publisher_fetch_evidence': 'supplied_manifest' if manifest else 'unknown'}


def prepare_inputs(conn, args):
    cards_prov = checked_source(args.cards, args.cards_sha256, 'oracle_cards', args.cards_manifest)
    rulings_prov = checked_source(args.rulings, args.rulings_sha256, 'rulings', args.rulings_manifest) if args.rulings else None
    card_index = {}
    for raw in read_cards(args.cards):
        if raw.get('object') != 'card' or not raw.get('oracle_id'):
            raise ValueError('Invalid bulk card')
        key = raw['oracle_id']
        if key in card_index:
            raise ValueError('Duplicate Oracle identity in unique-card bulk')
        card_index[key] = (canonical_hash(raw), raw)
    ruling_index = defaultdict(list)
    if args.rulings:
        ruling_count = 0
        for ruling in read_cards(args.rulings):
            validate_rulings_page({'object': 'list', 'data': [ruling], 'has_more': False}, ruling.get('oracle_id'))
            ruling_index[ruling['oracle_id']].append(ruling)
            ruling_count += 1
        manifest = json.loads(args.rulings_manifest.read_text())
        if manifest.get('records') not in (None, ruling_count):
            raise ValueError('Rulings record count differs from fetch manifest')
    return cards_prov, rulings_prov, card_index, ruling_index, audit(conn)


def prepare(conn, args, context=None):
    summary = args.out.with_suffix(args.out.suffix + '.summary.json')
    new_outputs(args.out, args.out.with_name(args.out.name + '.part'), summary, summary.with_name(summary.name + '.part'))
    cards_prov, rulings_prov, card_index, ruling_index, report = context or prepare_inputs(conn, args)
    refresh_tags = getattr(args, 'refresh_tags_sha256', None)
    if refresh_tags and refresh_tags != TAG_HASH:
        raise ValueError('Tag implementation hash mismatch; coordinate with metadata owner')
    config = {'version': VERSION, 'snapshot': report['knowledge_rows_sha256'], 'cards': cards_prov, 'rulings': rulings_prov, 'tags': refresh_tags or 'preserve_existing', 'audit_tags_implementation_sha256': TAG_HASH}
    mechanic_version = getattr(args, 'materialize_mechanics_version', None)
    mechanic_module = None
    if mechanic_version:
        if args.limit > 500:
            raise ValueError('Nested mechanic materialization is bounded to 500 examined rows per run')
        try:
            mechanic_module = importlib.import_module('knowledge.mechanic_metadata')
        except ImportError as exc:
            raise ValueError('Install reviewed metadata workstream B before materialization') from exc
        if mechanic_module.SCHEMA_VERSION != MECHANIC_SCHEMA or mechanic_module.EXTRACTOR_VERSION != mechanic_version or mechanic_version != MECHANIC_EXTRACTOR:
            raise ValueError('Mechanic extractor version mismatch')
        config['mechanics'] = {'schema_version': MECHANIC_SCHEMA, 'extractor_version': mechanic_version}
    refresh = checked_refresh(args)
    if refresh:
        config['card_refresh'] = {key: value for key, value in refresh.items() if key not in ('card_data', 'response_archive', 'differing_fields')}
    state_path = local_path(args.state)
    with closing(sqlite3.connect(state_path)) as state:
        state.execute('CREATE TABLE IF NOT EXISTS config (json TEXT NOT NULL)')
        state.execute('CREATE TABLE IF NOT EXISTS completed (id INTEGER PRIMARY KEY, patch TEXT, error TEXT)')
        old = state.execute('SELECT json FROM config').fetchone()
        encoded = json.dumps(config, sort_keys=True)
        if old and old[0] != encoded:
            before_config = json.loads(old[0])
            comparable_old, comparable_new = dict(before_config), dict(config)
            comparable_old.pop('audit_tags_implementation_sha256', None)
            comparable_new.pop('audit_tags_implementation_sha256', None)
            comparable_new.pop('card_refresh', None)
            if 'card_refresh' in comparable_old:
                comparable_new['card_refresh'] = config.get('card_refresh')
            if (getattr(args, 'resume_audit_version_change', False) and config['tags'] == 'preserve_existing'
                    and not mechanic_version and comparable_old == comparable_new):
                state.execute('CREATE TABLE IF NOT EXISTS config_history (json TEXT NOT NULL)')
                state.execute('INSERT INTO config_history VALUES (?)', (old[0],))
                state.execute('UPDATE config SET json=?', (encoded,))
                if refresh:
                    refusal = state.execute('SELECT error FROM completed WHERE id=?', (refresh['row_id'],)).fetchone()
                    if refusal and refusal[0] == 'Source record differs; no silent canonical overwrite':
                        state.execute('CREATE TABLE IF NOT EXISTS retry_history (id INTEGER, error TEXT, packet_sha256 TEXT)')
                        state.execute('INSERT INTO retry_history VALUES (?,?,?)', (refresh['row_id'], refusal[0], args.card_refresh_sha256))
                        state.execute('DELETE FROM completed WHERE id=?', (refresh['row_id'],))
                state.commit()
            else:
                raise ValueError('Resume inputs changed; use a new state file')
        if not old:
            state.execute('INSERT INTO config VALUES (?)', (encoded,))
            state.commit()
        completed = {r[0] for r in state.execute('SELECT id FROM completed')}
        ordered = sorted(report['cards'], key=lambda card: (not card['supported_deck_first_candidate'], not bool(card['fact_gaps']), card['id']))
        processed = 0
        batch_ids = []
        for card in ordered:
            if card['id'] in completed:
                continue
            if processed >= args.limit:
                break
            row = conn.execute('SELECT * FROM cardknowledge WHERE id=?', (card['id'],)).fetchone()
            profile = load_profile(row)
            raw = profile.get('card_data')
            indexed = card_index.get(card['oracle_id'])
            source_prov = cards_prov
            if refresh and row['id'] == refresh['row_id']:
                if (canonical_hash(raw) != refresh['previous_card_sha256'] or raw['id'] != refresh['scryfall_id'] or raw['oracle_id'] != refresh['oracle_id']):
                    raise ValueError('Refresh packet source precondition failed')
                raw = refresh['card_data']
                profile['card_data'] = raw
                profile['facts'] = {'mana_value': raw.get('cmc'), 'color_identity': raw.get('color_identity', []), 'keywords': raw.get('keywords', []), 'layout': raw.get('layout'), 'face_count': len(raw.get('card_faces', []))}
                indexed = (canonical_hash(raw), raw)
                source_prov = refresh['provenance']
            error, patch = None, None
            if not card['canonical_identity'] or not indexed:
                error = 'Canonical identity/source record missing; requires separately verified card acquisition'
            elif indexed[0] != canonical_hash(raw):
                error = 'Source record differs; no silent canonical overwrite'
            else:
                profile['card_data_provenance'] = {**source_prov, 'record_sha256': indexed[0]}
                profile['card_data_sha256'] = indexed[0]
                if refresh_tags:
                    profile.update(legacy_tags(raw))
                    if not raw.get('card_faces'):
                        profile.pop('face_tactical_tags', None)
                    profile['tactical_provenance'] = {'method': 'deterministic_oracle_text_tags', 'implementation_sha256': TAG_HASH, 'card_data_sha256': indexed[0], 'numerical_scores_generated': False}
                if mechanic_module and mechanic_status(profile, indexed[0]) != 'current_input_version_not_semantics':
                    profile['mechanic_metadata'] = mechanic_module.mechanic_metadata(raw)
                if rulings_prov:
                    previous_date = (profile.get('rulings_provenance') or {}).get('updated_at') or (profile.get('rulings_provenance') or {}).get('fetched_at')
                    if previous_date and rulings_prov.get('updated_at') and previous_date > rulings_prov['updated_at']:
                        error = 'Refusing to replace newer rulings evidence with older bulk snapshot'
                    else:
                        rulings = ruling_index[card['oracle_id']]
                        profile.update({'rulings': rulings, 'rulings_verified': True, 'rulings_provenance': {**rulings_prov, 'complete': True, 'oracle_id': card['oracle_id'], 'sha256': canonical_hash(rulings)}})
                if not error and profile != load_profile(row):
                    patch = json.dumps({'id': row['id'], 'name': row['name'], 'scryfall_id': row['scryfall_id'], 'before_profile_sha256': canonical_hash(load_profile(row)), 'after_profile_sha256': canonical_hash(profile), 'profile': profile}, sort_keys=True)
            state.execute('INSERT INTO completed VALUES (?,?,?)', (card['id'], patch, error))
            state.commit()  # One durable checkpoint per card; interrupted work resumes.
            processed += 1
            batch_ids.append(card['id'])
        if getattr(args, 'batch_artifact', False):
            records = (state.execute('SELECT patch FROM completed WHERE id=? AND patch IS NOT NULL', (row_id,)).fetchone() for row_id in batch_ids)
            patches = (row[0] for row in records if row)
        else:
            patches = (row[0] for row in state.execute('SELECT patch FROM completed WHERE patch IS NOT NULL ORDER BY id'))
        publish_artifact(args.out, config, patches)
        counts = dict(zip(('completed', 'patches', 'errors'), state.execute('SELECT count(*), coalesce(sum(patch IS NOT NULL),0), coalesce(sum(error IS NOT NULL),0) FROM completed').fetchone()))
        return {**counts, 'processed_this_run': processed, 'remaining': len(report['cards']) - counts['completed'], 'artifact_sha256': file_hash(args.out), 'errors_detail': [{'id': row[0], 'reason': row[1]} for row in state.execute('SELECT id,error FROM completed WHERE error IS NOT NULL')], 'provenance': config}


def validate_profile_patch(original, patch, manifest):
    """Shared source preconditions and owned-field/provenance checks, no writes."""
    if (not original or original['name'] != patch['name'] or original['scryfall_id'] != patch['scryfall_id']
            or canonical_hash(load_profile(original)) != patch['before_profile_sha256']):
        raise ValueError('Import precondition failed')
    profile = patch['profile']
    if canonical_hash(profile) != patch['after_profile_sha256']:
        raise ValueError('Import payload hash failed')
    before = load_profile(original)
    allowed = {'card_data_provenance', 'card_data_sha256', 'rulings', 'rulings_verified', 'rulings_provenance'}
    refresh = manifest.get('card_refresh')
    expected_prov = manifest['cards']
    if refresh and patch['id'] == refresh['row_id']:
        old_raw, new_raw = before['card_data'], profile['card_data']
        if (canonical_hash(old_raw) != refresh['previous_card_sha256']
                or canonical_hash(new_raw) != refresh['provenance']['record_sha256']
                or old_raw['id'] != new_raw['id'] or new_raw['id'] != refresh['scryfall_id']
                or old_raw['oracle_id'] != new_raw['oracle_id'] or new_raw['oracle_id'] != refresh['oracle_id']
                or old_raw['name'] != new_raw['name']):
            raise ValueError('Canonical refresh import identity/hash precondition failed')
        allowed.update({'card_data', 'facts'})
        expected_prov = refresh['provenance']
    if manifest.get('tags') == TAG_HASH:
        allowed.update({'tactical_tags', 'face_tactical_tags', 'tactical_provenance'})
    if manifest.get('mechanics') == {'schema_version': MECHANIC_SCHEMA, 'extractor_version': MECHANIC_EXTRACTOR}:
        allowed.add('mechanic_metadata')
        if mechanic_status(profile, canonical_hash(profile['card_data'])) != 'current_input_version_not_semantics':
            raise ValueError('Mechanic metadata input/version evidence mismatch')
    if any(before.get(key) != profile.get(key) for key in before.keys() | profile.keys() if key not in allowed):
        raise ValueError('Artifact changes non-owned canonical fields')
    raw = profile['card_data']
    cp = profile.get('card_data_provenance', {})
    if (profile.get('card_data_sha256') != canonical_hash(raw)
            or cp.get('record_sha256') != canonical_hash(raw)
            or any(cp.get(key) != value for key, value in expected_prov.items())):
        raise ValueError('Card source evidence does not match artifact manifest')
    if manifest.get('rulings'):
        rulings = profile.get('rulings')
        validate_rulings_page({'object': 'list', 'data': rulings, 'has_more': False}, raw['oracle_id'])
        rp = profile.get('rulings_provenance', {})
        if (profile.get('rulings_verified') is not True or rp.get('complete') is not True
                or rp.get('oracle_id') != raw['oracle_id'] or rp.get('sha256') != canonical_hash(rulings)
                or any(rp.get(key) != value for key, value in manifest['rulings'].items())):
            raise ValueError('Ruling source evidence does not match artifact manifest')
    return profile


def validate_artifact(conn, artifact, scratch, *, reuse=False, snapshot=None, full_audit=True, ownership=None):
    scratch = local_path(scratch)
    if not reuse and scratch.exists():
        raise ValueError('Validation scratch must not already exist')
    if reuse and not scratch.is_file():
        raise ValueError('Reused validation scratch must already exist')
    if not reuse:
        with scratch.open('xb'):
            pass
    count = 0
    try:
        with closing(sqlite3.connect(scratch)) as target:
            if not reuse:
                target.execute(conn.execute("SELECT sql FROM sqlite_master WHERE name='cardknowledge'").fetchone()[0])
                rows = conn.execute('SELECT * FROM cardknowledge')
                columns = len(rows.description)
                target.executemany('INSERT INTO cardknowledge VALUES (' + ','.join('?' for _ in range(columns)) + ')', rows)
                if ownership is not None:
                    target.execute('CREATE TABLE corpus_campaign_owner (json TEXT NOT NULL)')
                    target.execute('INSERT INTO corpus_campaign_owner VALUES (?)', (json.dumps(ownership, sort_keys=True),))
            with gzip.open(artifact, 'rt', encoding='utf-8') as stream:
                manifest = json.loads(next(stream))['manifest']
                if manifest['version'] != VERSION or manifest['snapshot'] != (snapshot or audit(conn)['knowledge_rows_sha256']):
                    raise ValueError('Artifact is for a different canonical snapshot')
                seen = set()
                for line in stream:
                    patch = json.loads(line)
                    if patch['id'] in seen:
                        raise ValueError('Duplicate artifact row')
                    seen.add(patch['id'])
                    row = target.execute('SELECT name,scryfall_id,profiles_json FROM cardknowledge WHERE id=?', (patch['id'],)).fetchone()
                    original = conn.execute('SELECT name,scryfall_id,profiles_json FROM cardknowledge WHERE id=?', (patch['id'],)).fetchone()
                    if (not row or not original or row[:2] != (patch['name'], patch['scryfall_id'])
                            or tuple(original[:2]) != row[:2] or canonical_hash(json.loads(original[2])) != patch['before_profile_sha256']
                            or canonical_hash(json.loads(row[2])) not in {patch['before_profile_sha256'], patch['after_profile_sha256']}):
                        raise ValueError('Import precondition failed')
                    profile = validate_profile_patch(original, patch, manifest)
                    target.execute('UPDATE cardknowledge SET profiles_json=? WHERE id=?', (json.dumps(profile, sort_keys=True), patch['id']))
                    saved = target.execute('SELECT profiles_json FROM cardknowledge WHERE id=?', (patch['id'],)).fetchone()[0]
                    if canonical_hash(json.loads(saved)) != patch['after_profile_sha256']:
                        raise ValueError('Stored patch hash mismatch')
                    count += 1
            target.commit()
            if full_audit and target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('Scratch integrity check failed')
        if full_audit:
            with closing(readonly(scratch)) as check:
                report = audit(check)
            return {'validated_import_rows': count, 'scratch_sha256': file_hash(scratch), 'after': report}
        return {'validated_import_rows': count, 'source_snapshot_sha256': snapshot, 'artifact_sha256': file_hash(artifact), 'stored_row_hashes_verified': True, 'sqlite_transaction_committed': True}
    except Exception:
        if not reuse:
            scratch.unlink(missing_ok=True)
        raise


def campaign_scratch_owned(scratch, ownership):
    scratch = local_path(scratch)
    if not scratch.exists():
        return False
    with closing(readonly(scratch)) as check:
        if not check.execute("SELECT 1 FROM sqlite_master WHERE name='corpus_campaign_owner'").fetchone():
            raise ValueError('Existing scratch has no committed campaign ownership; preserve it for explicit audit')
        rows = check.execute('SELECT json FROM corpus_campaign_owner').fetchall()
        if len(rows) != 1 or json.loads(rows[0][0]) != ownership:
            raise ValueError('Existing scratch belongs to a different campaign')
        if not check.execute("SELECT 1 FROM sqlite_master WHERE name='cardknowledge'").fetchone():
            raise ValueError('Owned scratch is missing canonical rows')
    return True


def verify_campaign_profiles(conn, args, *, final=False):
    """Check delivered artifact/checkpoint/full-profile equality without repair."""
    with closing(readonly(args.state)) as state, closing(readonly(args.scratch)) as scratch:
        has_delivered = state.execute("SELECT 1 FROM sqlite_master WHERE name='delivered'").fetchone()
        delivered = dict(state.execute('SELECT id,artifact_sha256 FROM delivered')) if has_delivered else {}
        completed = {row['id']: json.loads(row['patch']) if row['patch'] else None
                     for row in state.execute('SELECT id,patch FROM completed')}
        checkpoint_snapshot = json.loads(state.execute('SELECT json FROM config').fetchone()[0])['snapshot']
        delivered_digests = set(delivered.values())
        paths = [args.seed_artifact, *sorted(args.out.glob('batch-*.jsonl.gz'))]
        expected_by_digest = {}
        for path in paths:
            digest = file_hash(path)
            if digest not in delivered_digests:
                continue
            receipt_path = args.out / 'seed-validation.json' if path == args.seed_artifact else path.with_name(path.name + '.validated.json')
            receipt = json.loads(receipt_path.read_text())
            if (receipt.get('artifact_sha256') != digest or not receipt.get('stored_row_hashes_verified')
                    or not receipt.get('sqlite_transaction_committed')):
                raise ValueError('Delivered artifact receipt evidence mismatch')
            patches = {}
            with gzip.open(path, 'rt') as stream:
                manifest = json.loads(next(stream))['manifest']
                if manifest['snapshot'] != checkpoint_snapshot:
                    raise ValueError('Delivered artifact checkpoint snapshot mismatch')
                for line in stream:
                    patch = json.loads(line)
                    if patch['id'] in patches or canonical_hash(patch['profile']) != patch['after_profile_sha256']:
                        raise ValueError('Delivered artifact payload hash/duplicate mismatch')
                    patches[patch['id']] = patch
            if receipt.get('source_snapshot_sha256') != manifest['snapshot'] or receipt.get('validated_import_rows') != len(patches):
                raise ValueError('Delivered artifact receipt snapshot/count mismatch')
            expected_by_digest[digest] = (manifest['snapshot'], patches)
        snapshot = None
        for row_id, digest in delivered.items():
            if digest not in expected_by_digest:
                raise ValueError('Delivered artifact bytes no longer match checkpoint digest')
            artifact_snapshot, patches = expected_by_digest[digest]
            snapshot = artifact_snapshot if snapshot is None else snapshot
            patch = completed.get(row_id)
            if artifact_snapshot != snapshot or patch is None or patches.get(row_id) != patch:
                raise ValueError('Delivered checkpoint/artifact full payload mismatch')
            original = conn.execute('SELECT name,scryfall_id,profiles_json FROM cardknowledge WHERE id=?', (row_id,)).fetchone()
            saved = scratch.execute('SELECT name,scryfall_id,profiles_json FROM cardknowledge WHERE id=?', (row_id,)).fetchone()
            if (not original or not saved or original['name'] != patch['name'] or original['scryfall_id'] != patch['scryfall_id']
                    or canonical_hash(load_profile(original)) != patch['before_profile_sha256']
                    or saved['name'] != patch['name'] or saved['scryfall_id'] != patch['scryfall_id']
                    or canonical_hash(load_profile(saved)) != patch['after_profile_sha256']):
                raise ValueError('Delivered scratch full-profile/precondition hash mismatch')
        checked = len(delivered)
        if final:
            checked = 0
            for original, saved in zip(conn.execute('SELECT * FROM cardknowledge ORDER BY id'), scratch.execute('SELECT * FROM cardknowledge ORDER BY id'), strict=True):
                patch = completed.get(original['id'])
                expected = patch['after_profile_sha256'] if patch else canonical_hash(load_profile(original))
                if (original['id'] != saved['id'] or canonical_hash(load_profile(saved)) != expected
                        or (patch and original['id'] not in delivered)):
                    raise ValueError('Final all-row full-profile/checkpoint equality failed')
                checked += 1
        return {'delivered_artifact_checkpoint_profile_rows_verified': len(delivered),
                'all_row_full_profile_equality_verified': checked if final else None}


def campaign(conn, args):
    """Reuse one source snapshot/index; publish and validate <=500-row deltas."""
    root = args.out
    root.mkdir(parents=True, exist_ok=True)
    resumed = (root / 'run-config.json').exists()
    if resumed and not args.resume_campaign:
        raise FileExistsError('Existing campaign requires explicit --resume-campaign')
    if not resumed:
        new_outputs(root / 'run-config.json', root / 'baseline-readiness.json', root / 'seed-validation.json')
    context = prepare_inputs(conn, args)
    report = context[-1]
    snapshot = report['knowledge_rows_sha256']
    if file_hash(args.seed_artifact) != args.seed_artifact_sha256:
        raise ValueError('Seed artifact hash mismatch')
    run_config = {'source_snapshot_sha256': snapshot, 'source_database_sha256': file_hash(args.database),
                 'batch_limit': args.limit, 'seed_artifact_sha256': args.seed_artifact_sha256, 'tags': 'preserve_existing' if not args.refresh_tags_sha256 else args.refresh_tags_sha256,
                 'mechanics': args.materialize_mechanics_version or 'preserve_existing', 'source_provenance': {'cards': context[0], 'rulings': context[1]},
                 'card_refresh_sha256': args.card_refresh_sha256, 'state': str(args.state.resolve()), 'scratch': str(args.scratch.resolve())}
    if resumed:
        if json.loads((root / 'run-config.json').read_text()) != run_config:
            raise ValueError('Campaign resume configuration changed')
        if (root / 'campaign-summary.json').exists():
            raise FileExistsError('Campaign is already complete; preserve and inspect the existing report')
    else:
        new_outputs(local_path(args.scratch))
        publish_json(root / 'run-config.json', run_config)
    baseline = root / 'baseline-readiness.json'
    if baseline.exists():
        if json.loads(baseline.read_text())['knowledge_rows_sha256'] != snapshot:
            raise ValueError('Campaign baseline snapshot mismatch')
    else:
        publish_json(root / 'baseline-readiness.json', report)
    ownership = {'campaign_directory': str(root.resolve()), 'run_config_sha256': canonical_hash(run_config)}
    reuse_scratch = campaign_scratch_owned(args.scratch, ownership)
    if not reuse_scratch:
        with closing(readonly(args.state)) as state:
            delivered_table = state.execute("SELECT 1 FROM sqlite_master WHERE name='delivered'").fetchone()
            has_delivery = delivered_table and state.execute('SELECT 1 FROM delivered LIMIT 1').fetchone()
        if (root / 'seed-validation.json').exists() or has_delivery:
            raise ValueError('Committed campaign scratch is missing; preserve evidence for explicit recovery')
    if reuse_scratch:
        verify_campaign_profiles(conn, args)
    seed = validate_artifact(conn, args.seed_artifact, args.scratch, reuse=reuse_scratch, snapshot=snapshot, full_audit=False, ownership=ownership)
    receipt = root / 'seed-validation.json'
    if receipt.exists():
        if json.loads(receipt.read_text()) != seed:
            raise ValueError('Existing seed receipt differs; refusing replacement')
    else:
        publish_json(root / 'seed-validation.json', seed)
    with closing(sqlite3.connect(local_path(args.state))) as state:
        state.execute('CREATE TABLE IF NOT EXISTS delivered (id INTEGER PRIMARY KEY, artifact_sha256 TEXT NOT NULL)')
        with gzip.open(args.seed_artifact, 'rt') as stream:
            next(stream)
            for line in stream:
                patch = json.loads(line)
                saved = state.execute('SELECT patch FROM completed WHERE id=?', (patch['id'],)).fetchone()
                if not saved or not saved[0] or json.loads(saved[0])['after_profile_sha256'] != patch['after_profile_sha256']:
                    raise ValueError('Seed artifact differs from resumed checkpoint')
                state.execute('INSERT OR IGNORE INTO delivered VALUES (?,?)', (patch['id'], args.seed_artifact_sha256))
        state.commit()
    sequence = max((int(path.name.split('-')[1].split('.')[0]) for path in root.glob('batch-*.jsonl.gz')), default=0)
    while True:
        sequence += 1
        out = root / f'batch-{sequence:05d}.jsonl.gz'
        with closing(sqlite3.connect(args.state)) as state:
            pending = list(state.execute('SELECT id,patch FROM completed WHERE patch IS NOT NULL AND id NOT IN (SELECT id FROM delivered) ORDER BY id LIMIT ?', (args.limit,)))
            config = json.loads(state.execute('SELECT json FROM config').fetchone()[0])
        if pending:
            digest = publish_artifact(out, config, (row[1] for row in pending))
            result = {'processed_this_run': 0, 'recovered_pending_patches': len(pending), 'artifact_sha256': digest}
        else:
            batch_args = SimpleNamespace(**vars(args))
            batch_args.out = out
            batch_args.batch_artifact = True
            result = prepare(conn, batch_args, context)
        digest = file_hash(out)
        if digest != result['artifact_sha256']:
            raise ValueError('Published artifact digest changed')
        validation = validate_artifact(conn, out, args.scratch, reuse=True, snapshot=snapshot, full_audit=False)
        if digest != file_hash(out):
            raise ValueError('Artifact changed during validation')
        publish_json(out.with_name(out.name + '.validated.json'), validation)
        with closing(sqlite3.connect(args.state)) as state:
            with gzip.open(out, 'rt') as stream:
                next(stream)
                for line in stream:
                    state.execute('INSERT OR IGNORE INTO delivered VALUES (?,?)', (json.loads(line)['id'], digest))
            state.commit()
            counts = dict(zip(('processed_unique', 'prepared_patches', 'refused'), state.execute('SELECT count(*),coalesce(sum(patch IS NOT NULL),0),coalesce(sum(error IS NOT NULL),0) FROM completed').fetchone()))
            counts['validated_unique'] = state.execute('SELECT count(*) FROM delivered').fetchone()[0]
            counts['outstanding_unprocessed'] = len(report['cards']) - counts['processed_unique']
            counts['pending_validation'] = counts['prepared_patches'] - counts['validated_unique']
        progress = {**counts, 'pid': os.getpid(), 'batch': sequence, 'artifact': str(out), 'artifact_sha256': digest,
                    'batch_processed': result.get('processed_this_run', 0), 'batch_validated': validation['validated_import_rows'], 'source_snapshot_sha256': snapshot,
                    'live_imported_rows': 0, 'trained_competence': 'unknown'}
        publish_json(out.with_name(out.name + '.summary.json'), progress)
        print(json.dumps(progress, sort_keys=True), flush=True)
        if not counts['outstanding_unprocessed'] and not counts['pending_validation']:
            break
    with closing(sqlite3.connect(args.scratch)) as target:
        if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Final scratch integrity check failed')
    with closing(readonly(args.scratch)) as check:
        final_report = audit(check)
        changed_columns, changed_tags = [], []
        refreshed = []
        for before, after in zip(conn.execute('SELECT * FROM cardknowledge ORDER BY id'), check.execute('SELECT * FROM cardknowledge ORDER BY id'), strict=True):
            if any(before[key] != after[key] for key in before.keys() if key != 'profiles_json'):
                changed_columns.append(before['id'])
            old, new = load_profile(before), load_profile(after)
            if any(old.get(key) != new.get(key) for key in ('tactical_tags', 'face_tactical_tags', 'tactical_provenance')) and not args.refresh_tags_sha256:
                changed_tags.append(before['id'])
            if old.get('card_data') != new.get('card_data'):
                refreshed.append(before['id'])
        expected_refresh = [checked_refresh(args)['row_id']] if args.card_refresh else []
        if changed_columns or changed_tags or refreshed != expected_refresh:
            raise ValueError('Final all-row preservation check failed')
    equality = verify_campaign_profiles(conn, args, final=True)
    final = {**progress, **equality, 'scratch_sha256': file_hash(args.scratch), 'integrity_check': 'ok', 'preserved_numeric_and_tag_rows': len(report['cards']),
             'approved_refreshed_card_ids': refreshed, 'after': final_report}
    publish_json(root / 'campaign-summary.json', final)
    print(json.dumps({key: value for key, value in final.items() if key != 'after'}, sort_keys=True), flush=True)


def pinned_bytes(path, expected, max_bytes):
    path = Path(path)
    if not path.is_file():
        raise ValueError(f'Pinned input must be a regular file: {path}')
    with path.open('rb') as stream:
        if os.fstat(stream.fileno()).st_size > max_bytes:
            raise ValueError(f'Pinned input exceeds byte cap: {path}')
        data = stream.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError(f'Pinned input exceeds byte cap: {path}')
    if not expected or hashlib.sha256(data).hexdigest() != expected:
        raise ValueError(f'Pinned file digest mismatch: {path}')
    return data


def bounded_artifact_lines(data, rows, budget):
    if type(rows) is not int or not 0 < rows <= 500:
        raise ValueError('Artifact row bound must be 1..500')
    expanded = 0
    with gzip.open(io.BytesIO(data), 'rb') as stream:
        for _ in range(rows + 1):  # One manifest and exactly the indexed rows.
            allowance = min(MAX_ARTIFACT_LINE_BYTES, MAX_ARTIFACT_EXPANDED_BYTES - expanded,
                            MAX_TOTAL_EXPANDED_BYTES - budget['expanded'])
            line = stream.readline(allowance + 1)
            if len(line) > allowance:
                raise ValueError('Artifact expanded line/total byte cap exceeded')
            if not line:
                raise ValueError('Truncated artifact: missing indexed rows/manifest')
            expanded += len(line)
            budget['expanded'] += len(line)
            yield line
        # Probe one byte, never allocate the unindexed next line. This also
        # forces gzip EOF/trailer validation, including concatenated members.
        if stream.read(1):
            raise ValueError('Artifact exceeds indexed row/500-record bound')


def checked_apply_refresh(args):
    if not args.card_refresh:
        return None
    packet_data = pinned_bytes(args.card_refresh, args.card_refresh_sha256, MAX_REFRESH_BYTES)
    packet = json.loads(packet_data)
    response_data = pinned_bytes(packet['response_archive'], packet['provenance']['archive_sha256'], MAX_REFRESH_BYTES)
    return checked_refresh(args, packet_bytes=packet_data, response_bytes=response_data)


def offline_copy_path(path):
    path = Path(path).absolute()
    if any(item.is_symlink() for item in (path, *path.parents)):
        raise ValueError('Offline SQLite paths cannot contain symlinks')
    path = local_path(path)
    if not path.is_file() or path.stat().st_nlink != 1:
        raise ValueError('Offline SQLite must be an existing independent file, not a hardlink')
    if path.name == 'mtg_lab.db':
        raise ValueError('Refusing the application database name; supply a named offline copy')
    if any(item.exists() or item.is_symlink() for item in (Path(str(path) + suffix) for suffix in ('-wal', '-shm', '-journal'))):
        raise ValueError('Offline SQLite has active/recovery sidecars; preserve it for explicit audit')
    return path


def knowledge_snapshot(conn):
    rows, profile_bytes = conn.execute('SELECT count(*),coalesce(max(length(CAST(profiles_json AS BLOB))),0) FROM cardknowledge').fetchone()
    if rows > MAX_SOURCE_ROWS or profile_bytes > MAX_SOURCE_PROFILE_BYTES:
        raise ValueError('Source knowledge row/profile resource cap exceeded')
    digest = hashlib.sha256()
    ids = set()
    for row in conn.execute('SELECT * FROM cardknowledge ORDER BY id'):
        ids.add(row['id'])
        digest.update(f"{row['id']}:{canonical_hash(dict(row))}\n".encode())
    return digest.hexdigest(), ids


def knowledge_only_authorizer(action, table, column, database, trigger):
    if action == sqlite3.SQLITE_UPDATE:
        return sqlite3.SQLITE_OK if (table, column, database, trigger) == ('cardknowledge', 'profiles_json', 'main', None) else sqlite3.SQLITE_DENY
    blocked = {sqlite3.SQLITE_INSERT, sqlite3.SQLITE_DELETE, sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH,
               sqlite3.SQLITE_CREATE_TABLE, sqlite3.SQLITE_DROP_TABLE, sqlite3.SQLITE_ALTER_TABLE,
               sqlite3.SQLITE_CREATE_INDEX, sqlite3.SQLITE_DROP_INDEX, sqlite3.SQLITE_CREATE_TRIGGER,
               sqlite3.SQLITE_DROP_TRIGGER, sqlite3.SQLITE_CREATE_VIEW, sqlite3.SQLITE_DROP_VIEW,
               sqlite3.SQLITE_CREATE_VTABLE, sqlite3.SQLITE_DROP_VTABLE}
    if action in blocked or (action == sqlite3.SQLITE_PRAGMA and column is not None):
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def apply_index(conn, args):
    """Explicit, non-resumable, all-or-nothing application to an offline copy."""
    new_outputs(args.out, args.out.with_name(args.out.name + '.part'))
    source = offline_copy_path(args.database)
    target = offline_copy_path(args.target)
    if os.path.samefile(source, target):
        raise ValueError('Source and target must be distinct independent copies')
    source_sha = file_hash(source)
    if not args.target_sha256 or file_hash(target) != args.target_sha256 or source_sha != args.target_sha256:
        raise ValueError('Target must be an exact digest-pinned byte copy of the supplied source')
    identity = (target.stat().st_dev, target.stat().st_ino)
    index = json.loads(pinned_bytes(args.index, args.index_sha256, MAX_INDEX_BYTES))
    entries = index.get('artifacts')
    if not isinstance(entries, list) or not 0 < len(entries) <= MAX_INDEX_ENTRIES:
        raise ValueError('Index artifact entry cap exceeded/invalid')
    snapshot, source_ids = knowledge_snapshot(conn)
    if (index.get('duplicate_rows') != 0 or index.get('live_imported_rows') != 0
            or index.get('validated_unique_rows') != len(source_ids) or not index.get('artifacts')):
        raise ValueError('Index must describe complete, unique, offline-validated source coverage')
    refresh = checked_apply_refresh(args)
    if index.get('card_refresh_packet_sha256') != getattr(args, 'card_refresh_sha256', None):
        raise ValueError('Index refresh packet pin differs from supplied verified evidence')
    if index.get('card_refresh_response_sha256') != (refresh['provenance']['archive_sha256'] if refresh else None):
        raise ValueError('Index refresh response pin differs from supplied verified evidence')
    expected_refresh = {key: value for key, value in refresh.items() if key not in ('card_data', 'response_archive', 'differing_fields')} if refresh else None
    seen, expected_rows, source_evidence = set(), {}, []
    budget = {'expanded': 0, 'staged': 0}
    # Freeze verified payload bytes locally before the target transaction. Each
    # NFS artifact is read once into a bounded buffer, never reread for writes.
    with tempfile.TemporaryFile(mode='w+t', encoding='utf-8', dir=target.parent) as staged:
        for entry in entries:
            if type(entry.get('rows')) is not int or not 0 < entry['rows'] <= 500 or entry.get('source_snapshot_sha256') != snapshot:
                raise ValueError('Index batch bounds/source snapshot mismatch')
            receipt = json.loads(pinned_bytes(entry['validation_receipt'], entry['receipt_sha256'], MAX_RECEIPT_BYTES))
            if (receipt.get('artifact_sha256') != entry['sha256'] or receipt.get('source_snapshot_sha256') != snapshot
                    or receipt.get('validated_import_rows') != entry['rows']
                    or receipt.get('stored_row_hashes_verified') is not True or receipt.get('sqlite_transaction_committed') is not True):
                raise ValueError('Index receipt evidence mismatch')
            data = pinned_bytes(entry['artifact'], entry['sha256'], MAX_COMPRESSED_ARTIFACT_BYTES)
            count = 0
            with closing(bounded_artifact_lines(data, entry['rows'], budget)) as stream:
                manifest = json.loads(next(stream))['manifest']
                if manifest.get('version') != VERSION or manifest.get('snapshot') != snapshot or manifest.get('tags') != 'preserve_existing':
                    raise ValueError('Application requires matching source and preservation-only tags')
                if manifest.get('card_refresh') not in (None, expected_refresh):
                    raise ValueError('Artifact refresh descriptor is not verified by the index evidence')
                evidence = {'cards': manifest['cards'], 'rulings': manifest.get('rulings'), 'mechanics': manifest.get('mechanics')}
                if source_evidence and evidence != source_evidence[0]:
                    raise ValueError('Indexed artifacts have inconsistent source/metadata intent')
                if not source_evidence:
                    source_evidence.append(evidence)
                for line in stream:
                    patch = json.loads(line)
                    if patch['id'] in seen or patch['id'] not in source_ids:
                        raise ValueError('Duplicate or foreign index row')
                    original = conn.execute('SELECT * FROM cardknowledge WHERE id=?', (patch['id'],)).fetchone()
                    profile = validate_profile_patch(original, patch, manifest)
                    if any(load_profile(original).get(key) != profile.get(key) for key in ('tactical_tags', 'face_tactical_tags', 'tactical_provenance')):
                        raise ValueError('Application must preserve every legacy tag/version')
                    encoded = json.dumps(profile, sort_keys=True)
                    after = {**dict(original), 'profiles_json': encoded}
                    expected_rows[patch['id']] = canonical_hash(after)
                    staged_line = json.dumps({'id': patch['id'], 'before_row_sha256': canonical_hash(dict(original)),
                                              'after_profile_sha256': patch['after_profile_sha256'], 'profiles_json': encoded}) + '\n'
                    budget['staged'] += len(staged_line.encode('utf-8'))
                    if budget['staged'] > MAX_STAGE_BYTES:
                        raise ValueError('Application local staging byte cap exceeded')
                    staged.write(staged_line)
                    seen.add(patch['id'])
                    count += 1
            if count != entry['rows']:
                raise ValueError('Artifact row count differs from pinned receipt/index')
        if seen != source_ids:
            raise ValueError('Index coverage is incomplete')
        staged.flush()
        with closing(sqlite3.connect(target.as_uri() + '?mode=rw', uri=True, timeout=0, isolation_level=None)) as writable:
            writable.row_factory = sqlite3.Row
            writable.set_authorizer(knowledge_only_authorizer)
            writable.execute('BEGIN EXCLUSIVE')
            try:
                if (offline_copy_path(target) != target or (target.stat().st_dev, target.stat().st_ino) != identity
                        or file_hash(target) != args.target_sha256 or knowledge_snapshot(writable)[0] != snapshot):
                    raise ValueError('Target identity/content changed before exclusive transaction')
                staged.seek(0)
                for line in staged:
                    patch = json.loads(line)
                    current = writable.execute('SELECT * FROM cardknowledge WHERE id=?', (patch['id'],)).fetchone()
                    if not current or canonical_hash(dict(current)) != patch['before_row_sha256']:
                        raise ValueError('Target row precondition failed before any updates')
                staged.seek(0)
                for line in staged:
                    patch = json.loads(line)
                    writable.execute('UPDATE cardknowledge SET profiles_json=? WHERE id=?', (patch['profiles_json'], patch['id']))
                for row in writable.execute('SELECT * FROM cardknowledge ORDER BY id'):
                    if canonical_hash(dict(row)) != expected_rows.get(row['id']):
                        raise ValueError('Target full-row equality failed; rollback required')
                if writable.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise ValueError('Target integrity check failed; rollback required')
                if file_hash(source) != source_sha or file_hash(args.index) != args.index_sha256:
                    raise ValueError('Source/index changed during application; rollback required')
                after_snapshot = knowledge_snapshot(writable)[0]
                writable.execute('COMMIT')
            except BaseException:
                if writable.in_transaction:
                    writable.execute('ROLLBACK')
                raise
    return {'action': 'apply-index', 'source_database': str(source), 'source_database_sha256': source_sha,
            'source_snapshot_sha256': snapshot, 'target_database': str(target), 'target_before_sha256': args.target_sha256,
            'target_after_sha256': file_hash(target), 'target_after_snapshot_sha256': after_snapshot,
            'index': str(args.index), 'index_sha256': args.index_sha256, 'applied_rows': len(seen), 'artifacts_verified': len(index['artifacts']),
            'sqlite_transaction_committed': True, 'integrity_check': 'ok', 'complete_row_hashes_verified': True,
            'nonprofile_columns_numeric_tags_preserved': True, 'cardcache_and_game_table_writes': 0, 'live_imported_rows': 0,
            'source_provenance': source_evidence[0], 'card_refresh_packet_sha256': getattr(args, 'card_refresh_sha256', None),
            'resource_usage': budget,
            'resource_caps': {'index_bytes': MAX_INDEX_BYTES, 'receipt_bytes': MAX_RECEIPT_BYTES,
                              'compressed_artifact_bytes': MAX_COMPRESSED_ARTIFACT_BYTES, 'line_bytes': MAX_ARTIFACT_LINE_BYTES,
                              'artifact_expanded_bytes': MAX_ARTIFACT_EXPANDED_BYTES, 'total_expanded_bytes': MAX_TOTAL_EXPANDED_BYTES,
                              'staged_bytes': MAX_STAGE_BYTES, 'refresh_bytes': MAX_REFRESH_BYTES, 'source_profile_bytes': MAX_SOURCE_PROFILE_BYTES,
                              'source_rows': MAX_SOURCE_ROWS, 'index_entries': MAX_INDEX_ENTRIES, 'artifact_rows': 500},
            'trained_competence': 'unknown', 'rules_support_certified': False,
            'limitations': ['Digest/receipt checks establish pinned byte and precondition identity, not independent publisher authentication or upstream freshness.',
                            'This action applies only to an explicit offline copy; deployment/backup/reload require separate parent approval.',
                            'Do not retry a committed application if receipt publication fails; preserve target and audit its hashes.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['report', 'prepare', 'validate', 'fetch-rulings', 'fetch-card', 'campaign', 'apply-index'])
    parser.add_argument('--database', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--cards', type=Path)
    parser.add_argument('--cards-sha256')
    parser.add_argument('--cards-manifest', type=Path)
    parser.add_argument('--rulings', type=Path)
    parser.add_argument('--rulings-sha256')
    parser.add_argument('--rulings-manifest', type=Path)
    parser.add_argument('--state', type=Path)
    parser.add_argument('--refresh-tags-sha256', help='Explicit opt-in pinned to the current tactical.py hash; default preserves tags/version')
    parser.add_argument('--materialize-mechanics-version', help='Explicit nested-only materialization pin after installing reviewed workstream B; max 500 rows/run, default preserves nested metadata')
    parser.add_argument('--limit', type=int, default=500)
    parser.add_argument('--artifact', type=Path)
    parser.add_argument('--scratch', type=Path)
    parser.add_argument('--target', type=Path, help='Existing independent offline byte copy; no default/live target')
    parser.add_argument('--target-sha256', help='Required pin for the unmodified offline target and identical source file')
    parser.add_argument('--index', type=Path)
    parser.add_argument('--index-sha256')
    parser.add_argument('--row-id', type=int)
    parser.add_argument('--card-refresh', type=Path)
    parser.add_argument('--card-refresh-sha256')
    parser.add_argument('--resume-audit-version-change', action='store_true', help='Preserve old config in history; permit audit-only version changes with unchanged snapshot and preservation policy')
    parser.add_argument('--seed-artifact', type=Path)
    parser.add_argument('--seed-artifact-sha256')
    parser.add_argument('--resume-campaign', action='store_true', help='Explicitly resume the same immutable campaign/configuration without replacing completed outputs')
    args = parser.parse_args()
    if args.action == 'fetch-rulings':
        print(json.dumps(fetch_rulings(args.out), sort_keys=True))
        return 0
    if not args.database:
        parser.error('database is required except for fetch-rulings')
    if args.limit < 1 or args.limit > 50000:
        parser.error('limit must be 1..50000')
    if args.action in {'prepare', 'campaign'} and (not args.cards or not args.cards_sha256 or not args.state or bool(args.rulings) != bool(args.rulings_sha256)):
        parser.error('prepare requires cards, cards-sha256, state, and a hash for supplied rulings')
    if args.action == 'validate' and (not args.artifact or not args.scratch):
        parser.error('validate requires artifact and a new local scratch path')
    if bool(args.card_refresh) != bool(args.card_refresh_sha256):
        parser.error('card refresh requires a pinned packet hash')
    if args.action == 'fetch-card' and args.row_id is None:
        parser.error('fetch-card requires row-id')
    if args.action == 'campaign' and (not args.scratch or args.limit > 500 or not args.seed_artifact or not args.seed_artifact_sha256):
        parser.error('campaign requires local scratch, limit <=500, seed artifact and pinned seed hash')
    if args.action == 'apply-index' and (not args.target or not args.target_sha256 or not args.index or not args.index_sha256):
        parser.error('apply-index requires explicit target, target-sha256, index and index-sha256')
    if args.action == 'apply-index':
        offline_copy_path(args.database)
        offline_copy_path(args.target)
    inputs = [args.database, args.cards, args.rulings, args.cards_manifest, args.rulings_manifest, args.artifact, args.card_refresh, args.seed_artifact, args.index, args.target]
    outputs = [args.out, args.out.with_suffix(args.out.suffix + '.summary.json'), args.state, args.scratch]
    if any(left.resolve() == right.resolve() for left in inputs if left for right in outputs if right):
        parser.error('output/state/scratch paths must not overwrite inputs')
    output_paths = [path.resolve() for path in outputs if path]
    if len(output_paths) != len(set(output_paths)):
        parser.error('output/state/scratch paths must be distinct')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.action not in {'prepare', 'campaign'}:
        new_outputs(args.out, args.out.with_name(args.out.name + '.part'))
    with closing(readonly(args.database)) as conn:
        if args.action == 'report':
            result = audit(conn)
        elif args.action == 'prepare':
            result = prepare(conn, args)
        elif args.action == 'validate':
            result = validate_artifact(conn, args.artifact, args.scratch)
        elif args.action == 'apply-index':
            result = apply_index(conn, args)
        elif args.action == 'fetch-card':
            result = fetch_card(conn, args.out, args.row_id)
            print(json.dumps({'row_id': args.row_id, 'packet_sha256': file_hash(args.out), 'differing_fields': result['differing_fields']}, sort_keys=True))
            return 0
        else:
            campaign(conn, args)
            return 0
    output = args.out.with_suffix(args.out.suffix + '.summary.json') if args.action == 'prepare' else args.out
    try:
        publish_json(output, result)
    except Exception as exc:
        if args.action == 'apply-index':
            raise RuntimeError('Offline database transaction committed but report publication failed; preserve target, audit hashes, do not retry blindly') from exc
        raise
    print(json.dumps({key: value for key, value in result.items() if key not in ('cards', 'decks', 'after', 'provenance', 'errors_detail')}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
