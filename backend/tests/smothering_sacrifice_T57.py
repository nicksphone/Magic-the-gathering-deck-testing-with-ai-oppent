"""One full official parent; only physical fixture poses follow native birth."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from card_data.sync import ScryfallSyncService
from game_state.state import MatchFactory, Zone


DIRECTORY = Path(__file__).parent / 'fixtures/smothering_sacrifice_T57'
RAW_SHA = 'ff0cec752805b3545a3399925b3fc3189163a0940c2fed1d280e3b9909d80786'
PROVENANCE_SHA = 'c4f4d6a2426481c733c0b370dff3a84a7d3e6856a0634259874e45f9502e46be'


def raw_card():
    body = (DIRECTORY / 'response.json').read_bytes()
    proof = (DIRECTORY / 'PROVENANCE.json').read_bytes()
    if (len(body) != 5102 or hashlib.sha256(body).hexdigest() != RAW_SHA
            or hashlib.sha256(proof).hexdigest() != PROVENANCE_SHA):
        raise ValueError('Smothering full RAW/provenance binding changed')
    raw, origin = json.loads(body), json.loads(proof)
    if (raw.get('object') != 'card' or raw.get('name') != 'Smothering Abomination'
            or raw.get('id') != 'aac33238-e4bd-4c72-aecc-9905232c3ab4'
            or raw.get('oracle_id') != 'c3db28e5-6162-4642-a1c9-a7ace0737950'
            or origin.get('http_status') != 200 or origin.get('curl_exit') != 0
            or origin.get('body_sha256') != RAW_SHA or origin.get('body_bytes') != len(body)
            or origin.get('id') != raw['id'] or origin.get('oracle_id') != raw['oracle_id']):
        raise ValueError('Smothering canonical parent identity changed')
    return raw


def smothering_card(*, id, owner, controller, zone):
    raw = raw_card()
    normalized = ScryfallSyncService._normalize_payload(
        raw, ScryfallSyncService._extract_remote_image_uri(raw))
    entry = {**raw, **normalized, 'card_name': raw['name'], 'quantity': 8,
             'colors': raw['colors'], 'card_faces': json.loads(normalized['card_faces_json'])}
    sample = MatchFactory.from_decks([entry], [], seed=0)
    template = next(card for card in sample.cards.values() if card.zone == Zone.LIBRARY)
    return replace(template, id=id, owner=owner, controller=controller, zone=zone,
                   instance_order=0, summoning_sick=True)
