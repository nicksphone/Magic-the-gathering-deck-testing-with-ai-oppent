"""Independent RAW and real caller/birth controls; no synthetic-scope waiver."""
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
from tests import test_continuous_static_effects as original

FIXTURES = Path(__file__).parent / 'fixtures'
SOURCE = FIXTURES / 'static_layers_a32/SOURCES.json'
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == 'e576308cfa2da6a4d1df29c00555906c9d75672ea8f0e556b4177e915be31889'
SOURCES = json.loads(SOURCE.read_text())
SCENES = (
    ('test_tribal_static_buff_applies_to_subtype', {59: 'Llanowar Elves'}, {60: 'Elvish Anthem', 58: 'Bear'}),
    ('test_become_base_power_toughness_static_sets_are_parsed', {59: 'Hill Giant'}, {60: 'Humility Field'}),
    ('test_subject_specific_base_pt_set_only_applies_to_matching_creatures', {59: 'Llanowar Elves'}, {60: 'Elf Ward', 58: 'Knight'}),
    ('test_state_actions_repeat_when_a_lord_dies_and_its_buff_disappears', {60: 'Elvish Clancaller', 59: 'Llanowar Elves'}, {}),
    ('test_cascading_death_triggers_share_one_order_choice_after_restore', {60: 'Elvish Clancaller', 59: 'Llanowar Elves', 58: 'Grim Haruspex'}, {}),
    ('test_characteristic_defined_pt_counts_distinct_graveyard_card_types', {60: 'Tarmogoyf'}, {}),
)


def official(name):
    row = SOURCES[name]
    body = (FIXTURES / row['file']).read_bytes()
    assert hashlib.sha256(body).hexdigest() == row['file_sha256']
    body = body.splitlines()[row['line'] - 1] if row['line'] else body
    assert hashlib.sha256(body).hexdigest() == row['raw_sha256']
    raw = json.loads(body)
    assert raw['name'] == name and raw['id'] == row['id'] and raw['oracle_id'] == row['oracle_id']
    return raw


def assert_full(card, name):
    raw = official(name)
    # Printed card types come from the RAW head, not the Factory/helper parser.
    head = raw['type_line'].partition(' \u2014 ')[0].split()
    expected_types = [word for word in head if word in {
        'Artifact', 'Battle', 'Creature', 'Enchantment', 'Instant', 'Land',
        'Planeswalker', 'Sorcery', 'Kindred', 'Tribal'}]
    assert expected_types, 'types'
    assert card.types == expected_types, 'types'
    # Morph stays in full Oracle/RAW metadata, not the engine's standing-keyword
    # list. These six pinned cards have no other printed keyword to project.
    assert set(raw['keywords']) <= {'Morph'}, 'Unqualified RAW keyword projection'
    expected_keywords = [keyword.casefold() for keyword in raw['keywords'] if keyword != 'Morph']
    assert card.keywords == expected_keywords, 'keywords'
    for field in ('name', 'mana_cost', 'oracle_text', 'type_line', 'layout'):
        assert getattr(card, field) == raw.get(field, ''), field
    for field in ('power', 'toughness'):
        text = raw.get(field)
        expected = int(text) if text is not None and text.isdecimal() else None
        assert getattr(card, field) == expected, field
        assert getattr(card, 'printed_' + field) == text
    assert card.card_faces == raw.get('card_faces', [])
    assert card.colors == raw['colors']
    assert card.image_uri == raw['image_uris']['normal']
    record = card.characteristic_record
    assert type(record) is dict and record['version'] == 1
    for field in ('name', 'mana_cost', 'oracle_text', 'type_line', 'power', 'toughness', 'printed_power', 'printed_toughness', 'colors', 'types', 'keywords'):
        assert record['physical'][field] == getattr(card, field)
        assert record['values'][field] == getattr(card, field)


