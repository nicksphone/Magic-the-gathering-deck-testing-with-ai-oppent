"""Finite full-RAW births for this cycling and activation fixture slice only."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import random

from card_data.sync import ScryfallSyncService
from game_state.state import MatchFactory, Step, Zone


FIXTURES = Path(__file__).parent / 'fixtures'
SOURCES_SHA = '8836d3da496e7a453f91fb6189758802c09a411c64c45673a30df0569a00bac8'


def raw_card(name):
    data = (FIXTURES / 'cycling_timing_022758/SOURCES.json').read_bytes()
    assert hashlib.sha256(data).hexdigest() == SOURCES_SHA
    row = json.loads(data)['cards'][name]
    data = (FIXTURES / row['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == row['sha256']
    for proof in row['provenance']:
        assert hashlib.sha256((FIXTURES / proof['file']).read_bytes()).hexdigest() == proof['sha256']
    raw = json.loads(data.splitlines()[row['line'] - 1]) if row['line'] else json.loads(data)
    for step in row['steps']:
        raw = raw[step]
    encoded = json.dumps(raw, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    assert hashlib.sha256(encoded).hexdigest() == row['object_sha256']
    assert raw['object'] == 'card' and raw['name'] == name
    assert raw['id'] == row['id'] and raw['oracle_id'] == row['oracle_id']
    return raw


def deck_entry(name, quantity):
    raw = raw_card(name)
    normalized = ScryfallSyncService._normalize_payload(
        raw, ScryfallSyncService._extract_remote_image_uri(raw))
    return {**raw, **normalized, 'card_name': name, 'quantity': quantity,
            'colors': raw['colors'], 'card_faces': json.loads(normalized['card_faces_json'])}


def canonical_card(name, *, id, owner, controller, zone):
    sample = MatchFactory.from_decks([deck_entry(name, 8)], [], seed=0)
    template = next(card for card in sample.cards.values() if card.zone == Zone.LIBRARY)
    return replace(template, id=id, owner=owner, controller=controller, zone=zone,
                   instance_order=0, summoning_sick=True)


def cycling_state():
    deck = [deck_entry('Island', 60)]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = 1
    state.cards['land-1'] = canonical_card(
        'Island', id='land-1', owner=1, controller=1, zone=Zone.BATTLEFIELD)
    state.players[1].battlefield.append('land-1')
    state.cards['cycler'] = canonical_card(
        'Lonely Sandbar', id='cycler', owner=1, controller=1, zone=Zone.HAND)
    state.players[1].hand.append('cycler')
    return state, 'cycler'


def rats_state():
    # Preserve seed 7's original p1-053 library-top reference. The real Rats
    # occupies that shuffle slot before capture, not by rewriting an Island.
    order = list(range(60))
    random.Random(7).shuffle(order)
    rats_slot = order[52]
    deck = [deck_entry('Crypt Rats' if index == rats_slot else 'Island', 1)
            for index in range(60)]
    state = MatchFactory.from_decks(deck, [deck_entry('Island', 60)], seed=7)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = 1
    state.step = Step.PRECOMBAT_MAIN
    source_id = state.players[1].library.pop()
    source = state.cards[source_id]
    assert source_id == 'p1-053' and source.name == 'Crypt Rats'
    source.zone = Zone.BATTLEFIELD
    source.summoning_sick = False
    state.players[1].battlefield.append(source_id)
    return state, source_id
