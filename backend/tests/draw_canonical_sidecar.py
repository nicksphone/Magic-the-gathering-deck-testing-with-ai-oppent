"""Finite complete printed inputs; trusted poses are not casting evidence."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from card_data.sync import ScryfallSyncService
from game_state.state import MatchFactory, Zone
from tests.library_canonical_fixtures import PRINTED


FIXTURES = Path(__file__).parent / 'fixtures'
SOURCES = FIXTURES / 'draw_canonical_sidecar/SOURCES.json'


def raw_card(name):
    record = json.loads(SOURCES.read_bytes())[name]
    data = (FIXTURES / record['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == record['sha256']
    if 'provenance' in record:
        assert hashlib.sha256((FIXTURES / record['provenance']).read_bytes()).hexdigest() == record['provenance_sha256']
    if 'line' in record:
        data = data.splitlines()[record['line'] - 1]
        assert hashlib.sha256(data).hexdigest() == record['object_sha256']
    raw = json.loads(data)
    assert raw['object'] == 'card' and raw['name'] == name
    assert raw['id'] == record['id'] and raw['oracle_id'] == record['oracle_id']
    return raw


def _template(name):
    raw = raw_card(name)
    normalized = ScryfallSyncService._normalize_payload(
        raw, ScryfallSyncService._extract_remote_image_uri(raw))
    entry = {**raw, **normalized, 'card_name': name, 'quantity': 8,
             'colors': raw['colors'], 'card_faces': json.loads(normalized['card_faces_json'])}
    sample = MatchFactory.from_decks([entry], [], seed=0)
    return next(card for card in sample.cards.values() if card.zone == Zone.LIBRARY)


def canonical_card(name, **pose):
    if PRINTED.intersection(pose):
        raise ValueError('Printed facts are not runtime poses')
    return replace(_template(name), **{'instance_order': 0, 'summoning_sick': True, **pose})


def reprint(card, name):
    template = _template(name)
    for field in PRINTED:
        setattr(card, field, deepcopy(getattr(template, field)))


def deck_entry(name, quantity):
    raw = raw_card(name)
    normalized = ScryfallSyncService._normalize_payload(
        raw, ScryfallSyncService._extract_remote_image_uri(raw))
    return {**raw, **normalized, 'card_name': name, 'quantity': quantity,
            'colors': raw['colors'], 'card_faces': json.loads(normalized['card_faces_json'])}
