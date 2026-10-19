"""Unexecuted PREP: independent RAW and unchanged real manual-mana callers."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random
from unittest.mock import patch

import pytest

from ai import sideboard_facts
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Zone
from tests import test_manual_mana_tap as original


DATA = Path(__file__).parent / 'fixtures/manual_mana_a227'
SOURCES_SHA = 'e450c68b67cb25498e80c245962502715477bb9c903a4a77d931682ae1b5bcb8'
NAMES = ('Forest', 'Island', 'Mountain', 'Llanowar Tribe', 'Sol Ring',
         'Gilded Lotus', 'Watery Grave')
NONLANDS = ('Llanowar Tribe', 'Sol Ring', 'Gilded Lotus')
SCENES = ('bulk', *NONLANDS, 'dual')
WANTED = {'bulk': ('Mountain',), 'dual': ('Watery Grave', 'Island'),
          **{name: (name,) for name in NONLANDS}}


def official(name):
    wire = (DATA / 'SOURCES.json').read_bytes()
    assert hashlib.sha256(wire).hexdigest() == SOURCES_SHA
    sources = json.loads(wire)
    proof = (DATA / sources['provenance_file']).read_bytes()
    assert hashlib.sha256(proof).hexdigest() == sources['provenance_sha256']
    row = sources['objects'][name]
    body = (DATA / row['file']).read_bytes()
    assert hashlib.sha256(body).hexdigest() == row['sha256']
    raw = json.loads(body)
    assert raw['object'] == 'card' and raw['name'] == name
    assert raw['id'] == row['id'] and raw['oracle_id'] == row['oracle_id']
    assert len(raw) == row['fields'] >= 60
    return raw


def expected(name):
    raw = official(name)
    head = raw['type_line'].partition(' \u2014 ')[0].split()
    types = [word for word in head if word in {
        'Artifact', 'Battle', 'Creature', 'Enchantment', 'Instant', 'Land',
        'Planeswalker', 'Sorcery', 'Kindred', 'Tribal'}]
    assert types, 'RAW types'
    # All seven exact objects have no keyword metadata. Do not share Factory
    # inference, infer abilities from substrings, or silently drop new metadata.
    assert raw['keywords'] == []
    assert raw['layout'] == 'normal' and raw.get('card_faces', []) == []
    values = {key: raw[key] for key in ('name', 'mana_cost', 'oracle_text', 'type_line')}
    values.update(types=types, keywords=[], colors=raw['colors'], loyalty=None)
    for key in ('power', 'toughness'):
        text = raw.get(key)
        assert text is None or type(text) is str and text.isdecimal()
        values[key] = None if text is None else int(text)
        values['printed_' + key] = text
    physical = {**deepcopy(values), 'card_faces': [], 'layout': raw['layout'],
                'selected_face_index': None, 'image_uri': raw['image_uris']['normal']}
    return values, physical


def assert_complete(card, name):
    values, physical = expected(name)
    record = card.characteristic_record
    assert type(record) is dict and set(record) == {'version', 'physical', 'values'}
    assert type(record['version']) is int and record['version'] == 1
    assert type(record['physical']) is dict and set(record['physical']) == set(physical)
    assert type(record['values']) is dict and set(record['values']) == set(values)
    for actual, wanted in ((vars(card), physical),
                           (record['physical'], physical), (record['values'], values)):
        for key, value in wanted.items():
            assert type(actual[key]) is type(value), key
            assert actual[key] == value, key
            if type(value) is list and value:
                assert all(type(item) is str for item in actual[key]), key
    assert card.is_token is False


def native_birth(name, owner=1):
    raw = official(name)
    row = {**raw, 'card_name': name, 'quantity': 60,
           'image_uri': raw['image_uris']['normal']}
    state = MatchFactory.from_decks([row], [deepcopy(row)], seed=8)
    return state, state.cards[f'p{owner}-053']


def invoke(scene):
    if scene == 'bulk':
        return original.test_tap_lands_bulk_adds_mana_and_taps_requested_count()
    if scene == 'dual':
        return original.test_basic_is_used_before_dual_to_preserve_other_color()
    function = original.test_fixed_multi_mana_sources_produce_printed_amount
    marks = [mark for mark in function.pytestmark
             if mark.name == 'parametrize' and mark.args[0] == 'name,types,text,color,amount']
    assert len(marks) == 1
    rows = [row for row in marks[0].args[1] if row[0] == scene]
    assert len(rows) == 1
    return function(*deepcopy(rows[0]))


class ConsumerReached(BaseException):
    """Stop only this observation probe before an unchanged real call."""


def capture(scene):
    observed = {'births': [], 'rng_before': random.getstate()}
    initialize = sideboard_facts.initialize

    def birth(state, inventory):
        result = initialize(state, inventory)
        observed['births'].append(deepcopy(state))
        return result

    def observe(state):
        if set(WANTED[scene]) <= {card.name for card in state.cards.values()}:
            observed['state'] = state
            raise ConsumerReached

    def plain(real):
        def call(state, *args, **kwargs):
            observe(state)
            return real(state, *args, **kwargs)
        return call

    def method(real):
        def call(engine, state, *args, **kwargs):
            observe(state)
            return real(engine, state, *args, **kwargs)
        return call

    with patch.object(sideboard_facts, 'initialize', birth), \
            patch.object(original, 'nonland_mana_outputs', plain(original.nonland_mana_outputs)), \
            patch.object(original, 'can_pay_with_pool_and_lands', plain(original.can_pay_with_pool_and_lands)), \
            patch.object(original.RulesEngine, 'take_action', method(original.RulesEngine.take_action)):
        with pytest.raises(ConsumerReached):
            invoke(scene)
    observed['rng_after'] = random.getstate()
    assert 'state' in observed
    return observed


@pytest.mark.parametrize('name', NAMES)
def test_complete_official_objects_and_provenance_are_independent(name):
    first, second = official(name), official(name)
    assert {'legalities', 'uri', 'rulings_uri', 'colors', 'keywords'} <= first.keys()
    first['legalities'].clear()
    assert second == official(name)
    proof = json.loads((DATA / 'PROVENANCE.json').read_bytes())['objects'][name]
    if name in ('Llanowar Tribe', 'Watery Grave'):
        assert proof['http_status'] == 200 and proof['TLS_verify_result'] == 0
        assert proof['response_sha256'] == hashlib.sha256(
            (DATA / json.loads((DATA / 'SOURCES.json').read_bytes())['objects'][name]['file']).read_bytes()
        ).hexdigest()


@pytest.mark.parametrize('name', NAMES)
@pytest.mark.parametrize('owner', (1, 2))
def test_real_native_birth_has_full_live_physical_copiable_and_stock_facts(name, owner):
    state, card = native_birth(name, owner)
    assert_complete(card, name)
    assert card.owner == card.controller == owner and card.zone == Zone.LIBRARY
    assert state.sideboard_facts['capture_version'] == 3
    assert state.sideboard_facts['coverage_ok'] is True
    assert len(state.sideboard_facts['inventory']) == 120
    assert state.sideboard_facts['inventory'][card.id] == {'owner': owner, 'stock_key': name}
    before = serialize_match_snapshot(state)
    restored = deserialize_match_snapshot(before)
    assert serialize_match_snapshot(restored) == before
    assert_complete(restored.cards[card.id], name)


@pytest.mark.parametrize('name', NAMES)
@pytest.mark.parametrize('field,value', [('types', ['Battle']), ('keywords', ['flying'])])
def test_independent_oracle_rejects_coherent_live_physical_values_corruption(name, field, value):
    state, card = native_birth(name)
    assert_complete(card, name)
    setattr(card, field, deepcopy(value))
    card.characteristic_record['physical'][field] = deepcopy(value)
    card.characteristic_record['values'][field] = deepcopy(value)
    before = deepcopy(vars(card))
    with pytest.raises(AssertionError, match=field):
        assert_complete(card, name)
    assert vars(card) == before


@pytest.mark.parametrize('name', NAMES)
def test_live_physical_copiable_records_and_raw_reader_do_not_alias(name):
    state, card = native_birth(name)
    assert_complete(card, name)
    raw_before = official(name)
    values_before = deepcopy(card.characteristic_record['values'])
    live_types, live_keywords = deepcopy(card.types), deepcopy(card.keywords)
    card.characteristic_record['physical']['types'].append('Battle')
    assert card.types == live_types
    assert card.characteristic_record['values'] == values_before
    card.characteristic_record['values']['keywords'].append('flying')
    assert card.keywords == live_keywords
    assert card.characteristic_record['physical']['keywords'] == live_keywords
    assert official(name) == raw_before


@pytest.mark.parametrize('scene', SCENES)
def test_unchanged_actual_first_consumer_receives_complete_named_and_basic_facts(scene):
    state = capture(scene)['state']
    assert set(WANTED[scene]) <= {card.name for card in state.cards.values()}
    for card in state.cards.values():
        assert card.name in NAMES
        assert_complete(card, card.name)
    target = state.cards['p1-053']
    assert target.name == WANTED[scene][0] and target.owner == target.controller == 1
    assert target.zone == Zone.BATTLEFIELD and target.summoning_sick is False


@pytest.mark.parametrize('scene', SCENES)
def test_named_original_source_was_truthful_at_normal_capture_not_retagged_afterward(scene):
    observed = capture(scene)
    assert len(observed['births']) == 1
    birth, state = observed['births'][0], observed['state']
    assert birth.sideboard_facts['capture_version'] == 3
    assert birth.sideboard_facts['coverage_ok'] is True
    for name in WANTED[scene]:
        cards = [card for card in state.cards.values() if card.name == name]
        assert cards
        for card in cards:
            original_card = birth.cards[card.id]
            assert_complete(original_card, name)
            assert original_card.zone == Zone.LIBRARY
            assert birth.sideboard_facts['inventory'][card.id] == {'owner': card.owner, 'stock_key': name}
    for owner in (1, 2):
        expected_stock = Counter(row['card_name'] for row in state.starting_decks[owner]
                                 for _ in range(row['quantity']))
        actual_stock = Counter(row['stock_key'] for row in birth.sideboard_facts['inventory'].values()
                               if row['owner'] == owner)
        assert actual_stock == expected_stock and sum(actual_stock.values()) == 60


@pytest.mark.parametrize('scene', SCENES)
def test_original_shuffle_rng_ids_draw_counts_and_source_poses_are_preserved(scene):
    observed = capture(scene)
    state = observed['state']
    reference = random.Random(8)
    if scene == 'bulk':
        reference.setstate(observed['rng_before'])
    reference.shuffle(list(range(60)))
    reference.shuffle(list(range(60)))
    assert (observed['rng_after'] if scene == 'bulk' else state.rng.getstate()) == reference.getstate()
    assert set(state.cards) == {f'p{owner}-{index:03d}' for owner in (1, 2) for index in range(1, 61)}
    for owner in (1, 2):
        assert state.players[owner].hand == [f'p{owner}-{index:03d}' for index in range(60, 53, -1)]
    used = 3 if scene == 'bulk' else 2 if scene == 'dual' else 1
    assert state.players[1].battlefield == [f'p1-{index:03d}' for index in range(53, 53-used, -1)]
    assert state.players[1].library == [f'p1-{index:03d}' for index in range(1, 54-used)]
    assert state.players[2].library == [f'p2-{index:03d}' for index in range(1, 54)]
    if scene == 'dual':
        assert state.cards['p1-052'].name == 'Island'


@pytest.mark.parametrize('scene', SCENES)
@pytest.mark.parametrize('owner', (1, 2))
def test_real_first_consumer_snapshot_and_stock_tamper_reject_with_root_purity(scene, owner):
    state = capture(scene)['state']
    assert state.sideboard_facts.get('capture_version') == 3
    before = serialize_match_snapshot(state)
    assert serialize_match_snapshot(deserialize_match_snapshot(before)) == before
    bad = deepcopy(state)
    bad.cards[bad.players[owner].hand[0]].name = 'Noncard corrupted stock'
    with pytest.raises(ValueError, match='Sideboard stock'):
        serialize_match_snapshot(bad)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('name', NONLANDS)
def test_unchanged_named_mana_outcomes_use_full_facts_and_genuine_commands(name):
    real = original.nonland_mana_outputs
    observed = []

    def checked(state, cid, card):
        assert_complete(card, name)
        observed.append(cid)
        return real(state, cid, card)

    with patch.object(original, 'nonland_mana_outputs', checked):
        invoke(name)
    assert observed and set(observed) == {'p1-053'}


def test_unchanged_dual_payment_forwards_real_auto_pay_with_full_entry_text():
    real = original.auto_pay_cost
    observed = []

    def checked(state, *args, **kwargs):
        assert_complete(state.cards['p1-053'], 'Watery Grave')
        assert_complete(state.cards['p1-052'], 'Island')
        observed.append(True)
        return real(state, *args, **kwargs)

    with patch.object(original, 'auto_pay_cost', checked):
        invoke('dual')
    assert observed == [True]
