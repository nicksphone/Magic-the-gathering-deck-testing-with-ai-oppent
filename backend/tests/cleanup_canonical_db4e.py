"""Full official printed facts; existing cleanup/runtime poses remain explicit."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import random

from card_data.sync import ScryfallSyncService
from game_state.state import MatchFactory, Zone
from tests.library_canonical_fixtures import PRINTED

FIXTURES = Path(__file__).parent / 'fixtures'
SOURCES_SHA = '62357c718eea77653f40495709c54bd06d750a3f5d826cc512b58c0671ba5efc'


def raw_card(name):
    data = (FIXTURES / 'cleanup_choices_db4e/SOURCES.json').read_bytes()
    assert hashlib.sha256(data).hexdigest() == SOURCES_SHA
    record = json.loads(data)[name]
    data = (FIXTURES / record['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == record['file_sha256']
    raw = json.loads(data.splitlines()[record['line'] - 1] if record['line'] else data)
    for step in record['steps']:
        raw = raw[step]
    assert raw['object'] == 'card' and raw['name'] == name
    assert raw['id'] == record['id'] and raw['oracle_id'] == record['oracle_id']
    digest = hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(',', ':'),
                                      ensure_ascii=False).encode()).hexdigest()
    assert digest == record['object_sha256']
    return raw


def canonical_entry(name, quantity=8):
    raw = raw_card(name)
    normalized = ScryfallSyncService._normalize_payload(
        raw, ScryfallSyncService._extract_remote_image_uri(raw))
    return {**raw, **normalized, 'card_name': name, 'quantity': quantity,
            'colors': raw['colors'], 'card_faces': json.loads(normalized['card_faces_json'])}


def canonical_card(name, **pose):
    if PRINTED.intersection(pose):
        raise ValueError('Printed facts cannot be runtime overrides')
    sample = MatchFactory.from_decks([canonical_entry(name)], [], seed=0)
    template = next(card for card in sample.cards.values() if card.zone == Zone.LIBRARY)
    return replace(template, **{'instance_order': 0, 'summoning_sick': True, **pose})


def first_draw_deck(name, seed=9):
    # Match the existing first-hand fixture through real birth, not a stock rewrite.
    order = list(range(60))
    random.Random(seed).shuffle(order)
    position = order[-1]
    deck = [canonical_entry('Island', position)] if position else []
    deck.append(canonical_entry(name, 1))
    if position < 59:
        deck.append(canonical_entry('Island', 59 - position))
    return deck


def set_printed(card, name):
    template = canonical_card(name, id=card.id, owner=card.owner,
                              controller=card.controller, zone=card.zone)
    for field in PRINTED:
        setattr(card, field, deepcopy(getattr(template, field)))
