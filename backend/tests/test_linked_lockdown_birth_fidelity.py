"""Retained canonical birth at the original caller, not a stock reconstruction."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from game_state.serializers import (
    deserialize_match_snapshot, serialize_match, serialize_match_snapshot,
)
from game_state.state import CardInstance, MatchFactory, Zone
from rules_engine.copiable_values import values
from tests import test_linked_exile as original
from tests.rules_printed_facts_e4 import SOURCES


SEED = Path(__file__).parent / 'fixtures/knowledge_profiles/seed155-scryfall.jsonl'
SEED_SHA = '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732'
ROW_SHA = 'dafc7a16957b8da2ccfa8b83752bfe01691a0c4ef65fa92cf7a039abc0381fcf'


def official():
    data = SEED.read_bytes()
    assert hashlib.sha256(data).hexdigest() == SEED_SHA
    raw = json.loads(data.splitlines()[100])
    encoded = json.dumps(raw, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    assert hashlib.sha256(encoded).hexdigest() == ROW_SHA
    assert raw['object'] == 'card' and raw['name'] == 'Temporary Lockdown'
    assert raw['id'] == '82b3088f-7b49-45e9-b447-129a597ceb75'
    assert raw['oracle_id'] == 'b21c99b3-b975-4428-9c9a-326ded2fa8dc'
    return raw


def exact(actual, expected, path):
    assert type(actual) is type(expected), path
    if type(expected) is dict:
        assert actual.keys() == expected.keys(), path
        for key, value in expected.items():
            exact(actual[key], value, path + '.' + key)
    elif type(expected) is list:
        assert len(actual) == len(expected), path
        for index, value in enumerate(expected):
            exact(actual[index], value, path + '[' + str(index) + ']')
    else:
        assert actual == expected, path


def physical(raw):
    assert raw['type_line'] == 'Enchantment' and raw['layout'] == 'normal'
    assert not {'power', 'toughness', 'loyalty', 'card_faces'}.intersection(raw)
    return {
        'name': raw['name'], 'mana_cost': raw['mana_cost'],
        'type_line': raw['type_line'], 'types': ['Enchantment'],
        'power': None, 'toughness': None, 'printed_power': None,
        'printed_toughness': None, 'loyalty': None,
        'oracle_text': raw['oracle_text'], 'keywords': deepcopy(raw['keywords']),
        'colors': deepcopy(raw['colors']), 'card_faces': [],
        'layout': raw['layout'], 'selected_face_index': None,
        'image_uri': raw['image_uris']['normal'],
    }


def assert_birth(card, raw):
    expected = physical(raw)
    copiable = {key: value for key, value in expected.items()
                if key not in {'card_faces', 'layout', 'selected_face_index', 'image_uri'}}
    exact({key: getattr(card, key) for key in expected}, expected, 'live')
    exact(card.characteristic_record,
          {'version': 1, 'physical': expected, 'values': copiable}, 'record')


def test_complete_official_object_is_admitted_without_changing_the_print():
    raw = official()
    assert 'Temporary Lockdown' in SOURCES
    source = SOURCES['Temporary Lockdown']
    assert source['file'] == 'knowledge_profiles/seed155-scryfall.jsonl'
    assert source['line'] == 101 and source['steps'] == []
    assert source['sha256'] == SEED_SHA and source['raw_row_sha256'] == ROW_SHA
    assert raw['colors'] == ['W'] and raw['mana_cost'] == '{1}{W}{W}'


def test_actual_caller_supplies_complete_facts_before_constructor_capture(monkeypatch):
    raw, calls, births = official(), [], []
    real_constructor, real_factory = original.CardInstance, MatchFactory.from_decks

    def factory(*args, **kwargs):
        state = real_factory(*args, **kwargs)
        births.append((state, deepcopy(state.sideboard_facts), deepcopy(state.starting_decks),
                       state.rng.getstate(), {pid: deepcopy(p.mana_pool)
                                              for pid, p in state.players.items()}))
        return state

    def construct(*args, **kwargs):
        assert args == ('lockdown', raw['name'], 1, 1, Zone.BATTLEFIELD, ['Enchantment'])
        expected = physical(raw)
        supplied = {**dict(zip(('id', 'name', 'owner', 'controller', 'zone', 'types'), args)),
                    **kwargs}
        required = ('name', 'types', 'mana_cost', 'oracle_text', 'type_line', 'colors',
                    'keywords', 'layout', 'card_faces', 'image_uri')
        exact({key: supplied.get(key) for key in required},
              {key: expected[key] for key in required}, 'constructor')
        assert 'characteristic_record' not in kwargs and 'printed_characteristics' not in kwargs
        card = real_constructor(*args, **kwargs)
        assert_birth(card, raw)
        calls.append(card)
        return card

    monkeypatch.setattr(MatchFactory, 'from_decks', staticmethod(factory))
    monkeypatch.setattr(original, 'CardInstance', construct)
    state, source = original._state()
    assert calls == [source] and len(births) == 1
    born, stock, decks, rng, pools = births[0]
    assert born is state and state.cards['lockdown'] is source
    assert source.owner == source.controller == 1 and source.zone == Zone.BATTLEFIELD
    assert state.players[1].battlefield == ['lockdown']
    assert source.static_order == source.effect_timestamp > 0
    assert state.rng.getstate() == rng and state.starting_decks == decks
    assert state.sideboard_facts == stock and source.id not in stock['inventory']
    assert {pid: p.mana_pool for pid, p in state.players.items()} == pools
    assert not state.pregame_pending and state.kept_hands == {1, 2}


def test_native_copy_facts_snapshot_and_private_stock_keep_the_original_birth():
    raw, (state, card) = official(), original._state()
    assert_birth(card, raw)
    expected = physical(raw)
    for key in ('card_faces', 'layout', 'selected_face_index', 'image_uri'):
        expected.pop(key)
    exact(values(card), expected, 'native_copy_values')
    before = deepcopy(serialize_match_snapshot(state))
    restored = deserialize_match_snapshot(json.loads(json.dumps(before)))
    assert serialize_match_snapshot(restored) == before
    assert serialize_match_snapshot(state) == before
    assert_birth(restored.cards[card.id], raw)
    assert restored.sideboard_facts == state.sideboard_facts
    assert restored.starting_decks == state.starting_decks
    public = serialize_match(restored)
    assert 'sideboard_facts' not in public and 'starting_decks' not in public


@pytest.mark.parametrize('damage', ['type_line', 'colors', 'layout', 'oracle_text'])
def test_protocol_incomplete_birth_is_rejected_independently(damage):
    raw = official()
    supplied = physical(raw)
    supplied.pop('name')
    supplied.pop('selected_face_index')
    supplied[damage] = [] if damage == 'colors' else ''
    card = CardInstance('protocol-only', raw['name'], 1, 1, Zone.BATTLEFIELD, **supplied)
    with pytest.raises(AssertionError, match='live\\.' + damage):
        assert_birth(card, raw)
    assert official() == raw


def test_mutable_raw_inputs_and_retained_records_are_detached(monkeypatch):
    raw, calls = official(), []
    before = deepcopy(raw)
    real = original.CardInstance

    def construct(*args, **kwargs):
        card = real(*args, **kwargs)
        calls.append((card, kwargs))
        return card

    monkeypatch.setattr(original, 'CardInstance', construct)
    monkeypatch.setattr(original, 'raw_card', lambda name: raw, raising=False)
    state, card = original._state()
    assert_birth(card, raw)
    supplied = calls[0][1]
    retained = deepcopy(card.characteristic_record)
    assert calls[0][0] is card and state.cards[card.id] is card
    supplied['colors'].append('protocol-only mutation')
    supplied['keywords'].append('protocol-only mutation')
    supplied['card_faces'].append({'name': 'Protocol, not printed data'})
    assert card.characteristic_record == retained
    assert official() == raw == before


def test_protocol_exact_oracle_rejects_boolean_as_record_version():
    with pytest.raises(AssertionError, match='record.version'):
        exact(True, 1, 'record.version')
