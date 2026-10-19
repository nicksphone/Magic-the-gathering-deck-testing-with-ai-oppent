"""Finite full-RAW admissions; synthetic replacement protocols are not printed facts."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from card_data.sync import ScryfallSyncService
from game_state.state import MatchFactory, Zone
from tests.library_canonical_fixtures import PRINTED


FIXTURES = Path(__file__).parent / 'fixtures'
SOURCES = FIXTURES / 'prevention_replacement_canonical_fb531/SOURCES.json'
SOURCES_SHA = 'c45888fa1045eac22d4143ae516fca4a6737af8037e881757eaa3e6db6ab688e'


def raw_card(name):
    data = SOURCES.read_bytes()
    assert hashlib.sha256(data).hexdigest() == SOURCES_SHA
    row = json.loads(data)[name]
    proof = FIXTURES / row['provenance']['path']
    assert hashlib.sha256(proof.read_bytes()).hexdigest() == row['provenance']['sha256']
    data = (FIXTURES / row['path']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == row['file_sha256']
    raw = json.loads(data.splitlines()[row['line'] - 1]) if row['line'] else json.loads(data)
    for key in row['steps']:
        raw = raw[key]
    assert raw['object'] == 'card' and raw['name'] == name
    assert raw['id'] == row['id'] and raw['oracle_id'] == row['oracle_id']
    encoded = json.dumps(raw, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    assert hashlib.sha256(encoded).hexdigest() == row['object_sha256']
    return raw


def deck_entry(name, quantity):
    raw = raw_card(name)
    cached = ScryfallSyncService._normalize_payload(raw, ScryfallSyncService._extract_remote_image_uri(raw))
    return {**raw, **cached, 'card_name': name, 'quantity': quantity,
            'colors': raw['colors'], 'card_faces': json.loads(cached['card_faces_json'])}


def canonical_card(name, **pose):
    if PRINTED.intersection(pose):
        raise ValueError('Printed fields are not fixture pose overrides')
    entry = deck_entry(name, 8)
    sample = MatchFactory.from_decks([entry], [], seed=0)
    template = next(card for card in sample.cards.values() if card.zone == Zone.LIBRARY)
    return replace(template, **{'instance_order': 0, 'summoning_sick': True, **pose})
