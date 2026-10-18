"""Full RAW before native birth for only the combat/sacrifice191 fixture sites."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random

from card_data.sync import ScryfallSyncService
from game_state.state import CardInstance, MatchFactory, Zone, _infer_keywords, _infer_power, _infer_toughness
from rules_engine.card_types import printed_card_types
from tests.rules_printed_facts_e4 import PRINTED_FIELDS

FIXTURES = Path(__file__).parent / 'fixtures'
SOURCES_SHA256 = 'd2a6e86eca1faa039e9174f81d4ed6203d0f44c5eebe080de09e0a5267ccaad6'


def raw_card(name):
    data = (FIXTURES / 'combat_sacrifice191/SOURCES.json').read_bytes()
    assert hashlib.sha256(data).hexdigest() == SOURCES_SHA256
    record = json.loads(data)['objects'][name]
    data = (FIXTURES / record['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == record['file_sha256']
    for proof in record['provenance']:
        assert hashlib.sha256((FIXTURES / proof['file']).read_bytes()).hexdigest() == proof['sha256']
    if record['line'] is not None:
        data = data.splitlines()[record['line'] - 1]
        assert hashlib.sha256(data).hexdigest() == record['row_sha256']
    raw = json.loads(data)
    assert raw['object'] == 'card' and raw['name'] == name
    assert raw['id'] == record['id'] and raw['oracle_id'] == record['oracle_id']
    return raw


def deck_entry(name, quantity):
    raw = raw_card(name)
    cached = ScryfallSyncService._normalize_payload(raw, ScryfallSyncService._extract_remote_image_uri(raw))
    return {**raw, **cached, 'card_name': name, 'quantity': quantity,
            'colors': deepcopy(raw['colors']), 'card_faces': json.loads(cached['card_faces_json'])}


def canonical_card(name, **physical):
    if set(physical).intersection((*PRINTED_FIELDS, 'characteristic_record', 'knowledge_snapshot')):
        raise ValueError('Printed facts are not physical fixture overrides')
    cached = deck_entry(name, 1)
    types = printed_card_types(cached['type_line'])
    return CardInstance(name=cached['name'], types=types, oracle_text=cached['oracle_text'],
        mana_cost=cached['mana_cost'], type_line=cached['type_line'],
        power=_infer_power(cached['name'], cached['power'], types),
        toughness=_infer_toughness(cached['name'], cached['toughness'], types),
        printed_power=cached['power'], printed_toughness=cached['toughness'],
        loyalty=int(cached['loyalty']) if cached['loyalty'] is not None else None,
        colors=cached['colors'], keywords=_infer_keywords(cached['oracle_text']),
        layout=cached['layout'], card_faces=deepcopy(cached['card_faces']),
        image_uri=cached['image_uri'], **physical)


def born_combat_position(deck, *, seed, hands):
    if deck not in ([{'quantity': 60, 'card_name': 'Island'}], [{'quantity': 60, 'card_name': 'Forest'}]):
        raise ValueError('Unknown original basic-deck fixture')
    if type(seed) is not int or set(hands) - {1, 2}:
        raise ValueError('Unknown seeded fixture pose')
    preview = random.Random(seed)
    decks = []
    for seat in (1, 2):
        order = list(range(60))
        preview.shuffle(order)
        names = [deck[0]['card_name']] * 60
        for hand_index, name in hands.get(seat, {}).items():
            if type(hand_index) is not int or not 0 <= hand_index < 7:
                raise ValueError('Unknown opening-hand slot')
            names[order[-1-hand_index]] = name
        decks.append([deck_entry(name, 1) for name in names])
    # The real Factory performs its original two shuffles and original stock capture.
    return MatchFactory.from_decks(*decks, seed=seed)


def place_born_card(state, seat, name):
    player = state.players[seat]
    cid = player.hand[0]
    card = state.cards[cid]
    assert card.name == name
    player.hand.remove(cid)
    player.battlefield.append(cid)
    card.zone = Zone.BATTLEFIELD
    card.summoning_sick = False
    return cid
