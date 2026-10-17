"""Independent full-RAW observations of the original named fixture consumers."""
from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path

import pytest

from card_data.sync import ScryfallSyncService
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory
from rules_engine.copiable_values import FIELDS


FIXTURES = Path(__file__).parent / 'fixtures'
SOURCES_SHA = '8836d3da496e7a453f91fb6189758802c09a411c64c45673a30df0569a00bac8'
CASES = (
    ('test_cycling', 'test_fixed_cycling_is_a_legal_hand_action', 'legal_moves', 'cycler', 'Lonely Sandbar'),
    ('test_cycling', 'test_fixed_cycling_is_a_legal_hand_action', 'legal_moves', 'land-1', 'Island'),
    ('test_activated_ability_timing', 'test_restricted_x_payment_uses_only_black_mana_for_x', 'serialize_match_snapshot', 'p1-053', 'Crypt Rats'),
    ('test_activated_ability_timing', 'test_crypt_rats_damage_is_simultaneous_and_both_players_can_lose', 'take_action', 'bear', 'Grizzly Bears'),
    ('test_activated_ability_timing', 'test_crypt_rats_lifelink_is_one_gain_event_for_all_recipients', 'take_action', 'pridemate', "Ajani's Pridemate"),
    ('test_activated_ability_timing', 'test_crypt_rats_lifelink_gain_choice_resumes_after_snapshot', 'take_action', 'archive', "Alhammarret's Archive"),
    ('test_activated_ability_timing', 'test_crypt_rats_lifelink_gain_choice_resumes_after_snapshot', 'take_action', 'reflection', 'Boon Reflection'),
    ('test_activated_ability_timing', 'test_crypt_rats_batch_resumes_human_damage_replacements_before_lethal_sba', 'take_action', 'hekma-1', "Urza's Armor"),
)


class ConsumerCaptured(BaseException):
    pass


