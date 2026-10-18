"""Pinned mana-fixture prints; runtime poses and original RNG stay separate."""
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
PROVENANCE_SHA = '74a347ae0ab1ff7a1876c9a31a2c7543d222fb6dc7af516827dfb9962e63537a'


def raw_card(name):
    data = (FIXTURES / 'mana_canonical_76/PROVENANCE.json').read_bytes()
    assert hashlib.sha256(data).hexdigest() == PROVENANCE_SHA
    proof = json.loads(data)
    source = proof['objects'][name]
    data = (FIXTURES / source['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == proof['source_files'][source['file']]
    raw = json.loads(data.splitlines()[source['line'] - 1] if source['line'] else data)
    assert raw['object'] == 'card' and raw['name'] == name
    assert raw['id'] == source['id'] and raw['oracle_id'] == source['oracle_id']
    assert hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False).encode()).hexdigest() == source['object_sha256']
    return raw


def entry(name, quantity=1):
    raw = raw_card(name)
    cached = ScryfallSyncService._normalize_payload(
        raw, ScryfallSyncService._extract_remote_image_uri(raw))
    return {**raw, **cached, 'card_name': name, 'quantity': quantity,
            'colors': raw['colors'], 'card_faces': json.loads(cached['card_faces_json'])}


def canonical_card(name, **pose):
    if PRINTED.intersection(pose):
        raise ValueError('Printed fields are not fixture-pose overrides')
    sample = MatchFactory.from_decks([entry(name, 8)], [], seed=0)
    template = next(card for card in sample.cards.values() if card.zone == Zone.LIBRARY)
    return replace(template, **{'instance_order': 0, 'summoning_sick': True, **pose})


def mana_game(deck_a, deck_b, seed=None, *, births=None):
    """Choose seat-one shuffled print slots BEFORE the real Factory capture."""
    rng = random.Random(seed)
    if seed is None:
        rng.setstate(random.getstate())
    decks = []
    for seat, deck in enumerate((deck_a, deck_b), 1):
        templates = {row['card_name']: entry(row['card_name']) for row in deck}
        rows = [templates[row['card_name']] for row in deck for _ in range(row['quantity'])]
        order = list(range(len(rows)))
        rng.shuffle(order)
        if seat == 1:
            for slot, name in (births or {}).items():
                assert type(slot) is int and 1 <= slot <= len(rows)
                rows[order[slot - 1]] = entry(name)
        # Run-length encoding retains the exact pre-shuffle order without
        # duplicating an entire official response for every basic land.
        grouped = []
        for row in rows:
            if grouped and grouped[-1]['card_name'] == row['card_name']:
                grouped[-1]['quantity'] += 1
            else:
                grouped.append({**row, 'quantity': 1})
        decks.append(grouped)
    return MatchFactory.from_decks(*decks, seed=seed)


def print_uncaptured(state, births):
    """The existing controlled-basic fixture has no original-stock capture."""
    assert state.sideboard_facts == {}
    templates = {name: canonical_card(name) for name in
                 {card.name for card in state.cards.values()} | set(births.values())}
    for cid, card in state.cards.items():
        template = templates[births.get(cid, card.name)]
        for field in PRINTED:
            setattr(card, field, deepcopy(getattr(template, field)))
    return state
