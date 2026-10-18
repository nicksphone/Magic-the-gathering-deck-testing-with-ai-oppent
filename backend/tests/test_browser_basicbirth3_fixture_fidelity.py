"""Observe actual basic deck inputs and original stock capture, never repair them."""
from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path
import random

import pytest

from ai import sideboard_facts
from game_state.serializers import (
    deserialize_match_snapshot, serialize_match, serialize_match_snapshot,
)
from game_state.state import MatchFactory, Zone


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = Path(__file__).parent / 'fixtures/browser_positive83/SOURCES.json'
MANIFEST_SHA = 'cb515e9c199a4dba208e3a9c22af8bec840dcc265aeffe9b453706d39d56f994'
CASES = [
    pytest.param('recurring', 'Swamp', 941, 1, id='recurring'),
    pytest.param('opening', 'Plains', 54, 1, id='opening-1'),
    pytest.param('opening', 'Plains', 54, 2, id='opening-2'),
    pytest.param('linked', 'Plains', 621, 1, id='linked'),
]


def _raw(name):
    encoded = MANIFEST.read_bytes()
    assert hashlib.sha256(encoded).hexdigest() == MANIFEST_SHA
    record = json.loads(encoded)['cards'][name]
    encoded = (ROOT / record['path']).read_bytes()
    assert hashlib.sha256(encoded).hexdigest() == record['file_sha256']
    location = list(record['location'])
    if location and location[0] == 'line':
        value = json.loads(encoded.splitlines()[location[1] - 1])
        location = location[2:]
    else:
        value = json.loads(encoded)
    for key in location:
        value = value[key]
    digest = hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                      ensure_ascii=False).encode()).hexdigest()
    assert digest == record['object_sha256']
    assert value['object'] == 'card' and value['name'] == name
    assert value['id'] == record['id'] and value['oracle_id'] == record['oracle_id']
    assert len(value) == record['fields']
    return value


def _observe(monkeypatch, kind, starter):
    module_name, function_name = {
        'recurring': ('test_ai_recurring_engines', 'fixture'),
        'opening': ('test_opening_hand', 'opening_game'),
        'linked': ('test_linked_exile', '_state'),
    }[kind]
    module = importlib.import_module('tests.' + module_name)
    original_factory = MatchFactory.from_decks
    original_capture = sideboard_facts.initialize
    calls, captures, births = [], [], []

    def capture(state, inventory):
        captures.append({
            'state_id': state.id,
            'inventory': deepcopy(inventory),
            'cards': {cid: deepcopy(card.__dict__) for cid, card in state.cards.items()},
            'decks': deepcopy(state.starting_decks),
            'hands': {pid: list(p.hand) for pid, p in state.players.items()},
            'libraries': {pid: list(p.library) for pid, p in state.players.items()},
        })
        result = original_capture(state, inventory)
        captures[-1]['facts'] = deepcopy(state.sideboard_facts)
        return result

    def factory(a, b, *args, **kwargs):
        calls.append((deepcopy(a), deepcopy(b), args, deepcopy(kwargs)))
        result = original_factory(a, b, *args, **kwargs)
        births.append({
            'state': result,
            'facts': deepcopy(result.sideboard_facts),
            'rng': deepcopy(result.rng.getstate()),
        })
        return result

    monkeypatch.setattr(sideboard_facts, 'initialize', capture)
    monkeypatch.setattr(MatchFactory, 'from_decks', staticmethod(factory))
    result = (getattr(module, function_name)(starter) if kind == 'opening'
              else getattr(module, function_name)())
    state = result[0] if kind == 'linked' else result
    assert len(calls) == len(captures) == len(births) == 1
    assert state is births[0]['state']
    if kind == 'linked':
        assert result[1] is state.cards['lockdown']
    return state, calls[0], captures[0], births[0]


def _ids(seat, indices):
    return [f'p{seat}-{index:03d}' for index in indices]


