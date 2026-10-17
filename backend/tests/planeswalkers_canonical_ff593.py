"""Complete pinned real-card births; combat/protocol poses stay in their tests."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from card_data.sync import ScryfallSyncService
from game_state.state import MatchFactory, Zone


FIXTURES = Path(__file__).parent / 'fixtures'
SOURCES_SHA = '3e7806b3dd570e7c205a4813ab6dd85115871496a5b2e374d448aba5fd7853a6'
DISPLAY_IMAGE = '/card-images/planeswalkers-fixture.jpg'


def raw_card(name):
    data = (FIXTURES / 'planeswalkers_ff593/SOURCES.json').read_bytes()
    assert hashlib.sha256(data).hexdigest() == SOURCES_SHA
    proof = json.loads(data)
    data = (FIXTURES / proof['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == proof['sha256']
    assert hashlib.sha256((FIXTURES / proof['provenance']).read_bytes()).hexdigest() == proof['provenance_sha256']
    record = proof['cards'][name]
    row = data.splitlines()[record['line'] - 1]
    assert hashlib.sha256(row).hexdigest() == record['row_sha256']
    raw = json.loads(row)
    assert raw['object'] == 'card' and raw['name'] == name
    assert raw['id'] == record['id'] and raw['oracle_id'] == record['oracle_id']
    assert len(raw) == record['fields']
    return raw


def deck_entry(name, quantity):
    raw = raw_card(name)
    normalized = ScryfallSyncService._normalize_payload(raw, DISPLAY_IMAGE)
    return {**raw, **normalized, 'card_name': name, 'quantity': quantity,
            'colors': raw['colors'], 'card_faces': json.loads(normalized['card_faces_json'])}


def canonical_card(name, *, id, owner, controller, zone):
    sample = MatchFactory.from_decks([deck_entry(name, 8)], [], seed=0)
    template = next(card for card in sample.cards.values() if card.zone == Zone.LIBRARY)
    return replace(template, id=id, owner=owner, controller=controller, zone=zone,
                   instance_order=0)
