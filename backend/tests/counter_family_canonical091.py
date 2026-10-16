"""Finite complete official parents for the counter/entry fixture family."""
import hashlib
import json
from dataclasses import replace
from pathlib import Path

from card_data.sync import ScryfallSyncService
from game_state.state import MatchFactory, Zone, assign_static_order_on_battlefield_entry


FIXTURES = Path(__file__).parent / 'fixtures'
SOURCES_SHA = 'cb92c39da6b683f4ec31a5565c0f83c2b47c81dcb8729c911000d98ead8b486d'


def raw_card(name):
    proof = (FIXTURES / 'counter_family091/SOURCES.json').read_bytes()
    assert hashlib.sha256(proof).hexdigest() == SOURCES_SHA
    record = json.loads(proof)[name]
    data = (FIXTURES / record['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == record['file_sha256']
    value = ([json.loads(line) for line in data.splitlines()]
             if record['format'] == 'jsonl' else json.loads(data))
    rows = value if isinstance(value, list) else [value]
    matches = [row for row in rows if row.get('name') == name]
    assert len(matches) == 1
    raw = matches[0]
    digest = hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(',', ':'),
                                      ensure_ascii=False).encode()).hexdigest()
    assert digest == record['object_sha256']
    assert raw['object'] == 'card' and raw['name'] == name
    assert raw['id'] == record['id'] and raw['oracle_id'] == record['oracle_id']
    return raw


def add_card(state, name, player=1, zone=Zone.BATTLEFIELD, *, cards=None):
    raw = raw_card(name) if cards is None else cards[name]
    normalized = ScryfallSyncService._normalize_payload(
        raw, ScryfallSyncService._extract_remote_image_uri(raw))
    entry = {**raw, **normalized, 'card_name': name, 'quantity': 8,
             'colors': raw['colors'], 'card_faces': json.loads(normalized['card_faces_json'])}
    sample = MatchFactory.from_decks([entry], [], seed=0)
    template = next(card for card in sample.cards.values() if card.zone == Zone.LIBRARY)
    card = replace(template, id=state.allocate_object_id(), owner=player, controller=player,
                   zone=zone, instance_order=0, summoning_sick=True)
    state.cards[card.id] = card
    getattr(state.players[player], zone.value).append(card.id)
    return card


def add(state, name, player=1, zone=Zone.BATTLEFIELD):
    card = add_card(state, name, player, Zone.HAND if zone == Zone.STACK else zone)
    if zone == Zone.STACK:
        state.players[player].hand.remove(card.id)
        card.move_to_zone(Zone.STACK)
    if zone == Zone.BATTLEFIELD:
        assign_static_order_on_battlefield_entry(state, card.id)
    card.summoning_sick = False
    return card
