"""Full RAW at the real assigned consumers/births; PREP cases, not a pass claim."""
from copy import deepcopy
import hashlib
import json
import random

import pytest

from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from game_state.state import MatchFactory
from rules_engine.copiable_values import FIELDS, PHYSICAL
from tests import combat_sacrifice191_canonical as canonical
from tests import test_combat_advanced as combat_tests
from tests import test_sacrifice_team_counters as sacrifice_tests

NAMES = ('Island', 'Forest', 'Llanowar Elves', 'Elvish Mystic', 'Palace Guard',
         'Hallowed Fountain', 'Sol Ring', 'Mazirek, Kraul Death Priest')
SACRIFICE_CARDS = {'mazirek': 'Mazirek, Kraul Death Priest', 'ally': 'Llanowar Elves',
                   'fuel': 'Sol Ring', 'enemy': 'Llanowar Elves', 'enemy_fuel': 'Sol Ring'}
COMBAT_CASES = {
    'guard': (41, combat_tests.test_one_blocker_cannot_deal_full_power_to_each_attacker,
              {'p1-060': 'Llanowar Elves', 'p1-059': 'Elvish Mystic', 'p2-060': 'Palace Guard'}),
    'fountain': (21, combat_tests.test_nonbasic_landwalk_prevents_blocking,
                 {'p2-059': 'Hallowed Fountain'}),
}


def expected_printed(name):
    # Independent of the fixture materializer/production normalization result.
    raw = canonical.raw_card(name)
    front = raw['type_line'].split('—', 1)[0].split('-', 1)[0].split()
    kinds = ('Artifact', 'Battle', 'Creature', 'Enchantment', 'Instant', 'Land',
             'Planeswalker', 'Sorcery')
    return dict(name=raw['name'], oracle_text=raw.get('oracle_text', ''),
        mana_cost=raw.get('mana_cost', ''), type_line=raw['type_line'],
        types=[kind for kind in kinds if kind in front],
        power=int(raw['power']) if raw.get('power') is not None else None,
        toughness=int(raw['toughness']) if raw.get('toughness') is not None else None,
        printed_power=raw.get('power'), printed_toughness=raw.get('toughness'),
        loyalty=int(raw['loyalty']) if raw.get('loyalty') is not None else None,
        colors=raw['colors'], keywords=[word.lower() for word in raw.get('keywords', [])],
        layout=raw['layout'], card_faces=raw.get('card_faces', []), selected_face_index=None,
        image_uri=raw.get('image_uris', {}).get('normal'))


def assert_printed(card, name):
    expected = expected_printed(name)
    for field, value in expected.items():
        assert getattr(card, field) == value, (name, field)
    assert type(card.characteristic_record['version']) is int and card.characteristic_record['version'] == 1
    assert card.characteristic_record['physical'] == {key: deepcopy(expected[key]) for key in PHYSICAL}
    assert card.characteristic_record['values'] == {key: deepcopy(expected[key]) for key in FIELDS}


@pytest.mark.parametrize('case', ['guard', 'fountain'])
def test_real_factory_returns_full_named_stock_before_setup(monkeypatch, case):
    seed, function, expected = COMBAT_CASES[case]
    original = MatchFactory.from_decks
    births = []
    def observe(deck_a, deck_b, *args, **kwargs):
        state = original(deck_a, deck_b, *args, **kwargs)
        if kwargs.get('seed') == seed:
            births.append(deepcopy(state))
            for cid, name in expected.items():
                assert_printed(state.cards[cid], name)
                assert state.sideboard_facts['inventory'][cid] == {'owner': state.cards[cid].owner, 'stock_key': name}
            assert sum(row['quantity'] for row in deck_a) == sum(row['quantity'] for row in deck_b) == 60
            assert state.players[1].hand == [f'p1-{i:03d}' for i in range(60, 53, -1)]
            assert state.players[2].hand == [f'p2-{i:03d}' for i in range(60, 53, -1)]
            preview = random.Random(seed)
            preview.shuffle(list(range(60))); preview.shuffle(list(range(60)))
            assert state.rng.getstate() == preview.getstate()
        return state
    with monkeypatch.context() as patch:
        patch.setattr(MatchFactory, 'from_decks', observe)
        function()
    assert len(births) == 1
    restored = deserialize_match_snapshot(serialize_match_snapshot(births[0]))
    assert restored.sideboard_facts == births[0].sideboard_facts
    for cid, name in expected.items():
        assert_printed(restored.cards[cid], name)


