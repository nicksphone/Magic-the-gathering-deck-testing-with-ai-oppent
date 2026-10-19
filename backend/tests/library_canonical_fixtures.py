"""Full printed facts for Library6; structural poses are separate, not canon."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from card_data.sync import ScryfallSyncService
from game_state.state import MatchFactory, Zone


FIXTURES = Path(__file__).parent / 'fixtures'
PROVENANCE_SHA = '2c2750acb82ff6746cfbb4cb49c6118f276e9129fd2c819cbc2b5187e0b22f76'
PRINTED = frozenset((
    'name', 'types', 'mana_cost', 'power', 'toughness', 'printed_power',
    'printed_toughness', 'loyalty', 'keywords', 'oracle_text', 'type_line',
    'image_uri', 'card_faces', 'layout', 'selected_face_index', 'colors',
    'printed_characteristics', 'knowledge_snapshot', 'characteristic_record',
))
RANKING_NAMES = ('Tidings', 'Preordain', 'Explore', 'Deathbloom Gardener',
                 'Brindle Boar', 'Wayward Swordtooth', 'Divination')
RANKING_PROVENANCE_SHA = 'af841adc2418f6247a6dafc08c2e242b94c4d775ad8ecc94ce3981329a9e4a04'


def ranking_raw_card(name):
    directory = FIXTURES / 'library_ranking_vectors'
    data = (directory / 'PROVENANCE.json').read_bytes()
    assert hashlib.sha256(data).hexdigest() == RANKING_PROVENANCE_SHA
    proof = json.loads(data)
    assert set(proof['objects']) == set(RANKING_NAMES)
    record = proof['objects'][name]
    data = (directory / record['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == record['sha256']
    raw = json.loads(data)
    assert raw['object'] == 'card' and raw['name'] == name
    assert raw['id'] == record['id'] and raw['oracle_id'] == record['oracle_id']
    return raw


def raw_card(name):
    data = (FIXTURES / 'library_canonical_88/PROVENANCE.json').read_bytes()
    assert hashlib.sha256(data).hexdigest() == PROVENANCE_SHA
    record = json.loads(data)['objects'][name]
    data = (FIXTURES / record['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == record['file_sha256']
    raw = json.loads(data.splitlines()[record['source_line'] - 1]
                     if record['file'].endswith('.jsonl') else data)
    digest = hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(',', ':'),
                                      ensure_ascii=False).encode()).hexdigest()
    assert digest == record['object_sha256']
    assert raw['object'] == 'card' and raw['name'] == name
    assert raw['id'] == record['id'] and raw['oracle_id'] == record['oracle_id']
    return raw


def _template(name):
    raw = ranking_raw_card(name) if name in RANKING_NAMES else raw_card(name)
    cached = ScryfallSyncService._normalize_payload(
        raw, ScryfallSyncService._extract_remote_image_uri(raw))
    entry = {**raw, **cached, 'card_name': raw['name'], 'quantity': 8,
             'colors': raw['colors'], 'card_faces': json.loads(cached['card_faces_json'])}
    sample = MatchFactory.from_decks([entry], [], seed=0)
    return next(card for card in sample.cards.values() if card.zone == Zone.LIBRARY)


def canonical_card(name, **pose):
    if PRINTED.intersection(pose):
        raise ValueError('Printed fields are not fixture-pose overrides')
    # Retain the old direct CardInstance defaults, not template-library pose.
    return replace(_template(name), **{'instance_order': 0, 'summoning_sick': True, **pose})


def _apply_printed(card, template):
    for field in PRINTED:
        setattr(card, field, deepcopy(getattr(template, field)))
    return card


def reprint(state, cid, name):
    """Retain object identity and every runtime field before explicit old poses."""
    return _apply_printed(state.cards[cid], _template(name))


def canonicalize_basics(state):
    """Keep the old birth/RNG/stock/runtime pose, changing printed facts only."""
    names = {card.name for card in state.cards.values()}
    templates = {name: _template(name) for name in names.intersection(
        {'Plains', 'Island', 'Swamp', 'Mountain', 'Forest'})}
    for card in state.cards.values():
        if card.name in templates:
            _apply_printed(card, templates[card.name])