def _raw(name):
    data = (FIXTURES / 'cycling_timing_022758/SOURCES.json').read_bytes()
    assert hashlib.sha256(data).hexdigest() == SOURCES_SHA
    row = json.loads(data)['cards'][name]
    data = (FIXTURES / row['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == row['sha256']
    for proof in row['provenance']:
        assert hashlib.sha256((FIXTURES / proof['file']).read_bytes()).hexdigest() == proof['sha256']
    raw = json.loads(data.splitlines()[row['line'] - 1]) if row['line'] else json.loads(data)
    for step in row['steps']:
        raw = raw[step]
    encoded = json.dumps(raw, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    assert hashlib.sha256(encoded).hexdigest() == row['object_sha256']
    assert raw['object'] == 'card' and raw['name'] == name
    assert raw['id'] == row['id'] and raw['oracle_id'] == row['oracle_id']
    assert len(raw) == row['fields'] >= 60
    return raw


def _expected(name):
    raw = _raw(name)
    header = raw['type_line'].split(' // ', 1)[0].replace('\u2014', '-').split(' - ', 1)[0].split()
    types = [word for word in header if word in {
        'Artifact', 'Battle', 'Creature', 'Enchantment', 'Instant', 'Kindred',
        'Land', 'Planeswalker', 'Sorcery', 'Tribal',
    }]
    # None of these finite ten printed objects has an innate combat keyword.
    assert not set(raw.get('keywords', [])) - {
        'Cycling', 'Basic landcycling', 'Landcycling', 'Typecycling',
    }
    expected = dict(name=raw['name'], oracle_text=raw['oracle_text'],
                    mana_cost=raw.get('mana_cost', ''), type_line=raw['type_line'],
                    types=types, colors=raw['colors'], keywords=[],
                    power=int(raw['power']) if raw.get('power') is not None else None,
                    toughness=int(raw['toughness']) if raw.get('toughness') is not None else None,
                    printed_power=raw.get('power'), printed_toughness=raw.get('toughness'),
                    loyalty=int(raw['loyalty']) if raw.get('loyalty') is not None else None)
    assert set(expected) == set(FIELDS)
    return expected


def _assert_complete(card, name):
    raw = _raw(name)
    expected = _expected(name)
    assert {key: getattr(card, key) for key in FIELDS} == expected
    normalized = ScryfallSyncService._normalize_payload(
        raw, ScryfallSyncService._extract_remote_image_uri(raw))
    assert card.card_faces == json.loads(normalized['card_faces_json'])
    assert card.layout == raw['layout'] and card.selected_face_index is None
    assert card.characteristic_record['values'] == expected
    assert card.characteristic_record['physical'] == {
        **expected, 'card_faces': card.card_faces, 'layout': raw['layout'],
        'selected_face_index': None, 'image_uri': normalized['image_uri'],
    }


def _capture(monkeypatch, case):
    module_name, function_name, consumer, cid, name = case
    module = importlib.import_module('tests.' + module_name)
    real_factory = MatchFactory.from_decks
    result = {'births': []}

    def factory(*args, **kwargs):
        state = real_factory(*args, **kwargs)
        result['births'].append((deepcopy(args[:2]), deepcopy(state.cards)))
        return state

    def observe(state, *args, **kwargs):
        result['state'] = state
        result['card'] = state.cards[cid]
        raise ConsumerCaptured

    def observe_method(engine, state, *args, **kwargs):
        return observe(state, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(MatchFactory, 'from_decks', staticmethod(factory))
        if consumer == 'serialize_match_snapshot':
            patch.setattr(module, consumer, observe)
        else:
            patch.setattr(module.RulesEngine, consumer, observe_method)
        with pytest.raises(ConsumerCaptured):
            if cid == 'hekma-1':
                getattr(module, function_name)(False, 19)
            else:
                getattr(module, function_name)()
    assert result['card'].id == cid
    return result


@pytest.mark.parametrize('name', [
    'Island', 'Lonely Sandbar', 'Ash Barrens', 'Crypt Rats', 'Grizzly Bears',
    "Ajani's Pridemate", "Alhammarret's Archive", 'Boon Reflection', 'Protection of the Hekma',
    "Urza's Armor",
])
def test_complete_official_object_and_typed_expectation_are_pinned(name):
    assert _expected(name)['name'] == name


@pytest.mark.parametrize('case', CASES, ids=[case[3] for case in CASES])
def test_original_first_consumer_has_all_printed_and_retained_fields(monkeypatch, case):
    _assert_complete(_capture(monkeypatch, case)['card'], case[4])


@pytest.mark.parametrize('case', CASES, ids=[case[3] for case in CASES])
def test_real_factory_receives_full_object_before_stock_capture(monkeypatch, case):
    result = _capture(monkeypatch, case)
    raw = _raw(case[4])
    normalized = ScryfallSyncService._normalize_payload(
        raw, ScryfallSyncService._extract_remote_image_uri(raw))
    expected = {**raw, **normalized, 'colors': raw['colors'],
                'card_faces': json.loads(normalized['card_faces_json'])}
    observed = []
    for decks, cards in result['births']:
        entries = [entry for deck in decks for entry in deck if entry['card_name'] == raw['name']]
        for entry in entries:
            assert {key: entry[key] for key in expected} == expected
        observed.extend(card for card in cards.values() if card.name == raw['name'])
    assert observed
    for card in observed:
        _assert_complete(card, raw['name'])


@pytest.mark.parametrize('case', CASES, ids=[case[3] for case in CASES])
def test_printed_facts_survive_actual_snapshot(monkeypatch, case):
    state = _capture(monkeypatch, case)['state']
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    _assert_complete(restored.cards[case[3]], case[4])


@pytest.mark.parametrize('case', CASES, ids=[case[3] for case in CASES])
@pytest.mark.parametrize('field,value', [
    ('oracle_text', 'Invented ability.'), ('types', ['Planeswalker']),
    ('keywords', ['flying']), ('power', 99),
])
def test_coherent_card_and_record_corruption_cannot_satisfy_oracle(monkeypatch, case, field, value):
    card = _capture(monkeypatch, case)['card']
    _assert_complete(card, case[4])
    corrupted = deepcopy(card)
    setattr(corrupted, field, deepcopy(value))
    corrupted.characteristic_record['values'][field] = deepcopy(value)
    corrupted.characteristic_record['physical'][field] = deepcopy(value)
    with pytest.raises(AssertionError):
        _assert_complete(corrupted, case[4])
