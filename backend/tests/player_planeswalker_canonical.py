"""Four complete seed155 prints; native birth precedes any explicit scene pose."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from card_data.sync import ScryfallSyncService
from game_state.state import MatchFactory, Zone


NAMES = ('Lightning Bolt', 'Lava Spike', 'Skullcrack', 'Teferi, Hero of Dominaria')
SEED = Path(__file__).parent / 'fixtures/knowledge_profiles/seed155-scryfall.jsonl'
SEED_SHA = '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732'


def raw_card(name):
    if name not in NAMES:
        raise ValueError('Outside the four admitted fixture prints')
    data = SEED.read_bytes()
    if hashlib.sha256(data).hexdigest() != SEED_SHA:
        raise ValueError('Complete official fixture source changed')
    rows = [row for row in map(json.loads, data.splitlines()) if row.get('name') == name]
    if len(rows) != 1 or rows[0].get('object') != 'card':
        raise ValueError('Expected one complete canonical parent')
    return rows[0]


def spell_case(name):
    raw = raw_card(name)
    return name, raw['mana_cost'], raw['oracle_text']


def canonical_card(name, *, id, owner, controller, zone):
    raw = raw_card(name)
    cached = ScryfallSyncService._normalize_payload(raw, 'unused:target-fixture-display')
    entry = {**raw, **cached, 'card_name': name, 'quantity': 8, 'image_uri': None,
             'colors': deepcopy(raw['colors']), 'card_faces': deepcopy(raw.get('card_faces', []))}
    sample = MatchFactory.from_decks([entry], [], seed=0)
    template = next(card for card in sample.cards.values() if card.zone == Zone.LIBRARY)
    return replace(template, id=id, owner=owner, controller=controller, zone=zone,
                   instance_order=0, summoning_sick=True)


def canonical_spell(data, **pose):
    name, _, _ = data
    if data != spell_case(name):
        raise ValueError('Spell fixture operands must be the complete canonical print')
    return canonical_card(name, **pose)
