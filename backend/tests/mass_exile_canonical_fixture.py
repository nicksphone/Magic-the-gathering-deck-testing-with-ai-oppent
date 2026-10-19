"""Complete Final Judgment before birth; explicit hand pose, never stock repair."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from card_data.sync import ScryfallSyncService
from game_state.state import Zone


FIXTURE = Path(__file__).parent / 'fixtures/mass_exile_audit'
RAW_SHA = '0bc8a7a902fcfe58169a1e26f71785c730dccac3c616717aa65b1b1621789875'
PROVENANCE_SHA = '75c2c3bc4731ea49876ffde2a47171043da770c5e670bd93cce6e583d34b0b65'


def final_judgment_entry():
    encoded = (FIXTURE / 'final-judgment.json').read_bytes()
    provenance = (FIXTURE / 'provenance.json').read_bytes()
    if (hashlib.sha256(encoded).hexdigest() != RAW_SHA
            or hashlib.sha256(provenance).hexdigest() != PROVENANCE_SHA):
        raise ValueError('Canonical mass-exile source changed')
    raw = json.loads(encoded)
    proof = json.loads(provenance)
    receipt = proof['raw_rows']['final-judgment.json']
    if (raw.get('object') != 'card' or raw.get('name') != 'Final Judgment'
            or receipt['sha256'] != RAW_SHA or receipt['bytes'] != len(encoded)
            or receipt['name'] != raw['name'] or receipt['id'] != raw['id']
            or receipt['oracle_id'] != raw['oracle_id']
            or receipt['complete_oracle'] != raw['oracle_text']
            or receipt['oracle_modified'] is not False
            or receipt['raw_response_modified'] is not False
            or proof['before_offline_tests'] is not True):
        raise ValueError('Canonical mass-exile provenance mismatch')
    normalized = ScryfallSyncService._normalize_payload(raw, 'unused:mass-exile-display')
    return {**raw, **normalized, 'card_name': raw['name'], 'quantity': 1,
            'image_uri': None, 'colors': deepcopy(raw['colors']),
            'card_faces': deepcopy(raw.get('card_faces', []))}


def final_judgment_in_hand(state):
    matches = [card for card in state.cards.values() if card.name == 'Final Judgment']
    if len(matches) != 1:
        raise ValueError('Fixture requires one genuinely born Final Judgment')
    card = matches[0]
    binding = state.sideboard_facts.get('inventory', {}).get(card.id)
    if (card.owner != 1 or card.controller != 1
            or binding != {'owner': 1, 'stock_key': 'Final Judgment'}
            or card.zone not in (Zone.HAND, Zone.LIBRARY)):
        raise ValueError('Fixture spell is not original owned stock')
    pile = getattr(state.players[1], card.zone.value)
    if pile.count(card.id) != 1:
        raise ValueError('Fixture spell zone and inventory disagree')
    if card.zone == Zone.LIBRARY:
        pile.remove(card.id)
        card.move_to_zone(Zone.HAND)
        state.players[1].hand.append(card.id)
    return card
