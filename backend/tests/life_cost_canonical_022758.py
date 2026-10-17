"""Finite full-RAW materialization for five life-cost/sacrifice fixture cards."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from card_data.sync import ScryfallSyncService
from game_state.state import MatchFactory, Zone


FIXTURES = Path(__file__).parent / 'fixtures'
SOURCES_SHA = '9739e307c7839509b60d2aa0ea58c61bd969c5ccfdb058385c0f36cdff1d8923'


def raw_card(name):
    data = (FIXTURES / 'life_cost_022758/SOURCES.json').read_bytes()
    assert hashlib.sha256(data).hexdigest() == SOURCES_SHA
    record = json.loads(data)['cards'][name]
    data = (FIXTURES / record['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == record['sha256']
    for proof in record['provenance']:
        assert hashlib.sha256((FIXTURES / proof['file']).read_bytes()).hexdigest() == proof['sha256']
    if record['line'] is not None:
        data = data.splitlines()[record['line'] - 1]
    raw = json.loads(data)
    assert hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest() == record['object_sha256']
    assert raw['object'] == 'card' and raw['name'] == name
    assert raw['id'] == record['id'] and raw['oracle_id'] == record['oracle_id']
    return raw


def canonical_card(name, *, id, owner, controller, zone):
    raw = raw_card(name)
    normalized = ScryfallSyncService._normalize_payload(
        raw, ScryfallSyncService._extract_remote_image_uri(raw))
    entry = {**raw, **normalized, 'card_name': name, 'quantity': 8,
             'colors': raw['colors'], 'card_faces': json.loads(normalized['card_faces_json'])}
    sample = MatchFactory.from_decks([entry], [], seed=0)
    template = next(card for card in sample.cards.values() if card.zone == Zone.LIBRARY)
    return replace(template, id=id, owner=owner, controller=controller, zone=zone,
                   instance_order=0)
