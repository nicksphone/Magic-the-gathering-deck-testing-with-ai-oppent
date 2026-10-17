"""Test-local complete official admission before normal factory stock capture."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from card_data.sync import ScryfallSyncService
from game_state.state import MatchFactory


FIXTURES = Path(__file__).parent / 'fixtures'
SOURCES_SHA = '7b4e6891174bd118e73b5c5e308183bfea39b1c6644392c7c69bebf6c31b4bc2'


def raw_card(name):
    data = (FIXTURES / 'land_entry_a32/SOURCES.json').read_bytes()
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
    assert len(raw) == record['fields'] >= 60
    return raw


def canonical_row(name, quantity):
    assert type(quantity) is int and quantity > 0
    raw = raw_card(name)
    normalized = ScryfallSyncService._normalize_payload(
        raw, ScryfallSyncService._extract_remote_image_uri(raw))
    return {**raw, **normalized, 'card_name': name, 'quantity': quantity,
            'colors': raw['colors'], 'card_faces': json.loads(normalized['card_faces_json'])}


def canonical_match(left, right, *, seed):
    decks = [[canonical_row(row['card_name'], row['quantity']) for row in deck]
             for deck in (left, right)]
    return MatchFactory.from_decks(*decks, seed=seed)


def canonical_card(name, *, id, owner, controller, zone):
    # The original extra Font/Bolt fixtures are runtime participants, not a
    # rewrite or replacement of any captured original 60-card stock.
    sample = MatchFactory.from_decks([canonical_row(name, 8)], [], seed=0)
    template = next(iter(sample.cards.values()))
    return replace(template, id=id, owner=owner, controller=controller, zone=zone,
                   instance_order=0, summoning_sick=True)
