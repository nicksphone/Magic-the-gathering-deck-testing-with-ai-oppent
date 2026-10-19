"""Independent RAW/birth checks; original consumers still execute unchanged."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory
from rules_engine import combat, state_based_actions
from tests import test_events_apnap as events
from tests import test_interactions_expanded as interactions
from tests import test_release_card_contracts as release


FIXTURES = Path(__file__).parent / 'fixtures'
SEED = FIXTURES / 'knowledge_profiles/seed155-scryfall.jsonl'
SEED_SHA = '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732'
NAMES = ('Blood Artist', 'Rest in Peace', 'Tarmogoyf')
COPIABLE = ('name', 'mana_cost', 'type_line', 'types', 'power', 'toughness',
            'printed_power', 'printed_toughness', 'loyalty', 'oracle_text', 'keywords', 'colors')
PHYSICAL = (*COPIABLE, 'card_faces', 'layout', 'selected_face_index', 'image_uri')
CASES = (
    (events, 'test_sacrifice_emits_sacrifice_trigger_for_creature',
     events, 'sacrifice', 'p1', 'Smothering Abomination', 1),
    (interactions, 'test_combat_death_replacement_exiles_creature_instead_of_graveyard',
     combat, 'combat_damage', 'rep', 'Rest in Peace', 2),
    (interactions, 'test_state_based_action_lethal_creature_emits_permanent_and_creature_death_triggers',
     state_based_actions, 'apply_state_based_actions', 'trigger', 'Blood Artist', 1),
    (release, 'test_characteristic_stats_and_unknown_stats_are_not_fabricated',
     release, 'serialize_match', 'goyf', 'Tarmogoyf', 1),
)


def _raw(name):
    # Independent whole source: no producer, normalized view or loader-as-oracle.
    if name == 'Smothering Abomination':
        body = (FIXTURES / 'smothering_sacrifice_T57/response.json').read_bytes()
        assert hashlib.sha256(body).hexdigest() == 'ff0cec752805b3545a3399925b3fc3189163a0940c2fed1d280e3b9909d80786'
        raw = json.loads(body)
        assert raw['object'] == 'card' and raw['name'] == name
        assert raw['id'] == 'aac33238-e4bd-4c72-aecc-9905232c3ab4'
        assert raw['layout'] == 'normal' and raw['keywords'] == ['Flying', 'Devoid']
        return raw
    body = SEED.read_bytes()
    assert hashlib.sha256(body).hexdigest() == SEED_SHA
    rows = [row for row in map(json.loads, body.splitlines()) if row.get('name') == name]
    assert len(rows) == 1 and rows[0]['object'] == 'card'
    assert rows[0]['layout'] == 'normal' and rows[0]['keywords'] == []
    return rows[0]


def _expected(raw):
    kinds = {'Artifact', 'Battle', 'Creature', 'Enchantment', 'Instant',
             'Kindred', 'Land', 'Planeswalker', 'Sorcery'}
    numeric = lambda text: int(text) if text is not None and text.isdecimal() else None
    image = {
        'Blood Artist': '/card-images/placeholder-creature-blood-artist-creature-vampire.svg',
        'Rest in Peace': '/card-images/placeholder-enchantment-rest-in-peace-enchantment.svg',
    }.get(raw['name'], raw['image_uris']['normal'])
    return {**{key: raw.get(key, '') for key in ('name', 'mana_cost', 'type_line', 'oracle_text', 'layout')},
            'types': [word for word in raw['type_line'].split('\u2014')[0].split() if word in kinds],
            'power': numeric(raw.get('power')), 'toughness': numeric(raw.get('toughness')),
            'printed_power': raw.get('power'), 'printed_toughness': raw.get('toughness'),
            'loyalty': None, 'keywords': ['flying'] if raw['name'] == 'Smothering Abomination' else [], 'colors': raw['colors'],
            'card_faces': raw.get('card_faces', []), 'selected_face_index': None, 'image_uri': image}


def _facts(card):
    return {key: deepcopy(getattr(card, key)) for key in PHYSICAL}


def _strict(actual, expected):
    assert type(actual) is type(expected)
    if type(expected) is dict:
        assert actual.keys() == expected.keys()
        for key in expected:
            _strict(actual[key], expected[key])
    elif type(expected) is list:
        assert len(actual) == len(expected)
        for left, right in zip(actual, expected):
            _strict(left, right)
    else:
        assert actual == expected


def _assert_full(card, before, raw):
    expected = _expected(raw)
    _strict(before, expected)
    _strict(_facts(card), expected)
    _strict(card.characteristic_record, {
        'version': 1, 'physical': expected,
        'values': {key: expected[key] for key in COPIABLE},
    })


def _run_observed(case, monkeypatch, corrupt=None):
    subject, function, owner, consumer, cid, name, seat = case
    births, stocks, seen = [], {}, []
    post_init, factory, consume = CardInstance.__post_init__, MatchFactory.from_decks, getattr(owner, consumer)

    def birth(card):
        before = _facts(card)
        post_init(card)
        births.append((card, before))

    def from_decks(*args, **kwargs):
        state = factory(*args, **kwargs)
        stocks[id(state)] = (state, deepcopy(state.starting_decks),
                             deepcopy(state.sideboard_facts), state.rng.getstate())
        return state

    def observe(state, *args, **kwargs):
        card = state.cards[cid]
        captured = [facts for born, facts in births if born is card]
        assert len(captured) == 1
        raw = _raw(name)
        _assert_full(card, captured[0], raw)
        assert (card.id, card.owner, card.controller, card.zone.value) == (cid, seat, seat, 'battlefield')
        assert card.instance_order == 0 and card.summoning_sick is True
        assert card.zone_change_sequence == 0
        born_state, decks, stock, rng = stocks[id(state)]
        assert born_state is state
        assert state.starting_decks == decks and state.sideboard_facts == stock
        assert state.rng.getstate() == rng
        restored = deserialize_match_snapshot(serialize_match_snapshot(state))
        _assert_full(restored.cards[cid], captured[0], raw)
        assert restored.sideboard_facts == stock and restored.starting_decks == decks
        if corrupt is not None:
            surface, field = corrupt
            invalid, before = deepcopy(card), deepcopy(captured[0])
            values = (before if surface == 'birth' else invalid.characteristic_record[surface]
                      if surface in ('physical', 'values') else invalid.__dict__)
            values[field] = 'INTENTIONALLY INVALID METADATA-PROTOCOL VECTOR'
            with pytest.raises(AssertionError):
                _assert_full(invalid, before, raw)
        seen.append(cid)
        return consume(state, *args, **kwargs)

    monkeypatch.setattr(CardInstance, '__post_init__', birth)
    monkeypatch.setattr(MatchFactory, 'from_decks', from_decks)
    monkeypatch.setattr(owner, consumer, observe)
    getattr(subject, function)()
    assert seen, 'The genuine original consumer must execute'


@pytest.mark.parametrize('name', NAMES)
def test_full_official_RAW_and_provenance_are_reused(name):
    raw = _raw(name)
    assert {'legalities', 'rulings_uri', 'oracle_id', 'uri', 'mana_cost', 'oracle_text', 'type_line'} <= raw.keys()
    proof = (FIXTURES / 'knowledge_profiles/PROVENANCE.json').read_bytes()
    assert hashlib.sha256(proof).hexdigest() == 'f15047f1ecb06fdaa985a58537d01b6497683637d7caf88db518dea469fc1ca2'
    assert json.loads(proof)['snapshot_sha256'] == SEED_SHA
    if name == 'Tarmogoyf':
        assert (raw['power'], raw['toughness']) == ('*', '1+*')
    raw['legalities'].clear()
    assert _raw(name)['legalities']


@pytest.mark.parametrize('case', CASES, ids=[case[1] for case in CASES])
def test_original_consumers_receive_full_native_birth_and_retained_snapshot(case, monkeypatch):
    _run_observed(case, monkeypatch)


@pytest.mark.parametrize('index,surface,field', (
    (0, 'birth', 'mana_cost'), (0, 'physical', 'oracle_text'),
    (1, 'values', 'colors'), (1, 'live', 'type_line'),
    (2, 'birth', 'types'), (2, 'physical', 'power'),
    (3, 'values', 'printed_toughness'), (3, 'live', 'printed_power'),
), ids=('artist-birth-cost', 'artist-physical-oracle', 'peace-values-colors',
        'peace-live-type', 'artist-birth-types', 'artist-physical-power',
        'goyf-values-printed-toughness', 'goyf-live-printed-power'))
def test_explicit_invalid_metadata_is_rejected_without_altering_original_consumer(index, surface, field, monkeypatch):
    _run_observed(CASES[index], monkeypatch, corrupt=(surface, field))
