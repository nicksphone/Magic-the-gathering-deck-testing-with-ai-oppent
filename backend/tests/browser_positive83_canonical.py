"""Complete pinned fixture prints, before native birth; scene poses stay separate."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import random

from card_data.sync import ScryfallSyncService
from game_state.state import MatchFactory, Zone


ROOT = Path(__file__).resolve().parents[2]
SOURCES = Path(__file__).parent / 'fixtures/browser_positive83/SOURCES.json'
SOURCES_SHA = 'cb515e9c199a4dba208e3a9c22af8bec840dcc265aeffe9b453706d39d56f994'


def raw_card(name):
    encoded = SOURCES.read_bytes()
    if hashlib.sha256(encoded).hexdigest() != SOURCES_SHA:
        raise ValueError('Fixture source manifest changed')
    record = json.loads(encoded)['cards'][name]
    encoded = (ROOT / record['path']).read_bytes()
    if hashlib.sha256(encoded).hexdigest() != record['file_sha256']:
        raise ValueError('Full fixture source changed')
    location = list(record['location'])
    if location and location[0] == 'line':
        value = json.loads(encoded.splitlines()[location[1] - 1])
        location = location[2:]
    else:
        value = json.loads(encoded)
    for key in location:
        value = value[key]
    digest = hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    if (value.get('object') != 'card' or value.get('name') != name
            or value.get('id') != record['id'] or value.get('oracle_id') != record['oracle_id']
            or len(value) != record['fields'] or digest != record['object_sha256']):
        raise ValueError('Fixture identity or complete object changed')
    return value


def entry(name, quantity=1):
    raw = raw_card(name)
    # A truthy display-only operand prevents placeholder image writes. No art IO.
    normalized = ScryfallSyncService._normalize_payload(raw, 'unused:browser-fixture-display')
    return {**raw, **normalized, 'card_name': name, 'quantity': quantity,
            'image_uri': None, 'colors': deepcopy(raw.get('colors', [])),
            'card_faces': deepcopy(raw.get('card_faces', []))}


def card(name, *, id, owner, controller, zone, summoning_sick=True):
    # The true Factory captures all printed facts; replace only the scene pose.
    sample = MatchFactory.from_decks([entry(name, 8)], [], seed=0)
    template = next(value for value in sample.cards.values() if value.zone == Zone.LIBRARY)
    return replace(template, id=id, owner=owner, controller=controller, zone=zone,
                   instance_order=0, summoning_sick=summoning_sick)


def company_decks():
    """Inverse-bind six prints before BOTH real seeded shuffles/native IDs."""
    rng = random.Random(34)
    decks = []
    births = {48: 'Grizzly Bears', 49: 'Llanowar Elves', 50: 'Island',
              51: 'Plains', 52: 'Swamp', 53: 'Mountain'}
    for seat in (1, 2):
        names = ['Forest'] * 60
        order = list(range(60))
        rng.shuffle(order)
        if seat == 2:
            for slot, name in births.items():
                names[order[slot - 1]] = name
        grouped = []
        for name in names:
            if grouped and grouped[-1]['card_name'] == name:
                grouped[-1]['quantity'] += 1
            else:
                grouped.append(entry(name))
        decks.append(grouped)
    return decks


def scene_decks(seed, basic, slots):
    """Bind selected native copy indices before the original two shuffles."""
    rng = random.Random(seed)
    decks = []
    for seat in (1, 2):
        names = [basic] * 60
        order = list(range(60))
        rng.shuffle(order)
        for slot, name in slots.get(seat, {}).items():
            if type(slot) is not int or not 1 <= slot <= 60:
                raise ValueError('Invalid native fixture copy index')
            names[order[slot - 1]] = name
        grouped = []
        for name in names:
            if grouped and grouped[-1]['card_name'] == name:
                grouped[-1]['quantity'] += 1
            else:
                grouped.append(entry(name))
        decks.append(grouped)
    return decks
