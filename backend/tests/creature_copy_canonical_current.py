"""Reuse the committed complete official catalog for the copy-token fixtures."""
import hashlib
import json
from pathlib import Path
import random

from card_data.sync import ScryfallSyncService
from game_state.state import MatchFactory, Zone
from rules_engine.card_faces import apply_transform_face


CATALOG = Path(__file__).parent / 'fixtures/knowledge_profiles'
RAW_SHA256 = '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732'
PROVENANCE_SHA256 = 'f15047f1ecb06fdaa985a58537d01b6497683637d7caf88db518dea469fc1ca2'
PARENT = 'Fable of the Mirror-Breaker // Reflection of Kiki-Jiki'


def raw_card(name):
    provenance = (CATALOG / 'PROVENANCE.json').read_bytes()
    assert hashlib.sha256(provenance).hexdigest() == PROVENANCE_SHA256
    data = (CATALOG / 'seed155-scryfall.jsonl').read_bytes()
    assert hashlib.sha256(data).hexdigest() == RAW_SHA256
    assert json.loads(provenance)['snapshot_sha256'] == RAW_SHA256
    parent = PARENT if name == 'Reflection of Kiki-Jiki' else name
    return next(row for line in data.splitlines()
                if (row := json.loads(line))['name'] == parent and row['object'] == 'card')


def deck_entry(name, quantity):
    raw = raw_card(name)
    cached = ScryfallSyncService._normalize_payload(raw, None)
    return {**raw, **cached, 'card_name': raw['name'], 'quantity': quantity,
            'colors': raw.get('colors'), 'card_faces': json.loads(cached['card_faces_json'])}


def fixture_decks(seed=49):
    # Declare named stock before the real shuffle, outside its seven opening slots.
    order_rng = random.Random(seed)
    decks = []
    names = [PARENT, 'Bloodtithe Harvester', 'Sheoldred, the Apocalypse', 'Topiary Stomper']
    for _ in range(2):
        permutation = list(range(60))
        order_rng.shuffle(permutation)
        deck = [deck_entry('Forest', 1) for _ in range(60)]
        for position, name in enumerate(names):
            deck[permutation[position]] = deck_entry(name, 1)
        decks.append(deck)
    return decks


def source_id(state, player_id, name):
    return next(cid for cid in state.players[player_id].library
                if state.cards[cid].name == name
                or name == 'Reflection of Kiki-Jiki'
                and state.cards[cid].card_faces
                and state.cards[cid].card_faces[1]['name'] == name)


def place(state, player_id, name):
    cid = source_id(state, player_id, name)
    state.players[player_id].library.remove(cid)
    card = state.cards[cid]
    if name == 'Reflection of Kiki-Jiki':
        apply_transform_face(card, 1)
    card.zone = Zone.BATTLEFIELD
    card.summoning_sick = False
    state.players[player_id].battlefield.append(cid)
    return cid
