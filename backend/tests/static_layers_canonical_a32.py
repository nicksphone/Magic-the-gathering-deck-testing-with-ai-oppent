"""Native mixed births for named layer fixtures; synthetic rows stay unwaived."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random

from ai.sideboard_facts import copy_facts
from card_data.sync import ScryfallSyncService
from game_state.state import MatchFactory, Zone, _infer_keywords

FIXTURES = Path(__file__).parent / 'fixtures'
SOURCE_SHA = 'e576308cfa2da6a4d1df29c00555906c9d75672ea8f0e556b4177e915be31889'
NAMES = frozenset({'Llanowar Elves', 'Hill Giant', 'Elvish Clancaller', 'Grim Haruspex', 'Tarmogoyf'})
SCENES = {
    'tribal': {60: 'Elvish Anthem', 59: 'Llanowar Elves', 58: 'Bear'},
    'base': {60: 'Humility Field', 59: 'Hill Giant'},
    'subtype': {60: 'Elf Ward', 59: 'Llanowar Elves', 58: 'Knight'},
    'lords': {60: 'Elvish Clancaller', 59: 'Llanowar Elves'},
    'cascade': {60: 'Elvish Clancaller', 59: 'Llanowar Elves', 58: 'Grim Haruspex'},
    'cda': {60: 'Tarmogoyf'},
}
# These are the unchanged noncard protocol vectors, not official Oracle data.
SYNTHETIC = {
    'Elvish Anthem': {'type_line': 'Enchantment', 'oracle_text': 'Elves you control get +1/+1.'},
    'Humility Field': {'type_line': 'Enchantment', 'oracle_text': 'Creatures you control become 1/1.'},
    'Elf Ward': {'type_line': 'Enchantment', 'oracle_text': 'Elves you control become 1/1.'},
    'Bear': {'type_line': 'Creature - Bear', 'power': '2', 'toughness': '2'},
    'Knight': {'type_line': 'Creature - Human Knight', 'power': '3', 'toughness': '3'},
}


def raw_card(name):
    data = (FIXTURES / 'static_layers_a32/SOURCES.json').read_bytes()
    if hashlib.sha256(data).hexdigest() != SOURCE_SHA:
        raise ValueError('Static fixture source binding changed')
    row = json.loads(data)[name]
    body = (FIXTURES / row['file']).read_bytes()
    if hashlib.sha256(body).hexdigest() != row['file_sha256']:
        raise ValueError('Static fixture RAW source changed')
    body = body.splitlines()[row['line'] - 1] if row['line'] else body
    raw = json.loads(body)
    if (hashlib.sha256(body).hexdigest() != row['raw_sha256']
            or raw.get('object') != 'card' or raw.get('name') != name
            or raw.get('id') != row['id'] or raw.get('oracle_id') != row['oracle_id']):
        raise ValueError('Static fixture complete identity changed')
    return raw


def entry(name):
    if name in SYNTHETIC:
        return {'card_name': name, 'quantity': 1, **deepcopy(SYNTHETIC[name])}
    raw = raw_card(name)
    row = ScryfallSyncService._normalize_payload(raw, ScryfallSyncService._extract_remote_image_uri(raw))
    return {**raw, **row, 'card_name': name, 'quantity': 1,
            'colors': raw['colors'], 'card_faces': json.loads(row['card_faces_json'])}


def canonical_state(deck_a, deck_b, *, scene, seed=None):
    if (scene not in SCENES or any(deck != [{'quantity': 60, 'card_name': 'Forest'}]
                                  for deck in (deck_a, deck_b))
            or seed is not None and type(seed) is not int):
        raise ValueError('Unknown static fixture birth contract')
    order = random.Random(seed) if seed is not None else random.Random(0)
    if seed is None:
        order.setstate(random.getstate())
    forest = entry('Forest')
    decks = []
    for owner in (1, 2):
        permutation = list(range(60))
        order.shuffle(permutation)
        rows = [deepcopy(forest) for _ in range(60)]
        if owner == 1:
            for position, name in SCENES[scene].items():
                rows[permutation[position - 1]] = entry(name)
        decks.append(rows)
    # Only the real Factory shuffles the game RNG and captures the actual stock.
    return MatchFactory.from_decks(*decks, seed=seed)


def place_named(state, player_id, name):
    if type(player_id) is not int or player_id not in (1, 2) or name not in NAMES:
        raise ValueError('Invalid named fixture placement')
    player = state.players[player_id]
    if not player.hand:
        raise ValueError('Named fixture opening slot is absent')
    cid = player.hand[0]
    card = state.cards[cid]
    raw = raw_card(name)
    numeric = lambda value: int(value) if value is not None and value.isdecimal() else None
    expected = {key: raw.get(key, '') for key in ('name', 'mana_cost', 'oracle_text', 'type_line', 'layout')}
    expected.update(power=numeric(raw.get('power')), toughness=numeric(raw.get('toughness')),
                    printed_power=raw.get('power'), printed_toughness=raw.get('toughness'),
                    types=['Creature'], keywords=_infer_keywords(raw['oracle_text']),
                    colors=raw['colors'], card_faces=raw.get('card_faces', []),
                    image_uri=raw['image_uris']['normal'])
    if (card.id != cid or card.owner != player_id or card.controller != player_id
            or card.zone != Zone.HAND
            or any(getattr(card, key) != value for key, value in expected.items())):
        raise ValueError('Named fixture was not born with complete canonical facts')
    record = card.characteristic_record
    if (type(record) is not dict or record.get('version') != 1
            or any(record.get('physical', {}).get(key) != value for key, value in expected.items())
            or any(record.get('values', {}).get(key) != value for key, value in expected.items()
                   if key not in ('layout', 'card_faces', 'image_uri'))):
        raise ValueError('Named fixture retained record is not its canonical birth')
    copy_facts(state.sideboard_facts, state)
    player.hand.remove(cid)
    player.battlefield.append(cid)
    card.zone = Zone.BATTLEFIELD
    card.summoning_sick = False
    return cid