def birth_only(function):
    states = []
    real = MatchFactory.from_decks
    class Reached(Exception):
        pass
    def observe(*args, **kwargs):
        state = real(*args, **kwargs)
        states.append(state)
        raise Reached
    with patch.object(MatchFactory, 'from_decks', observe), pytest.raises(Reached):
        getattr(original, function)()
    assert len(states) == 1
    return states[0]


@pytest.mark.parametrize('name', tuple(sorted(SOURCES)))
def test_full_raw_reuse_and_independence(name):
    first, second = official(name), official(name)
    assert first['object'] == 'card'
    assert {'legalities', 'rulings_uri', 'oracle_id', 'uri', 'oracle_text', 'type_line', 'mana_cost'} <= first.keys()
    first['legalities'].clear()
    assert second == official(name)
    proof = FIXTURES / 'static_layers_a32/PROVENANCE.json'
    assert hashlib.sha256(proof.read_bytes()).hexdigest() == '86b5c544dde1bb874ab3f451a1c194d3baee3038e13f6da4276a8acc519efa16'
    origin = json.loads(proof.read_text())['objects'][name]
    if name != 'Hill Giant':
        body = (FIXTURES / origin['file']).read_bytes()
        assert hashlib.sha256(body).hexdigest() == origin['file_sha256']
        body = body.splitlines()[origin['line'] - 1] if origin['line'] else body
        assert hashlib.sha256(body).hexdigest() == origin['raw_sha256']
        assert json.loads(body) == second
    if name == 'Hill Giant':
        assert SOURCES[name]['raw_sha256'] == '869aef4e953041c120e763204e507901780fa2f5f30ac6560dd1f74351788861'
        assert (second['power'], second['toughness']) == ('3', '3')
    if name == 'Grim Haruspex':
        assert 'Morph' in second['oracle_text']


@pytest.mark.parametrize('function,named,synthetic', SCENES, ids=[row[0] for row in SCENES])
def test_actual_native_inventory_is_canonical_before_capture(function, named, synthetic):
    captures = []
    initialize = sideboard_facts.initialize
    def observe(state, inventory):
        result = initialize(state, inventory)
        captures.append(deepcopy(state))
        return result
    with patch.object(sideboard_facts, 'initialize', observe):
        getattr(original, function)()
    assert len(captures) == 1
    state = captures[0]
    assert len(state.cards) == len(state.sideboard_facts['inventory']) == 120
    expected = Counter({'Forest': 60 - len(named) - len(synthetic)}) + Counter(named.values()) + Counter(synthetic.values())
    assert Counter({name: sum(row['quantity'] for row in state.starting_decks[1] if row['card_name'] == name) for name in expected}) == expected
    for position, name in {**named, **synthetic}.items():
        cid = f'p1-{position:03d}'
        assert state.cards[cid].name == name
        assert state.sideboard_facts['inventory'][cid] == {'owner': 1, 'stock_key': name}
    for position, name in named.items():
        card = state.cards[f'p1-{position:03d}']
        assert_full(card, name)
        assert card.zone == Zone.LIBRARY and card.summoning_sick is True
    assert state.sideboard_facts['capture_version'] == 3 and state.sideboard_facts['coverage_ok'] is True


@pytest.mark.parametrize('function,named,synthetic', SCENES, ids=[row[0] for row in SCENES])
def test_original_first_consumers_receive_complete_current_named_pose(function, named, synthetic):
    seen = []
    def check(state):
        for position, name in named.items():
            card = state.cards[f'p1-{position:03d}']
            assert_full(card, name)
            assert card.owner == card.controller == 1
            assert card.summoning_sick is False
        before = serialize_match_snapshot(state)
        restored = deserialize_match_snapshot(before)
        assert serialize_match_snapshot(restored) == before
        seen.append(True)
    def wrap(real):
        def invoke(state, *args, **kwargs):
            check(state)
            return real(state, *args, **kwargs)
        return invoke
    with patch.object(original, 'effective_power', wrap(original.effective_power)), patch.object(original, 'effective_toughness', wrap(original.effective_toughness)), patch.object(original, 'apply_state_based_actions', wrap(original.apply_state_based_actions)):
        getattr(original, function)()
    assert seen


