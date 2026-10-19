"""Independent retained-parent birth checks; corruption rows are protocol only."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from effects.registry import resolve_effect
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, Zone
from rules_engine.card_faces import select_cast_face
from tests import test_transformed_entry as original


RAW_FILE = Path(__file__).parent / 'fixtures/transformed_entry.json'
RAW_SHA = '181985b1b21e065f153502df37dbea3654bf163b0b4030af30d4aac8779e134c'
ROW_SHA = '5f6df9081c6f898d098666cde2cca05af7a39f896d3a2c7290e4d77a09f291ab'
OFFICIAL_SHA = '019ca19ad55b75d0aaff7ac39245d4819e897a364e3e53674008d765f81920a6'


def official_parent():
    data = RAW_FILE.read_bytes()
    assert hashlib.sha256(data).hexdigest() == RAW_SHA
    raw = json.loads(data)[0]
    encoded = lambda value: json.dumps(value, sort_keys=True, separators=(',', ':'),
                                       ensure_ascii=False).encode()
    assert hashlib.sha256(encoded(raw)).hexdigest() == ROW_SHA
    official = {key: value for key, value in raw.items() if key != 'fixture_provenance'}
    assert hashlib.sha256(encoded(official)).hexdigest() == OFFICIAL_SHA
    assert raw['id'] == '02d6d693-f1f3-4317-bcc0-c21fa8490d38'
    assert raw['oracle_id'] == '594f6881-c059-46f8-aa4e-7151d502de73'
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


def face_values(raw, index):
    face = raw['card_faces'][index]
    head = face['type_line'].partition(' \u2014 ')[0].split()
    return {
        'name': face['name'], 'mana_cost': face['mana_cost'],
        'type_line': face['type_line'],
        'types': [word for word in head if word in {'Creature', 'Planeswalker'}],
        'power': int(face['power']) if face.get('power') is not None else None,
        'toughness': int(face['toughness']) if face.get('toughness') is not None else None,
        'printed_power': face.get('power'), 'printed_toughness': face.get('toughness'),
        'loyalty': int(face['loyalty']) if face.get('loyalty') is not None else None,
        'oracle_text': face['oracle_text'], 'keywords': [], 'colors': face['colors'],
    }


def physical_values(raw):
    return {**face_values(raw, 0), 'name': raw['name'],
            'card_faces': deepcopy(raw['card_faces']), 'layout': raw['layout'],
            'selected_face_index': None,
            'image_uri': raw['card_faces'][0]['image_uris']['normal']}


def assert_physical(card, raw):
    record = card.characteristic_record
    assert type(record) is dict and set(record) == {'version', 'physical', 'values'}
    exact(record['version'], 1, 'record.version')
    exact(record['physical'], physical_values(raw), 'physical')


def assert_selected(card, raw, index):
    expected = face_values(raw, index)
    exact({key: getattr(card, key) for key in expected}, expected, 'selected')
    exact(card.characteristic_record['values'], expected, 'copiable')
    exact(card.card_faces, raw['card_faces'], 'ordered_faces')
    assert card.layout == raw['layout'] and card.selected_face_index == index


def test_full_parent_and_provenance_are_not_replaced_by_a_face_record():
    raw = official_parent()
    assert raw['object'] == 'card' and raw['layout'] == 'transform'
    assert raw['name'] == "Jace, Vryn's Prodigy // Jace, Telepath Unbound"
    assert [face['name'] for face in raw['card_faces']] == [
        "Jace, Vryn's Prodigy", 'Jace, Telepath Unbound']
    assert raw['keywords'] == ['Transform', 'Mill']
    assert raw['card_faces'][1]['loyalty'] == '5'
    assert {'legalities', 'all_parts', 'prices', 'prints_search_uri', 'rulings_uri'} <= raw.keys()
    assert raw['fixture_provenance'] == {
        'source': raw['scryfall_uri'], 'endpoint': 'https://api.scryfall.com/cards/named',
        'retrieved_at': '2026-10-01T14:48:54.300Z'}
    assert 'oracle_text' not in raw and 'mana_cost' not in raw


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_caller_forwards_full_front_before_native_capture_and_selection(seat, monkeypatch):
    raw, calls = official_parent(), []
    state = original.clean(seat)
    before_rows = deepcopy(original.ROWS)
    rng, stock, decks = state.rng.getstate(), deepcopy(state.sideboard_facts), deepcopy(state.starting_decks)
    pools = {pid: deepcopy(player.mana_pool) for pid, player in state.players.items()}
    expected = physical_values(raw)
    real_constructor, real_select = original.CardInstance, original.select_cast_face

    def construct(*args, **kwargs):
        assert len(args) == 5 and type(args[0]) is str
        assert args[1:] == (raw['name'], seat, seat, Zone.BATTLEFIELD)
        admission = {key: value for key, value in expected.items()
                     if key not in {'name', 'selected_face_index'}}
        exact(kwargs, admission, 'constructor')
        card = real_constructor(*args, **kwargs)
        assert_physical(card, raw)
        assert card.selected_face_index is None and not card.printed_characteristics
        calls.append(('constructor', card.id))
        return card

    def select(card, index):
        assert index == 0 and calls == [('constructor', card.id)]
        assert_physical(card, raw)
        selected = real_select(card, index)
        assert_selected(selected, raw, index)
        calls.append(('selected', selected.id))
        return selected

    monkeypatch.setattr(original, 'CardInstance', construct)
    monkeypatch.setattr(original, 'select_cast_face', select)
    card = original.jace(state, seat)
    assert calls == [('constructor', card.id), ('selected', card.id)]
    assert state.cards[card.id] is card and state.players[seat].battlefield.count(card.id) == 1
    assert card.owner == card.controller == seat and card.zone == Zone.BATTLEFIELD
    assert_physical(card, raw)
    assert_selected(card, raw, 0)
    assert original.ROWS == before_rows
    assert state.rng.getstate() == rng and state.sideboard_facts == stock and state.starting_decks == decks
    assert {pid: player.mana_pool for pid, player in state.players.items()} == pools


@pytest.mark.parametrize('seat', [1, 2])
def test_native_return_selected_face_and_whole_snapshot_keep_the_birth_record(seat):
    raw, state = official_parent(), original.clean(seat)
    card = original.jace(state, seat)
    physical = deepcopy(card.characteristic_record['physical'])
    stock, decks = deepcopy(state.sideboard_facts), deepcopy(state.starting_decks)
    assert card.id not in stock['inventory']
    assert stock['coverage_ok'] is True
    for index in (0, 1):
        if index:
            resolve_effect(state, seat, 'exile_return_transformed', {'target_card_id': card.id})
            stock['coverage_ok'] = False
        assert stock['coverage_ok'] is (index == 0)
        assert state.sideboard_facts == stock
        assert_physical(card, raw)
        assert_selected(card, raw, index)
        assert card.characteristic_record['physical'] == physical
        assert card.owner == card.controller == seat and card.zone == Zone.BATTLEFIELD
        snapshot = deepcopy(serialize_match_snapshot(state))
        restored = deserialize_match_snapshot(json.loads(json.dumps(snapshot)))
        assert serialize_match_snapshot(restored) == snapshot
        assert_physical(restored.cards[card.id], raw)
        assert_selected(restored.cards[card.id], raw, index)
        assert restored.sideboard_facts == stock and restored.starting_decks == decks
        state, card = restored, restored.cards[card.id]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('damage', ['front_oracle', 'ordered_faces'])
def test_protocol_corruption_at_birth_cannot_hide_behind_a_selected_face(seat, damage):
    raw = official_parent()
    supplied = physical_values(raw)
    supplied.pop('name')
    supplied.pop('selected_face_index')
    if damage == 'front_oracle':
        supplied['oracle_text'] = ''
    else:
        supplied['card_faces'].reverse()
    card = CardInstance('protocol-corruption', raw['name'], seat, seat, Zone.BATTLEFIELD, **supplied)
    selected = select_cast_face(card, 0)
    if damage == 'front_oracle':
        assert selected.oracle_text == raw['card_faces'][0]['oracle_text']
    field = 'oracle_text' if damage == 'front_oracle' else 'card_faces'
    with pytest.raises(AssertionError, match='physical\\.' + field):
        assert_physical(selected, raw)
    assert official_parent() == raw


@pytest.mark.parametrize('seat', [1, 2])
def test_returned_face_mutation_does_not_alias_raw_or_retained_physical_faces(seat, monkeypatch):
    raw, state = official_parent(), original.clean(seat)
    rows = deepcopy(original.ROWS)
    card = original.jace(state, seat)
    physical = deepcopy(card.characteristic_record['physical'])
    monkeypatch.setitem(card.card_faces[0], 'oracle_text', 'Protocol mutation; not canonical card data.')
    assert original.ROWS == rows and official_parent() == raw
    assert card.characteristic_record['physical'] == physical
