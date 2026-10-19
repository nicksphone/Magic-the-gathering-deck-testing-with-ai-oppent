"""Exact pinned public RAW admissions for this bounded stack-copy fixture batch."""
import hashlib
import json
from pathlib import Path
from copy import deepcopy

from card_data.sync import ScryfallSyncService
from game_state.state import CardInstance, MatchFactory, Step, _infer_keywords, _infer_power, _infer_toughness
from rules_engine.card_faces import apply_transform_face
from rules_engine.card_types import printed_card_types

FIXTURES = Path(__file__).parent / 'fixtures'
SOURCES = json.loads((FIXTURES / 'stack_copy_printed_b720/SOURCES.json').read_bytes())
PRINTED_FIELDS = ('name', 'oracle_text', 'mana_cost', 'type_line', 'types', 'power',
    'toughness', 'printed_power', 'printed_toughness', 'loyalty', 'colors', 'keywords',
    'layout', 'card_faces', 'selected_face_index', 'printed_characteristics', 'image_uri',
    'characteristic_record')


def raw_card(name):
    source = SOURCES[name]
    data = (FIXTURES / source['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == source['sha256']
    raw = json.loads(data.splitlines()[source['line'] - 1]) if source['line'] else json.loads(data)
    for key in source['steps']:
        raw = raw[key]
    assert raw['object'] == 'card' and raw['name'] == name
    assert hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest() == source['raw_row_sha256']
    return raw


def canonical_stack_card(name, **physical):
    """Use the same existing projection as the qualified AI fixture materializer."""
    assert not set(physical).intersection(PRINTED_FIELDS)
    cached = ScryfallSyncService._normalize_payload(raw_card(name), None)
    types = printed_card_types(cached['type_line'])
    card = CardInstance(name=cached['name'], types=types, oracle_text=cached['oracle_text'],
        mana_cost=cached['mana_cost'], type_line=cached['type_line'],
        power=_infer_power(cached['name'], cached['power'], types),
        toughness=_infer_toughness(cached['name'], cached['toughness'], types),
        printed_power=cached['power'], printed_toughness=cached['toughness'],
        loyalty=int(cached['loyalty']) if cached['loyalty'] is not None else None,
        colors=cached['colors'].split(',') if cached['colors'] else [],
        keywords=_infer_keywords(cached['oracle_text']), layout=cached['layout'],
        card_faces=json.loads(cached['card_faces_json']), image_uri=cached['image_uri'], **physical)
    if card.card_faces and card.layout in {'transform', 'modal_dfc'}:
        apply_transform_face(card, 0)
    return card


def canonical_deck_entry(name, quantity):
    raw = raw_card(name)
    cached = ScryfallSyncService._normalize_payload(raw, None)
    return {**raw, 'card_name': name, 'quantity': quantity, 'image_uri': cached['image_uri']}


def set_stack_printed(card, name):
    printed = canonical_stack_card(name, id=card.id, owner=card.owner,
                             controller=card.controller, zone=card.zone)
    for field in PRINTED_FIELDS:
        setattr(card, field, deepcopy(getattr(printed, field)))
