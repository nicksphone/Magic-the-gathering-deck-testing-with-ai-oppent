"""Finite full-RAW printed facts; the old tests retain their runtime poses."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from card_data.sync import ScryfallSyncService
from game_state.state import MatchFactory, Zone
from tests.library_canonical_fixtures import PRINTED


FIXTURES = Path(__file__).parent / 'fixtures'
SOURCES_SHA = '0587b87b4a78e95c491e08d1427d653f7cde4a8a7ebcaf68439ff0fc3f2bbd6d'


def raw_card(name):
    data = (FIXTURES / 'death_artifact4f86/SOURCES.json').read_bytes()
    assert hashlib.sha256(data).hexdigest() == SOURCES_SHA
    record = json.loads(data)[name]
    data = (FIXTURES / record['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == record['file_sha256']
    raw = json.loads(data.splitlines()[record['line'] - 1]
                     if record['line'] else data)
    for step in record['steps']:
        raw = raw[step]
    assert raw['object'] == 'card' and raw['name'] == name
    assert raw['id'] == record['id'] and raw['oracle_id'] == record['oracle_id']
    digest = hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(',', ':'),
                                      ensure_ascii=False).encode()).hexdigest()
    assert digest == record['object_sha256']
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


def add_card(controller, cid, name, zone, owner=1):
    card = canonical_card(name, id=cid, owner=owner, controller=owner,
                          zone=zone, summoning_sick=False)
    controller.state.cards[cid] = card
    getattr(controller.state.players[owner], zone.value).append(cid)
    return card
