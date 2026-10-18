"""Canonical input layout for six established-board fixtures, not paid entry."""
import hashlib
import json
from pathlib import Path
import random

from card_data.sync import ScryfallSyncService
from game_state.state import MatchFactory, Zone, assign_static_order_on_battlefield_entry

FIXTURES = Path(__file__).parent / 'fixtures'
SOURCE_SHA = 'f629355f018f2e6a23c299ac1f8d2e51464eb756fe7c0c5bd5788f6c3d64362f'
SCENES = {
    'realmwalker': {'base': 'Plains', 'seed': 106,
        'extras': {1: 'Realmwalker'},
        'selected': {51: 'Spectral Procession', 50: 'Figure of Destiny'}},
    'souleater': {'base': 'Island', 'seed': 110,
        'extras': {1: 'Pestilent Souleater'}, 'selected': {}},
    'tamiyo': {'base': 'Island', 'seed': 924,
        'extras': {}, 'selected': {60: 'Tamiyo, Compleated Sage'}},
    'font': {'base': 'Forest', 'seed': 108,
        'extras': {1: 'Llanowar Elves', 2: 'Font of Agonies'},
        'selected': {62: 'Mutagenic Growth'}},
    'fountain': {'base': 'Island', 'seed': 96,
        'extras': {1: 'Hallowed Fountain', 2: 'Marble Diamond'},
        'selected': {62: 'Lavinia, Azorius Renegade'}},
    'lotus': {'base': 'Island', 'seed': 97,
        'extras': {1: 'Gilded Lotus'}, 'selected': {}},
}


def raw_card(name):
    body = (FIXTURES / 'mana_remaining_current191/SOURCES.json').read_bytes()
    if hashlib.sha256(body).hexdigest() != SOURCE_SHA:
        raise ValueError('Mana remaining source pin changed')
    pin = json.loads(body)['objects'][name]
    body = (FIXTURES / pin['file']).read_bytes()
    if hashlib.sha256(body).hexdigest() != pin['file_sha256']:
        raise ValueError('Full official RAW file changed')
    body = body.splitlines()[pin['line'] - 1] if pin['line'] else body
    raw = json.loads(body)
    if (hashlib.sha256(body).hexdigest() != pin['raw_sha256']
            or raw.get('object') != 'card' or raw.get('name') != name
            or raw.get('id') != pin['id'] or raw.get('oracle_id') != pin['oracle_id']
            or len(raw) != pin['fields']):
        raise ValueError('Full official RAW identity changed')
    return raw


def row(name):
    raw = raw_card(name)
    cached = ScryfallSyncService._normalize_payload(
        raw, ScryfallSyncService._extract_remote_image_uri(raw))
    return {**raw, **cached, 'card_name': name, 'quantity': 1,
            'colors': list(raw['colors']), 'card_faces': json.loads(cached['card_faces_json'])}


def decks(scene, *, seat=1):
    if scene not in SCENES or type(seat) is not int or seat not in (1, 2):
        raise ValueError('Unknown finite mana birth layout')
    spec = SCENES[scene]
    rng = random.Random(spec['seed'])
    result = []
    for owner in (1, 2):
        size = 60 + (len(spec['extras']) if owner == seat else 0)
        order = list(range(size))
        rng.shuffle(order)
        names = [spec['base']] * size
        if owner == seat:
            for position, name in {**spec['extras'], **spec['selected']}.items():
                names[order[position - 1]] = name
        result.append([row(name) for name in names])
    return result


def birth(scene, *, seat=1):
    """One real Factory call; no inventory, printed-record or RNG repair."""
    return MatchFactory.from_decks(*decks(scene, seat=seat), seed=SCENES[scene]['seed'])


def from_scene(deck_a, deck_b, *, scene, seed):
    spec = SCENES[scene]
    expected = [{'quantity': 60, 'card_name': spec['base']}]
    if deck_a != expected or deck_b != expected or type(seed) is not int or seed != spec['seed']:
        raise ValueError('Original fixture resource template or seed changed')
    return birth(scene)


def take(state, name, zone=Zone.BATTLEFIELD, *, seat=1, chosen_creature_type=None):
    matches = [card for card in state.cards.values() if card.owner == seat and card.name == name]
    if len(matches) != 1:
        raise ValueError('Fixture needs exactly one native-born participant')
    card = matches[0]
    if card.zone not in (Zone.LIBRARY, Zone.HAND):
        raise ValueError('Participant is not in its native starting zone')
    getattr(state.players[seat], card.zone.value).remove(card.id)
    card.move_to_zone(zone)
    getattr(state.players[seat], zone.value).append(card.id)
    if zone == Zone.BATTLEFIELD:
        assign_static_order_on_battlefield_entry(state, card.id)
    if chosen_creature_type is not None:
        card.chosen_creature_type = chosen_creature_type
    return card
