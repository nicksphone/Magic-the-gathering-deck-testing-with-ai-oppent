"""Supplied-row admission before native birth, not a canonical name lookup."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone
from rules_engine.copiable_values import values
from tests import test_ai_recurring_engines as recurring
from tests import test_counter_prohibitions as counters
from tests.browser_positive83_canonical import entry


TABLE = Path(__file__).parent / 'fixtures/counter_prohibitions.json'
TABLE_SHA = '94fe0b7a42c358835cc4abf1f1e231c5096798a32de7de61a34c5a21d4cdc448'
NAMES = (
    'Solemnity', 'Melira, Sylvok Outcast', 'Tatterkite', 'Soul-Scar Mage',
    'Glistener Elf', 'Blightbelly Rat', 'Cankerbloom', 'Walking Ballista',
    'The First Iroan Games', "Elspeth, Sun's Champion",
)


def _raw(name):
    encoded = TABLE.read_bytes()
    assert hashlib.sha256(encoded).hexdigest() == TABLE_SHA
    rows = [row for row in json.loads(encoded) if row['name'] == name]
    assert len(rows) == 1 and rows[0]['object'] == 'card' and len(rows[0]) > 30
    return rows[0]


def _facts(raw):
    # Independent RAW projection; do not obtain goldens from add/Factory output.
    front = raw['type_line'].split('//', 1)[0].split('\u2014', 1)[0]
    kinds = {'Artifact', 'Battle', 'Creature', 'Enchantment', 'Instant',
             'Kindred', 'Land', 'Planeswalker', 'Sorcery'}
    return {
        'name': raw['name'], 'types': [word for word in front.split() if word in kinds],
        'mana_cost': raw['mana_cost'], 'type_line': raw['type_line'],
        'oracle_text': raw['oracle_text'],
        'power': int(raw['power']) if raw.get('power') is not None else None,
        'toughness': int(raw['toughness']) if raw.get('toughness') is not None else None,
        'printed_power': raw.get('printed_power', str(raw['power']) if raw.get('power') is not None else None),
        'printed_toughness': raw.get('printed_toughness', str(raw['toughness']) if raw.get('toughness') is not None else None),
        'loyalty': int(raw['loyalty']) if raw.get('loyalty') is not None else None,
        'keywords': deepcopy(raw.get('keywords') or []), 'colors': deepcopy(raw.get('colors') or []),
        'layout': raw.get('layout') or '', 'card_faces': deepcopy(raw.get('card_faces') or []),
        'selected_face_index': raw.get('selected_face_index'), 'image_uri': raw.get('image_uri'),
    }


def _constructor_spy(monkeypatch):
    real, calls = recurring.CardInstance, []

    def observed(*args, **kwargs):
        supplied = deepcopy(kwargs)
        card = real(*args, **kwargs)
        calls.append((supplied, card))
        return card

    monkeypatch.setattr(recurring, 'CardInstance', observed)
    return calls


def _assert_card(card, facts):
    assert {key: getattr(card, key) for key in facts} == facts
    assert card.characteristic_record == {
        'version': 1, 'physical': facts,
        'values': {key: value for key, value in facts.items()
                   if key not in {'layout', 'card_faces', 'selected_face_index', 'image_uri'}},
    }
    assert values(card) == card.characteristic_record['values']


@pytest.mark.parametrize('name', NAMES)
@pytest.mark.parametrize('seat', (1, 2))
def test_actual_counter_consumer_supplies_complete_printed_fields_before_native_init(monkeypatch, name, seat):
    raw, state = _raw(name), recurring.fixture()
    rows_before = deepcopy(counters.ROWS)
    rng, stock, decks = state.rng.getstate(), deepcopy(state.sideboard_facts), deepcopy(state.starting_decks)
    ids, history = set(state.cards), deepcopy(state.log)
    zone = Zone.HAND if seat == 1 else Zone.BATTLEFIELD
    calls = _constructor_spy(monkeypatch)

    card = counters.source(state, name, seat, zone)

    assert len(calls) == 1 and calls[0][1] is card
    supplied, _ = calls[0]
    facts = _facts(raw)
    assert {key: supplied.get(key, 'MISSING_CONSTRUCTOR_FIELD') for key in facts} == facts
    assert 'characteristic_record' not in supplied
    _assert_card(card, facts)
    assert (card.owner, card.controller, card.zone) == (seat, seat, zone)
    assert state.cards[card.id] is card and set(state.cards) == ids | {card.id}
    assert getattr(state.players[seat], zone.value).count(card.id) == 1
    assert state.rng.getstate() == rng and state.sideboard_facts == stock
    assert state.starting_decks == decks and state.log == history
    assert counters.ROWS == rows_before
    snapshot = deepcopy(serialize_match_snapshot(state))
    restored = deserialize_match_snapshot(json.loads(json.dumps(snapshot)))
    _assert_card(restored.cards[card.id], facts)
    assert serialize_match_snapshot(restored) == snapshot


@pytest.mark.parametrize('seat', (1, 2))
def test_supplied_mutable_fields_are_independent_of_row_sibling_and_retained_records(seat):
    # Whole official DFC entry is normalized before add; no printed retag or Factory repair.
    raw = entry('Bala Ged Recovery // Bala Ged Sanctuary')
    raw['selected_face_index'] = 0
    raw['image_uri'] = 'unused:owned-display-contract'
    before, state = deepcopy(raw), recurring.fixture()
    rows = {raw['name']: raw}
    first = recurring.add(state, raw['name'], seat, Zone.HAND, cards=rows)
    second = recurring.add(state, raw['name'], seat, Zone.HAND, cards=rows)
    facts = _facts(raw)
    _assert_card(first, facts)
    _assert_card(second, facts)
    snapshot = deepcopy(serialize_match_snapshot(state))
    first.card_faces[0]['oracle_text'] = 'deliberate independent-mutation protocol'
    first.card_faces[0]['image_uris']['normal'] = 'unused:mutated-display'
    first.keywords.append('deliberate protocol sentinel')
    first.colors.append('deliberate protocol sentinel')
    assert raw == before
    _assert_card(second, facts)
    assert first.characteristic_record['physical'] == facts
    assert first.characteristic_record['values'] == second.characteristic_record['values']
    restored = deserialize_match_snapshot(snapshot)
    _assert_card(restored.cards[first.id], facts)
    _assert_card(restored.cards[second.id], facts)
    raw['card_faces'][1]['oracle_text'] = 'deliberate input-mutation protocol'
    assert second.card_faces == facts['card_faces']
    assert first.characteristic_record['physical'] == facts


@pytest.mark.parametrize('mode', ('absent', 'null'))
@pytest.mark.parametrize('seat', (1, 2))
def test_absent_and_null_optional_fields_keep_native_empty_defaults(monkeypatch, mode, seat):
    # Explicit protocol inputs, not claims that these edited rows are official.
    raw = _raw('Walking Ballista')
    for field in ('printed_power', 'printed_toughness', 'loyalty', 'layout',
                  'card_faces', 'selected_face_index', 'image_uri'):
        if mode == 'absent':
            raw.pop(field, None)
        else:
            raw[field] = None
    calls = _constructor_spy(monkeypatch)
    card = recurring.add(recurring.fixture(), raw['name'], seat, Zone.HAND, cards={raw['name']: raw})
    facts = _facts(raw)
    assert {key: calls[0][0].get(key, 'MISSING_CONSTRUCTOR_FIELD') for key in facts} == facts
    _assert_card(card, facts)


@pytest.mark.parametrize('seat', (1, 2))
@pytest.mark.parametrize('loyalty', ('-3', '0'))
def test_explicit_printed_fields_and_signed_numeric_runtime_conversion_are_preserved(seat, loyalty):
    # Deliberate supplied-template protocol, distinct from official-card goldens.
    raw = _raw('Walking Ballista')
    raw.update(power='+7', toughness='-2', printed_power='*', printed_toughness='1+*',
               loyalty=loyalty, layout='normal', selected_face_index=0, image_uri='unused:explicit-image')
    before = deepcopy(raw)
    card = recurring.add(recurring.fixture(), raw['name'], seat, Zone.HAND, cards={raw['name']: raw})
    _assert_card(card, _facts(raw))
    assert (card.power, card.toughness, card.loyalty) == (7, -2, int(loyalty))
    assert raw == before


@pytest.mark.parametrize('field', ('power', 'toughness', 'loyalty'))
def test_invalid_existing_numeric_operand_still_raises_without_publishing_card(field):
    raw, state = _raw('Walking Ballista'), recurring.fixture()
    raw[field] = 'deliberately-not-a-number'
    before, ids = deepcopy(raw), set(state.cards)
    with pytest.raises(ValueError):
        recurring.add(state, raw['name'], cards={raw['name']: raw})
    assert raw == before and set(state.cards) == ids
