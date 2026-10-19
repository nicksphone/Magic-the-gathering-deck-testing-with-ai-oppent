"""Pinned RAW admission for three fixtures, separate from legacy scene tables."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from card_data.sync import ScryfallSyncService
from game_state.state import Zone, _infer_keywords
from tests.browser_positive83_canonical import raw_card as browser_raw
from tests.test_ai_recurring_engines import CARDS as DEFAULT_CARDS, add as original_add


ROOT = Path(__file__).parent / 'fixtures/remaining_named3'
PROVENANCE_SHA = 'c7a046b3512f8dc3024660f77c075591d8edb9f11023e99d207bf660c56bb826'
LOCAL_ROWS = {'Graveyard Trespasser': 0, 'Behold the Multiverse': 1}
LEGACY = {
    'Wandering Archaic // Explore the Vastlands': (
        'modal_spell_faces.json', 'ffb6877741439134938257c07262d58dcfd56050eb221211e20d8c6e7de7b332'),
    'Graveyard Trespasser': (
        'ward.json', '5ac010f65ac406637d20083511b34186bae81acff2b946e612dff03213775599'),
    'Behold the Multiverse': (
        'foretell.json', 'dca40879cb924e898a487390f4a541c945930dcdeaa87c44ef02d7ce348d00e2'),
}
_MODAL_BINDING = None


def _same_json(actual, expected):
    if type(actual) is not type(expected):
        return False
    if type(expected) is dict:
        return (all(type(key) is str for key in actual) and actual.keys() == expected.keys()
                and all(_same_json(actual[key], expected[key]) for key in expected))
    if type(expected) is list:
        return len(actual) == len(expected) and all(_same_json(a, b) for a, b in zip(actual, expected))
    return actual == expected


def _bind_row(table, target):
    filename, digest = LEGACY[target]
    encoded = (ROOT.parent / filename).read_bytes()
    if hashlib.sha256(encoded).hexdigest() != digest:
        raise ValueError('Reviewed legacy fixture changed')
    data = json.loads(encoded)
    expected = data[target] if type(data) is dict else next(row for row in data if row['name'] == target)
    return table, target, table[target], deepcopy(expected)


def _matches(binding, table, name):
    if binding is None:
        return False
    original_table, target, row, snapshot = binding
    return (table is original_table and type(name) is str and name == target
            and all(type(key) is str for key in table) and table.get(target) is row
            and _same_json(row, snapshot))


def bind_modal(table, target):
    global _MODAL_BINDING
    _MODAL_BINDING = _bind_row(table, target)


def modal_raw(table, name):
    return raw_card(name) if _matches(_MODAL_BINDING, table, name) else None


def raw_card(name):
    if name == 'Wandering Archaic // Explore the Vastlands':
        return browser_raw(name)
    index = LOCAL_ROWS[name]
    encoded = (ROOT / 'PROVENANCE.json').read_bytes()
    if hashlib.sha256(encoded).hexdigest() != PROVENANCE_SHA:
        raise ValueError('Remaining fixture provenance changed')
    provenance = json.loads(encoded)
    encoded = (ROOT / 'canonical.jsonl').read_bytes()
    if hashlib.sha256(encoded).hexdigest() != provenance['canonical_jsonl_sha256']:
        raise ValueError('Remaining complete RAW changed')
    rows = encoded.splitlines()
    if len(rows) != 2:
        raise ValueError('Remaining fixture row count changed')
    raw, expected = json.loads(rows[index]), provenance['cards'][index]
    digest = hashlib.sha256(json.dumps(
        raw, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    if (raw.get('object') != 'card' or raw.get('name') != expected['name']
            or raw.get('id') != expected['id'] or raw.get('oracle_id') != expected['oracle_id']
            or len(raw) != expected['fields'] or digest != expected['object_sha256']):
        raise ValueError('Remaining complete fixture identity changed')
    return raw


def bind_add(table, target):
    """Adapt only this fixture's target row; custom/default tables pass through."""
    binding = _bind_row(table, target)

    def add(state, name, player=1, zone=Zone.BATTLEFIELD, *, cards=DEFAULT_CARDS):
        if not _matches(binding, cards, name):
            return original_add(state, name, player, zone, cards=cards)
        raw = raw_card(name)
        rules = ScryfallSyncService._canonical_rule_projection(raw, physical_front=True)
        printed = {key: deepcopy(rules[key]) for key in (
            'type_line', 'mana_cost', 'oracle_text', 'power', 'toughness', 'loyalty', 'layout')}
        printed.update(card_faces=deepcopy(raw.get('card_faces', [])),
                       colors=rules['colors'].split(',') if rules['colors'] else [],
                       keywords=_infer_keywords(rules['oracle_text']),
                       image_uri=deepcopy(cards[name].get('image_uri')),
                       selected_face_index=cards[name].get('selected_face_index'))
        return original_add(state, name, player, zone, cards={name: printed})

    return add
