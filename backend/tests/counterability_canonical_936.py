"""Finite full official parents; runtime fixture poses are not printed overrides."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from card_data.sync import ScryfallSyncService
from game_state.state import MatchFactory, Zone
from tests.library_canonical_fixtures import PRINTED

FIXTURES = Path(__file__).parent / 'fixtures'
SOURCES_SHA = '30313d3f08893bac273d3b761022de07fc2e1b4c840ab415e6aeeb75e70c7bf1'


def raw_card(name):
    proof = (FIXTURES / 'counterability_canonical_936/SOURCES.json').read_bytes()
    assert hashlib.sha256(proof).hexdigest() == SOURCES_SHA
    record = json.loads(proof)[name]
    data = (FIXTURES / record['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == record['file_sha256']
    if record['format'] == 'jsonl':
        rows = [json.loads(line) for line in data.splitlines()]
        matches = [row for row in rows if row['name'] == name]
        assert len(matches) == 1
        raw = matches[0]
    else:
        value = json.loads(data)
        raw = value[name] if record['format'] == 'mapping' else value
    body = json.dumps(raw, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    assert hashlib.sha256(body).hexdigest() == record['object_sha256']
    assert raw['object'] == 'card' and raw['name'] == name
    assert raw['id'] == record['id'] and raw['oracle_id'] == record['oracle_id']
    return raw


def deck_entry(name, quantity):
    raw = raw_card(name)
    normalized = ScryfallSyncService._normalize_payload(raw, ScryfallSyncService._extract_remote_image_uri(raw))
    return {**raw, **normalized, 'card_name': name, 'quantity': quantity,
            'colors': raw['colors'], 'card_faces': json.loads(normalized['card_faces_json'])}


def canonical_card(name, **pose):
    if PRINTED.intersection(pose):
        raise ValueError('Printed fields cannot be fixture poses')
    sample = MatchFactory.from_decks([deck_entry(name, 8)], [], seed=0)
    template = next(card for card in sample.cards.values() if card.zone == Zone.LIBRARY)
    return replace(template, **{'instance_order': 0, 'summoning_sick': True, **pose})
