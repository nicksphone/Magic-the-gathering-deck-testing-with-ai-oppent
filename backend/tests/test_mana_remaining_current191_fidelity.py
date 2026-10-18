"""Independent full-fact consumers; authored PREP, not executed qualification."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random

import pytest

from ai import sideboard_facts
from ai.sideboard_facts import copy_facts
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from tests import test_mana_system as original
from tests import mana_remaining_current191 as fixture

FIXTURES = Path(__file__).parent / 'fixtures'
SOURCE_SHA = 'f629355f018f2e6a23c299ac1f8d2e51464eb756fe7c0c5bd5788f6c3d64362f'
NAMES = ('Plains', 'Island', 'Forest', 'Realmwalker', 'Spectral Procession',
         'Figure of Destiny', 'Pestilent Souleater', 'Tamiyo, Compleated Sage',
         'Mutagenic Growth', 'Llanowar Elves', 'Font of Agonies',
         'Hallowed Fountain', 'Marble Diamond', 'Lavinia, Azorius Renegade', 'Gilded Lotus')
CASES = (
    ('realmwalker', 'test_hybrid_choices_are_exposed_for_exile_and_top_library_casts',
     'legal_moves', ('Realmwalker', 'Spectral Procession', 'Figure of Destiny')),
    ('souleater', 'test_pestilent_souleater_activated_phyrexian_choice',
     'legal_moves', ('Pestilent Souleater',)),
    ('tamiyo', 'test_compleated_uses_announced_phyrexian_life_choice_on_entry',
     'checked_action', ('Tamiyo, Compleated Sage',)),
    ('font', 'test_mutagenic_growth_phyrexian_life_trigger_is_above_spell',
     'legal_moves', ('Font of Agonies', 'Mutagenic Growth', 'Llanowar Elves')),
    ('fountain', 'test_nonland_single_color_source_is_used_before_flexible_land',
     'legal_moves', ('Hallowed Fountain', 'Marble Diamond', 'Lavinia, Azorius Renegade')),
    ('lotus', 'test_multi_mana_source_surplus_pays_generic_cost',
     'can_pay_with_pool_and_lands', ('Gilded Lotus',)),
)
PRIMARY = (
    ('realmwalker', 'Realmwalker'), ('souleater', 'Pestilent Souleater'),
    ('tamiyo', 'Tamiyo, Compleated Sage'), ('font', 'Font of Agonies'),
    ('fountain', 'Hallowed Fountain'), ('lotus', 'Gilded Lotus'),
)


def official(name):
    body = (FIXTURES / 'mana_remaining_current191/SOURCES.json').read_bytes()
    assert hashlib.sha256(body).hexdigest() == SOURCE_SHA
    pin = json.loads(body)['objects'][name]
    body = (FIXTURES / pin['file']).read_bytes()
    assert hashlib.sha256(body).hexdigest() == pin['file_sha256']
    body = body.splitlines()[pin['line'] - 1] if pin['line'] else body
    assert hashlib.sha256(body).hexdigest() == pin['raw_sha256']
    raw = json.loads(body)
    assert raw['object'] == 'card' and raw['name'] == name
    assert len(raw) == pin['fields'] >= 60
    assert raw['id'] == pin['id'] and raw['oracle_id'] == pin['oracle_id']
    return raw


def assert_full(card, name):
    raw = official(name)
    assert raw['layout'] == 'normal' and raw.get('card_faces', []) == []
    # These RAW keywords remain in full Oracle; this engine derives their rules
    # outside the standing-evergreen keyword list. Never use its infer helper.
    assert set(raw['keywords']) <= {'Changeling', 'Compleated'}
    head = raw['type_line'].partition(' \u2014 ')[0].split()
    types = [word for word in head if word in {
        'Artifact', 'Battle', 'Creature', 'Enchantment', 'Instant',
        'Kindred', 'Land', 'Planeswalker', 'Sorcery', 'Tribal'}]
    assert types
    numeric = lambda text: int(text) if text is not None and text.lstrip('-').isdigit() else None
    values = {key: raw.get(key, '') for key in ('name', 'mana_cost', 'type_line', 'oracle_text')}
    values.update(types=types, keywords=[], colors=raw['colors'],
                  power=numeric(raw.get('power')), toughness=numeric(raw.get('toughness')),
                  printed_power=raw.get('power'), printed_toughness=raw.get('toughness'),
                  loyalty=numeric(raw.get('loyalty')))
    physical = {**values, 'card_faces': [], 'layout': raw['layout'],
                'selected_face_index': None, 'image_uri': raw['image_uris']['normal']}
    for key, expected in physical.items():
        actual = getattr(card, key)
        assert type(actual) is type(expected) and actual == expected, key
        if type(expected) is list:
            assert all(type(item) is str for item in actual), key
    record = card.characteristic_record
    assert type(record) is dict and type(record['version']) is int and record['version'] == 1
    assert set(record) == {'version', 'physical', 'values'}
    assert record['physical'] == physical and record['values'] == values
    for slot, expected in ((record['physical'], physical), (record['values'], values)):
        assert all(type(slot[key]) is type(value) for key, value in expected.items())
        for key in ('types', 'keywords', 'colors'):
            assert all(type(item) is str for item in slot[key])


def participant(state, name, seat=1):
    matches = [card for card in state.cards.values() if card.owner == seat and card.name == name]
    assert len(matches) == 1
    return matches[0]


@pytest.mark.parametrize('name', NAMES)
def test_complete_official_source_identity_is_pinned(name):
    raw = official(name)
    assert fixture.raw_card(name) == raw
    assert raw['uri'].startswith('https://api.scryfall.com/cards/')


@pytest.mark.parametrize('scene,function,boundary,names', CASES, ids=[case[0] for case in CASES])
def test_actual_original_first_consumer_receives_full_native_facts(
        scene, function, boundary, names, monkeypatch):
    observed = []
    seen = set()
    births = []
    initialize = sideboard_facts.initialize

    def capture_birth(state, inventory):
        result = initialize(state, inventory)
        births.append((state.id, deepcopy(state.cards), deepcopy(inventory)))
        return result

    monkeypatch.setattr(sideboard_facts, 'initialize', capture_birth)
    if boundary == 'legal_moves':
        owner = original.RulesEngine
    else:
        owner = original
    real = getattr(owner, boundary)

    def forward(*args, **kwargs):
        state = args[1] if boundary == 'legal_moves' else args[0]
        if state.id not in seen:
            matching_births = [birth for birth in births if birth[0] == state.id]
            assert len(matching_births) == 1
            _, born_cards, born_inventory = matching_births[0]
            for name in names:
                card = participant(state, name)
                assert_full(card, name)
                assert card.id in born_cards
                assert_full(born_cards[card.id], name)
                assert born_inventory[card.id] == {'owner': card.owner, 'stock_key': name}
            assert state.sideboard_facts and len(state.sideboard_facts['inventory']) == len(state.cards)
            assert state.sideboard_facts['inventory'] == born_inventory
            assert copy_facts(state.sideboard_facts, state) == state.sideboard_facts
            before = serialize_match_snapshot(state)
            restored = deserialize_match_snapshot(deepcopy(before))
            assert serialize_match_snapshot(restored) == before
            observed.append(before)
            seen.add(state.id)
        return real(*args, **kwargs)

    monkeypatch.setattr(owner, boundary, forward)
    getattr(original, function)()
    assert len(observed) == (2 if scene == 'tamiyo' else 1)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('scene,name', PRIMARY, ids=[case[0] for case in PRIMARY])
def test_genuine_factory_birth_has_stock_full_snapshot_and_native_rng(scene, name, seat):
    state = fixture.birth(scene, seat=seat)
    spec = fixture.SCENES[scene]
    for card in state.cards.values():
        assert_full(card, card.name)
    assert copy_facts(state.sideboard_facts, state) == state.sideboard_facts
    assert len(state.cards) == 120 + len(spec['extras'])
    reference = random.Random(spec['seed'])
    for owner in (1, 2):
        size = 60 + (len(spec['extras']) if owner == seat else 0)
        values = list(range(size))
        reference.shuffle(values)
        assert len(state.players[owner].hand) == 7
        assert len(state.players[owner].library) == size - 7
        assert sum(row['quantity'] for row in state.starting_decks[owner]) == size
    assert state.rng.getstate() == reference.getstate()
    selected = participant(state, name, seat)
    assert state.sideboard_facts['inventory'][selected.id] == {'owner': seat, 'stock_key': name}
    before = serialize_match_snapshot(state)
    restored = deserialize_match_snapshot(deepcopy(before))
    assert serialize_match_snapshot(restored) == before
    assert restored.rng.getstate() == state.rng.getstate()
    for owner in (1, 2):
        assert Counter(card.name for card in restored.cards.values() if card.owner == owner) == Counter(
            row['card_name'] for row in restored.starting_decks[owner])


@pytest.mark.parametrize('slot', ['types', 'keywords'])
@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('scene,name', PRIMARY, ids=[case[0] for case in PRIMARY])
def test_coherent_all_three_slot_unprinted_fact_corruption_is_rejected(scene, name, seat, slot):
    state = fixture.birth(scene, seat=seat)
    card = participant(state, name, seat)
    before = serialize_match_snapshot(state)
    corrupted = deepcopy(card)
    forged = ['Instant'] if slot == 'types' else ['flying']
    setattr(corrupted, slot, list(forged))
    for record in ('physical', 'values'):
        corrupted.characteristic_record[record][slot] = list(forged)
    with pytest.raises(AssertionError):
        assert_full(corrupted, name)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('scene,name', PRIMARY, ids=[case[0] for case in PRIMARY])
def test_stock_name_tamper_is_rejected_without_capture_repair(scene, name, seat):
    state = fixture.birth(scene, seat=seat)
    before = serialize_match_snapshot(state)
    changed = deepcopy(before)
    selected = participant(state, name, seat)
    raw = changed['cards'][selected.id]
    raw['name'] = 'Forest' if name != 'Forest' else 'Island'
    raw['characteristic_record']['physical']['name'] = raw['name']
    raw['characteristic_record']['values']['name'] = raw['name']
    with pytest.raises(ValueError, match='Sideboard stock'):
        deserialize_match_snapshot(changed)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('scene,name', PRIMARY, ids=[case[0] for case in PRIMARY])
def test_official_loader_native_records_and_restored_root_are_independent(scene, name, seat):
    raw = fixture.raw_card(name)
    stable = official(name)
    raw['colors'].append('X')
    assert fixture.raw_card(name) == stable
    state = fixture.birth(scene, seat=seat)
    before = serialize_match_snapshot(state)
    restored = deserialize_match_snapshot(deepcopy(before))
    card, clone = participant(state, name, seat), participant(restored, name, seat)
    assert clone is not card and clone.characteristic_record is not card.characteristic_record
    assert clone.characteristic_record['physical'] is not card.characteristic_record['physical']
    assert clone.characteristic_record['values'] is not card.characteristic_record['values']
    clone.characteristic_record['physical']['keywords'].append('flying')
    assert_full(card, name)
    assert serialize_match_snapshot(state) == before
