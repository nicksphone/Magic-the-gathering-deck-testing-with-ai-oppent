"""Test-local complete RAW admissions and finite physical fixture poses."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from card_data.sync import ScryfallSyncService
from game_state.state import MatchFactory, Zone
from tests.rules_printed_facts_e4 import raw_card as existing_raw

WEDDING = 'Wedding Announcement // Wedding Festivity'
SEED = Path(__file__).parent / 'fixtures/knowledge_profiles/seed155-scryfall.jsonl'
SEED_SHA256 = '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732'
ROWS = {'Island': (50, '932ef67074504645e2ddf2ceefcb9e65aa3b6938c6f6c42cb226dbdbe5b30d6b'),
        'Plains': (70, 'bb36c8b3d7c52e7274ab49ee95993248b8dc616ba4e1702b3d8e33ec107b1b0b'),
        WEDDING: (116, 'fed913802841e8b3e1792279cd3a93ba119c68a243952eeb1c473646fe6fcbad')}


def raw_card(name):
    if name == 'Grizzly Bears': return existing_raw(name)
    line, digest = ROWS[name]
    data = SEED.read_bytes()
    assert hashlib.sha256(data).hexdigest() == SEED_SHA256
    rows = data.splitlines()
    assert len(rows) == 155
    raw = json.loads(rows[line - 1])
    assert raw['object'] == 'card' and raw['name'] == name
    encoded = json.dumps(raw, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    assert hashlib.sha256(encoded).hexdigest() == digest
    return raw


def deck_entry(name, quantity):
    raw = raw_card(name)
    cached = ScryfallSyncService._normalize_payload(raw, None)
    entry = {**deepcopy(raw), 'card_name': raw['name'], 'quantity': quantity,
             'image_uri': cached['image_uri']}
    if name == WEDDING: entry['selected_face_index'] = 0
    return entry


def canonical_card(name, **physical):
    assert set(physical) <= {'id', 'owner', 'controller', 'zone', 'summoning_sick'}
    # Supply front0 before Factory's printed captures, never repair a record later.
    fixture = MatchFactory.from_decks([deck_entry(name, 8)], [], seed=0)
    template = next(card for card in fixture.cards.values() if card.zone == Zone.LIBRARY)
    pose = {'summoning_sick': True, 'instance_order': 0, **physical}
    return replace(deepcopy(template), **pose)