@pytest.mark.parametrize('kind,name,seed,starter', CASES)
def test_complete_raw_reaches_real_factory_and_cards_before_original_stock_capture(
        monkeypatch, kind, name, seed, starter):
    _, call, capture, _ = _observe(monkeypatch, kind, starter)
    raw = _raw(name)
    a, b, args, kwargs = call
    assert args == () and kwargs == {'seed': seed}
    assert len(a) == len(b) == 1
    for deck in (a, b):
        item = deck[0]
        assert item['card_name'] == name and item['quantity'] == 60
        assert {key: item.get(key) for key in raw} == raw
        assert item['image_uri'] is None
        assert item['card_faces'] == raw.get('card_faces', [])
        assert json.loads(item['legalities_json']) == raw['legalities']
    expected_types = set(raw['type_line'].split('\u2014')[0].split()) & {
        'Artifact', 'Battle', 'Creature', 'Enchantment', 'Instant', 'Kindred',
        'Land', 'Planeswalker', 'Sorcery',
    }
    assert expected_types == {'Land'}
    values = {
        'name': raw['name'], 'mana_cost': raw.get('mana_cost') or '',
        'type_line': raw['type_line'], 'types': ['Land'],
        'power': None, 'toughness': None, 'printed_power': None,
        'printed_toughness': None, 'loyalty': None,
        'oracle_text': raw.get('oracle_text') or '',
        'keywords': raw['keywords'], 'colors': raw['colors'],
    }
    physical = {**values, 'card_faces': raw.get('card_faces', []),
                'layout': raw['layout'], 'selected_face_index': None, 'image_uri': None}
    expected_inventory = {
        cid: {'owner': seat, 'stock_key': name}
        for seat in (1, 2) for cid in _ids(seat, range(1, 61))
    }
    assert capture['inventory'] == expected_inventory
    assert capture['decks'] == {1: a, 2: b}
    for seat in (1, 2):
        assert capture['hands'][seat] == []
        assert capture['libraries'][seat] == _ids(seat, range(1, 61))
        for index, cid in enumerate(capture['libraries'][seat], 1):
            card = capture['cards'][cid]
            assert card['id'] == cid and card['owner'] == card['controller'] == seat
            assert card['zone'] == Zone.LIBRARY and card['zone_change_sequence'] == 0
            assert card['instance_order'] == index
            assert {key: card[key] for key in physical} == physical
            assert card['characteristic_record'] == {
                'version': 1, 'physical': physical, 'values': values,
            }
    assert capture['facts'] == {
        'version': 1, 'game_id': capture['state_id'], 'complete': False,
        'capture_version': 3, 'coverage_ok': True, 'terminal_winner': None,
        'inventory': expected_inventory,
        'seats': {str(seat): {'hand_entries': {}, 'protected': [],
                             'observed_creatures': [], 'observed_creature_sources': {}}
                  for seat in (1, 2)},
    }


@pytest.mark.parametrize('kind,name,seed,starter', CASES)
def test_basic_birth_keeps_native_ids_rng_zones_and_original_runtime_pose(
        monkeypatch, kind, name, seed, starter):
    state, _, capture, birth = _observe(monkeypatch, kind, starter)
    expected_rng = random.Random(seed)
    expected_rng.shuffle(list(range(60)))
    expected_rng.shuffle(list(range(60)))
    assert birth['rng'] == state.rng.getstate() == expected_rng.getstate()
    assert state.log == ['Game start. Both players draw 7 and decide on London mulligans.']
    assert state.active_player == state.priority_player == starter
    assert state.pregame_pending is (kind == 'opening')
    assert state.kept_hands == (set() if kind == 'opening' else {1, 2})
    if kind == 'recurring':
        assert state.turn == 5 and state.step.value == 'precombat_main'
    else:
        assert state.turn == 1 and state.step.value == 'untap'
    for seat in (1, 2):
        player = state.players[seat]
        initial_hand = _ids(seat, range(60, 53, -1))
        assert player.hand == ([] if kind == 'recurring' else initial_hand)
        assert player.library == (_ids(seat, range(1, 54)) + initial_hand
                                  if kind == 'recurring' else _ids(seat, range(1, 54)))
        if kind == 'recurring':
            assert player.mana_pool == {'B': 10, 'G': 2, 'C': 10}
        for cid in _ids(seat, range(1, 61)):
            card = state.cards[cid]
            assert card.owner == card.controller == seat
            assert card.zone == (Zone.HAND if cid in player.hand else Zone.LIBRARY)
            assert card.zone_change_sequence == ((2 if kind == 'recurring' else 1)
                                                  if cid in initial_hand else 0)
    assert state.sideboard_facts == birth['facts']
    assert state.sideboard_facts['inventory'] == capture['inventory']


@pytest.mark.parametrize('kind,name,seed,starter', CASES)
def test_private_stock_snapshot_roundtrips_without_public_leak_or_shared_records(
        monkeypatch, kind, name, seed, starter):
    state, _, capture, birth = _observe(monkeypatch, kind, starter)
    before = deepcopy(serialize_match_snapshot(state))
    restored = deserialize_match_snapshot(deepcopy(before))
    assert serialize_match_snapshot(restored) == before
    assert serialize_match_snapshot(state) == before
    assert restored.sideboard_facts == state.sideboard_facts == birth['facts']
    assert restored.sideboard_facts['inventory'] == capture['inventory']
    for seat in (1, 2):
        assert restored.sideboard_facts['seats'][str(seat)]['hand_entries'] == {
            cid: 1 for cid in _ids(seat, range(60, 53, -1))
        }
    public = serialize_match(restored)
    assert 'sideboard_facts' not in public and 'starting_decks' not in public
    restored.cards['p1-001'].characteristic_record['values']['keywords'].append('protocol-only mutation')
    assert restored.cards['p1-002'].characteristic_record['values']['keywords'] == []
    assert restored.cards['p2-001'].characteristic_record['values']['keywords'] == []
    restored.starting_decks[1][0]['card_name'] = 'explicit invalid protocol mutation'
    assert restored.starting_decks[2][0]['card_name'] == name
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('name', ['Swamp', 'Plains'])
def test_full_basic_entries_are_fresh_not_retained_row_mutation(name):
    from tests.browser_positive83_canonical import entry
    raw_before = _raw(name)
    a, b = entry(name, 60), entry(name, 60)
    assert a == b
    a['legalities']['fixture_only'] = 'explicit invalid protocol mutation'
    assert b['legalities'] == raw_before['legalities']
    assert _raw(name) == raw_before