@pytest.mark.parametrize('function,named,synthetic', SCENES, ids=[row[0] for row in SCENES])
@pytest.mark.parametrize('owner', (1, 2))
def test_normal_capture_snapshot_and_stock_mutations_reject_without_root_changes(function, named, synthetic, owner):
    state = birth_only(function)
    assert state.sideboard_facts.get('capture_version') == 3
    for position, name in named.items():
        assert_full(state.cards[f'p1-{position:03d}'], name)
    before = serialize_match_snapshot(state)
    assert serialize_match_snapshot(deserialize_match_snapshot(before)) == before
    bad = deepcopy(state)
    bad.cards[bad.players[owner].hand[0]].name = 'Noncard stock mutation'
    with pytest.raises(ValueError, match='Sideboard stock'):
        serialize_match_snapshot(bad)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('function,named,synthetic', SCENES, ids=[row[0] for row in SCENES])
def test_actual_factory_keeps_shuffle_rng_ids_and_draw_counts(function, named, synthetic):
    observations = []
    factory = MatchFactory.from_decks
    def observe(*args, **kwargs):
        seed = kwargs.get('seed')
        expected = random.Random(seed) if seed is not None else random.Random(0)
        if seed is None:
            expected.setstate(random.getstate())
        expected.shuffle(list(range(60)))
        expected.shuffle(list(range(60)))
        state = factory(*args, **kwargs)
        assert (state.rng.getstate() if seed is not None else random.getstate()) == expected.getstate()
        for owner in (1, 2):
            assert state.players[owner].hand == [f'p{owner}-{position:03d}' for position in range(60, 53, -1)]
            assert state.players[owner].library == [f'p{owner}-{position:03d}' for position in range(1, 54)]
        observations.append(True)
        return state
    with patch.object(MatchFactory, 'from_decks', observe):
        getattr(original, function)()
    assert observations == [True]


@pytest.mark.parametrize('field,value', [('name', 'Forest'), ('oracle_text', 'Draw a card.'), ('type_line', 'Creature - Elf Warrior'), ('power', 8), ('printed_power', '8'), ('card_faces', [{'name': 'Unknown face'}]), ('owner', 2), ('id', 'unknown-id')])
def test_named_placement_rejects_mutated_birth_before_any_move(field, value):
    function = 'test_state_actions_repeat_when_a_lord_dies_and_its_buff_disappears'
    state = birth_only(function)
    card = state.cards['p1-060']
    assert_full(card, 'Elvish Clancaller')
    setattr(card, field, value)
    before = deepcopy((vars(card), state.players[1].hand, state.players[1].battlefield, state.sideboard_facts))
    with pytest.raises(ValueError):
        original._setup_creature(state, 1, 'Elvish Clancaller')
    assert (vars(card), state.players[1].hand, state.players[1].battlefield, state.sideboard_facts) == before


@pytest.mark.parametrize('name', tuple(sorted(SOURCES)))
@pytest.mark.parametrize('field,value', [('types', ['Artifact']), ('keywords', ['flying'])])
def test_independent_oracle_rejects_coherent_live_physical_and_values_corruption(name, field, value):
    function = next((function for function, named, _ in SCENES if name in named.values()), SCENES[0][0])
    state = birth_only(function)
    card = next(card for card in state.cards.values() if card.name == name)
    assert_full(card, name)
    setattr(card, field, deepcopy(value))
    card.characteristic_record['physical'][field] = deepcopy(value)
    card.characteristic_record['values'][field] = deepcopy(value)
    before = deepcopy(vars(card))
    with pytest.raises(AssertionError, match=field):
        assert_full(card, name)
    assert vars(card) == before
