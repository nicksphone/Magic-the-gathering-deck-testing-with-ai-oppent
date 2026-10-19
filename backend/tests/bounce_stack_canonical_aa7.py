"""Two complete official parents, with runtime poses applied after real birth."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from card_data.sync import ScryfallSyncService
from game_state.state import MatchFactory, Zone
from rules_engine.card_faces import select_cast_face


FIXTURES = Path(__file__).parent / 'fixtures'
SOURCES_SHA = '15a23fafc9bcf69aec0a5a3aea9336947fdf8e925510fb0e8cf1dddff1b088a3'


def raw_card(name):
    proof_bytes = (FIXTURES / 'bounce_stack_aa7/SOURCES.json').read_bytes()
    assert hashlib.sha256(proof_bytes).hexdigest() == SOURCES_SHA
    proof = json.loads(proof_bytes)
    record = proof['cards'][name]
    data = (FIXTURES / proof['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == proof['sha256']
    provenance = (FIXTURES / proof['provenance']).read_bytes()
    assert hashlib.sha256(provenance).hexdigest() == proof['provenance_sha256']
    line = data.splitlines()[record['line'] - 1]
    assert hashlib.sha256(line).hexdigest() == record['row_sha256']
    raw = json.loads(line)
    assert raw['object'] == 'card' and raw['name'] == name
    assert raw['id'] == record['id'] and raw['oracle_id'] == record['oracle_id']
    return raw


def canonical_card(name, *, id, owner, controller, zone, face_index=None):
    raw = raw_card(name)
    normalized = ScryfallSyncService._normalize_payload(
        raw, ScryfallSyncService._extract_remote_image_uri(raw))
    entry = {**raw, **normalized, 'card_name': name, 'quantity': 8,
             'colors': raw['colors'], 'card_faces': json.loads(normalized['card_faces_json'])}
    sample = MatchFactory.from_decks([entry], [], seed=0)
    template = next(card for card in sample.cards.values() if card.zone == Zone.LIBRARY)
    card = replace(template, id=id, owner=owner, controller=controller, zone=zone,
                   instance_order=0)
    return select_cast_face(card, face_index) if face_index is not None else card
