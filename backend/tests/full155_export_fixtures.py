"""Unchanged verified full155 fixture constructors extracted from frozen audit."""
from copy import deepcopy

import hashlib

import json

from pathlib import Path

import sqlite3

import subprocess

import sys

import pytest

from scripts import export_builtin_oracle_seed as exporter

ROOT = Path(__file__).parents[1]

SEED_PATH = ROOT / 'card_data/builtin_oracle_seed.json'

SEED = json.loads(SEED_PATH.read_text())

BASE = json.loads((Path(__file__).parent / 'fixtures/mh3_seed_gap/seed119_before.json').read_text())

APPEND = json.loads((ROOT / 'card_data/mh3_catalog_seed_provenance.json').read_text())

ADDED = {r['requested_name'] for r in APPEND['records']}

FACE_DIR = Path(__file__).parent / 'fixtures/builtin_face_colors'

FACE_RAW = [json.loads(s) for s in (FACE_DIR / 'canonical.jsonl').read_text().splitlines()]

EVENT_RAW = [json.loads(s) for s in (Path(__file__).parent / 'fixtures/historical_event_catalog/canonical.jsonl').read_text().splitlines()]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def inputs(tmp_path, route='cache', fault='complete'):
    db = tmp_path / 'owned.sqlite'
    with sqlite3.connect(db) as conn:
        conn.execute('CREATE TABLE cardcache(name TEXT,scryfall_id TEXT,oracle_text TEXT,mana_cost TEXT,type_line TEXT,layout TEXT,colors TEXT,power TEXT,toughness TEXT,card_faces_json TEXT,loyalty TEXT)')
        conn.execute('CREATE TABLE cardknowledge(name TEXT,scryfall_id TEXT,oracle_source TEXT,profiles_json TEXT)')
        for name, card in SEED['cards'].items():
            if route == 'knowledge' and name in ADDED:
                raw = next(r for r in EVENT_RAW if r['id'] == card['scryfall_id'])
                conn.execute('INSERT INTO cardknowledge VALUES (?,?,?,?)', (raw['name'], raw['id'], 'scryfall', json.dumps({'card_data': raw})))
                continue
            oracle = card['oracle_text']
            if fault == 'cache_oracle_conflict' and name == 'Monastery Swiftspear':
                oracle += '\n'  # Deliberate corrupt input, not canonical fixture replacement.
            conn.execute('INSERT INTO cardcache VALUES (?,?,?,?,?,?,?,?,?,?,?)', (
                card['name'], card['scryfall_id'], oracle, card['mana_cost'], card['type_line'],
                card['layout'], ','.join(card.get('colors', [])), card.get('power'), card.get('toughness'),
                json.dumps(card.get('card_faces', [])), card.get('loyalty')))
    raws = {r['id']: deepcopy(r) for r in EVENT_RAW}
    raws.update({r['id']: deepcopy(r) for r in FACE_RAW})
    if fault == 'missing_printing':
        raws.pop(FACE_RAW[0]['id'])
    bulk = tmp_path / 'verified.jsonl'
    bulk.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in raws.values()))
    admission = tmp_path / 'admission.json'
    admission.write_bytes((FACE_DIR / 'reviewed_admission.json').read_bytes() if fault != 'missing_admission' else b'[]')
    return db, dict(canonical_bulk=bulk, bulk_sha256=sha(bulk), semantic_admission=admission,
                    admission_sha256='0' * 64 if fault == 'bad_admission_hash' else sha(admission),
                    preservation_seed=SEED_PATH)
