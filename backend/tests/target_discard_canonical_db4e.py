"""Finite official printed facts; existing tests own all runtime poses."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from card_data.sync import ScryfallSyncService
from game_state.state import MatchFactory, Zone
from tests.library_canonical_fixtures import PRINTED


FIXTURES = Path(__file__).parent / 'fixtures'
SOURCES_SHA = '04accba579d442b70e9d36b39b4cddf5547aed32be56b5b7cdb2bb50884bd1ce'


def raw_card(name):
    data = (FIXTURES / 'target_discard_db4e/SOURCES.json').read_bytes()
    assert hashlib.sha256(data).hexdigest() == SOURCES_SHA
    record = json.loads(data)[name]
    data = (FIXTURES / record['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == record['file_sha256']
    raw = json.loads(data.splitlines()[record['line'] - 1] if record['line'] else data)
    for step in record['steps']:
        raw = raw[step]
    assert raw['object'] == 'card' and raw['name'] == name
    assert raw['id'] == record['id'] and raw['oracle_id'] == record['oracle_id']
    assert hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False).encode()).hexdigest() == record['object_sha256']
    return raw


def canonical_card(name, **pose):
    if PRINTED.intersection(pose):
        raise ValueError('Printed facts cannot be runtime overrides')
    raw = raw_card(name)
    normalized = ScryfallSyncService._normalize_payload(
        raw, ScryfallSyncService._extract_remote_image_uri(raw))
    entry = {**raw, **normalized, 'card_name': name, 'quantity': 8,
             'colors': raw['colors'], 'card_faces': json.loads(normalized['card_faces_json'])}
    sample = MatchFactory.from_decks([entry], [], seed=0)
    template = next(card for card in sample.cards.values() if card.zone == Zone.LIBRARY)
    return replace(template, **{'instance_order': 0, 'summoning_sick': True, **pose})


def set_printed(card, name):
    template = canonical_card(name, id=card.id, owner=card.owner,
                              controller=card.controller, zone=card.zone)
    for field in PRINTED:
        setattr(card, field, deepcopy(getattr(template, field)))