@pytest.mark.parametrize('case', ['guard', 'fountain'])
def test_real_blocking_consumer_gets_full_printed_fields(monkeypatch, case):
    _, function, expected = COMBAT_CASES[case]
    original = combat_tests.combat.declare_blockers
    observed = []
    def observe(state, *args, **kwargs):
        for cid, name in expected.items():
            assert_printed(state.cards[cid], name)
            assert state.sideboard_facts['inventory'][cid]['stock_key'] == name
        observed.append(tuple(expected))
        return original(state, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(combat_tests.combat, 'declare_blockers', observe)
        function()
    assert observed == [tuple(expected)]


@pytest.mark.parametrize('owner,cid', [(1, 'fuel'), (2, 'enemy_fuel')])
def test_real_sacrifice_consumer_gets_all_five_full_named_cards(monkeypatch, owner, cid):
    original = sacrifice_tests.sacrifice
    observed = []
    def observe(state, *args, **kwargs):
        for identifier, name in SACRIFICE_CARDS.items():
            assert_printed(state.cards[identifier], name)
        observed.append(tuple(SACRIFICE_CARDS))
        return original(state, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(sacrifice_tests, 'sacrifice', observe)
        sacrifice_tests.test_either_player_sacrifice_puts_counter_on_current_friendly_creatures(owner, cid)
    assert observed == [tuple(SACRIFICE_CARDS)]


def capture_constructor(monkeypatch, callback):
    original = sacrifice_tests.CardInstance
    def observe(*args, **kwargs):
        card = original(*args, **kwargs)
        if card.id in {*SACRIFICE_CARDS, 'newcomer'}:
            callback(card)
        return card
    monkeypatch.setattr(sacrifice_tests, 'CardInstance', observe)
    monkeypatch.setattr(canonical, 'CardInstance', observe)


def test_full_facts_exist_at_actual_extra_card_constructor_return(monkeypatch):
    observed = []
    def check(card):
        assert_printed(card, SACRIFICE_CARDS[card.id])
        observed.append(card.id)
    capture_constructor(monkeypatch, check)
    sacrifice_tests._state()
    assert observed == list(SACRIFICE_CARDS)


def test_resolution_time_newcomer_is_full_at_birth_before_original_actions(monkeypatch):
    observed = []
    def check(card):
        assert_printed(card, 'Llanowar Elves' if card.id == 'newcomer' else SACRIFICE_CARDS[card.id])
        observed.append(card.id)
    capture_constructor(monkeypatch, check)
    sacrifice_tests.test_team_counter_trigger_uses_creatures_present_at_resolution()
    assert observed == [*SACRIFICE_CARDS, 'newcomer']


def test_extra_card_fixture_preserves_native_initial_stock_and_snapshot():
    state = sacrifice_tests._state()
    facts, decks, rng = deepcopy(state.sideboard_facts), deepcopy(state.starting_decks), state.rng.getstate()
    assert set(facts['inventory']) == {f'p{seat}-{i:03d}' for seat in (1, 2) for i in range(1, 61)}
    assert all(row['stock_key'] == 'Island' for row in facts['inventory'].values())
    assert not set(SACRIFICE_CARDS).intersection(facts['inventory'])
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert restored.sideboard_facts == facts and restored.starting_decks == decks
    assert state.sideboard_facts == facts and state.starting_decks == decks and state.rng.getstate() == rng
    for identifier, name in SACRIFICE_CARDS.items():
        assert_printed(restored.cards[identifier], name)


@pytest.mark.parametrize('name', NAMES)
def test_native_card_constructor_has_complete_typed_printed_and_face_fields(name):
    card = canonical.canonical_card(name, id='full-printed-fixture', owner=2, controller=1,
                                    zone=canonical.Zone.BATTLEFIELD)
    assert_printed(card, name)
    assert (card.id, card.owner, card.controller, card.zone) == ('full-printed-fixture', 2, 1, canonical.Zone.BATTLEFIELD)


@pytest.mark.parametrize('field', ['mana_cost', 'type_line', 'oracle_text', 'colors', 'keywords', 'power'])
def test_independent_full_RAW_checker_rejects_coherent_protocol_corruption(field):
    card = canonical.canonical_card('Palace Guard', id='negative-protocol', owner=1,
                                    controller=1, zone=canonical.Zone.BATTLEFIELD)
    value = getattr(card, field)
    changed = value + ['PROTOCOL_NEGATIVE'] if type(value) is list else value + 1 if type(value) is int else value + ' PROTOCOL_NEGATIVE'
    setattr(card, field, changed)
    card.characteristic_record['physical'][field] = deepcopy(changed)
    card.characteristic_record['values'][field] = deepcopy(changed)
    with pytest.raises(AssertionError):
        assert_printed(card, 'Palace Guard')


@pytest.mark.parametrize('field', ['oracle_text', 'mana_cost', 'types', 'power', 'printed_power',
    'colors', 'keywords', 'layout', 'card_faces', 'selected_face_index',
    'printed_characteristics', 'characteristic_record', 'knowledge_snapshot'])
def test_printed_field_override_is_not_a_physical_pose(field):
    with pytest.raises(ValueError):
        canonical.canonical_card('Palace Guard', id='bad-pose', owner=1, controller=1,
                                 zone=canonical.Zone.BATTLEFIELD, **{field: None})


def test_complete_source_admissions_have_identity_and_no_RAW_reconstruction():
    data = (canonical.FIXTURES / 'combat_sacrifice191/SOURCES.json').read_bytes()
    assert hashlib.sha256(data).hexdigest() == canonical.SOURCES_SHA256
    records = json.loads(data)['objects']
    assert set(records) == set(NAMES)
    for name in NAMES:
        raw = canonical.raw_card(name)
        assert raw['object'] == 'card' and raw['name'] == name
        assert raw['id'] == records[name]['id'] and raw['oracle_id'] == records[name]['oracle_id']
        assert type(raw['oracle_text']) is str and type(raw['colors']) is list
