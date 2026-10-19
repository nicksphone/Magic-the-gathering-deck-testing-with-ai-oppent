"""Capture the original fixtures at their actual first rules consumer."""
from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path
import re

import pytest

from card_data.sync import ScryfallSyncService
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory
from rules_engine.copiable_values import FIELDS


FIXTURES = Path(__file__).parent / 'fixtures'
SEED_SHA = '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732'
PROVENANCE_SHA = 'f15047f1ecb06fdaa985a58537d01b6497683637d7caf88db518dea469fc1ca2'
SOURCES = {
    'Brazen Borrower // Petty Theft': (13, '5f3cdc8aaaca6372f702eaf6aa4995be9052ee320c0405f048203a6f3799ae76'),
    'Supreme Verdict': (96, 'fb33914ee6ec01b341ca9d60ee60fc9cda93c538ee36c97a776832bb81d17a3d'),
}
CASES = (
    ('test_bounce_rules', 'test_bounce_inference_exposes_nonland_permanent_targets', 'build_cast_hints', 'petty-theft', 'Brazen Borrower // Petty Theft'),
    ('test_bounce_rules', 'test_bounce_ability_spec_is_not_marked_as_oracle_fallback', 'build_ability_spec', 'petty-theft-spec', 'Brazen Borrower // Petty Theft'),
    ('test_bounce_rules', 'test_bounce_rejects_card_outside_current_target_candidates', 'build_cast_hints', 'petty-theft-invalid', 'Brazen Borrower // Petty Theft'),
    ('test_priority_stack', 'test_counter_spell_respects_cannot_be_countered_and_keeps_target_on_stack', 'counter_spell', 'verdict-stack', 'Supreme Verdict'),
)


class ConsumerCaptured(BaseException):
    pass


def _raw(name):
    seed = (FIXTURES / 'knowledge_profiles/seed155-scryfall.jsonl').read_bytes()
    assert hashlib.sha256(seed).hexdigest() == SEED_SHA
    proof = (FIXTURES / 'knowledge_profiles/PROVENANCE.json').read_bytes()
    assert hashlib.sha256(proof).hexdigest() == PROVENANCE_SHA
    number, digest = SOURCES[name]
    line = seed.splitlines()[number - 1]
    assert hashlib.sha256(line).hexdigest() == digest
    raw = json.loads(line)
    assert raw['object'] == 'card' and raw['name'] == name
    assert len(raw) >= 60 and raw['id'] and raw['oracle_id']
    return raw


def _normalized(name):
    raw = _raw(name)
    normalized = ScryfallSyncService._normalize_payload(
        raw, ScryfallSyncService._extract_remote_image_uri(raw))
    return raw, normalized


def _capture(monkeypatch, case):
    module_name, function_name, consumer, cid, name = case
    module = importlib.import_module('tests.' + module_name)
    actual_factory = MatchFactory.from_decks
    captured = {'births': []}

    def observe_factory(*args, **kwargs):
        state = actual_factory(*args, **kwargs)
        captured['births'].append((deepcopy(args[:2]), deepcopy(state.cards)))
        return state

    def observe_consumer(state, *args, **kwargs):
        captured['state'] = state
        captured['card'] = state.cards[cid]
        raise ConsumerCaptured

    with monkeypatch.context() as patch:
        patch.setattr(MatchFactory, 'from_decks', staticmethod(observe_factory))
        patch.setattr(module, consumer, observe_consumer)
        with pytest.raises(ConsumerCaptured):
            getattr(module, function_name)()
    assert captured['card'].id == cid
    assert captured['card'].owner == captured['card'].controller == 1
    return captured


def _expected_typed_source(data, colors):
    # This finite source oracle does not call the materializer, Factory, or
    # native selected-face projection to manufacture its expected typed view.
    header = data['type_line'].split('//', 1)[0].split('\u2014', 1)[0]
    types = [word for word in header.split() if word in {
        'Artifact', 'Battle', 'Creature', 'Enchantment', 'Instant', 'Kindred',
        'Land', 'Planeswalker', 'Sorcery',
    }]
    if 'keywords' in data:
        declared = {word.casefold() for word in data['keywords']}
        assert declared <= {'flash', 'flying'}
    else:
        declared = {line.strip().casefold() for line in data['oracle_text'].splitlines()}
    keywords = [word for word in ('flash', 'flying') if word in declared]

    def number(field):
        value = data.get(field)
        return int(value) if value is not None and re.fullmatch(r'[+-]?[0-9]+', str(value)) else None

    return {
        **{key: data[key] for key in ('name', 'oracle_text', 'mana_cost', 'type_line')},
        'types': types, 'keywords': keywords, 'colors': colors,
        'power': number('power'), 'toughness': number('toughness'),
        'loyalty': number('loyalty'),
        'printed_power': str(data['power']) if data.get('power') is not None else None,
        'printed_toughness': str(data['toughness']) if data.get('toughness') is not None else None,
    }


def _assert_complete(card, name):
    raw, normalized = _normalized(name)
    faces = json.loads(normalized['card_faces_json'])
    assert card.layout == raw['layout']
    assert card.card_faces == faces
    physical = card.characteristic_record['physical']
    for key in ('name', 'type_line', 'oracle_text', 'mana_cost'):
        assert physical[key] == normalized[key]
    assert physical['colors'] == raw['colors']
    assert physical['card_faces'] == faces
    assert physical['layout'] == raw['layout']
    assert physical['selected_face_index'] is None
    expected = faces[1] if faces else normalized
    for key in ('name', 'type_line', 'oracle_text', 'mana_cost'):
        assert getattr(card, key) == expected[key]
    assert card.colors == (expected['colors'] if faces else raw['colors'])
    assert card.selected_face_index == (1 if faces else None)
    assert card.characteristic_record['values'] == {key: getattr(card, key) for key in FIELDS}
    expected_physical = _expected_typed_source({**raw, **normalized}, raw['colors'])
    assert {key: physical[key] for key in FIELDS} == expected_physical
    expected_selected = (_expected_typed_source(faces[1], faces[1]['colors'])
                         if faces else expected_physical)
    assert {key: getattr(card, key) for key in FIELDS} == expected_selected
    assert card.characteristic_record['values'] == expected_selected


@pytest.mark.parametrize('name', SOURCES)
def test_reused_sources_are_complete_official_parents(name):
    raw = _raw(name)
    if raw['layout'] == 'adventure':
        assert [face['name'] for face in raw['card_faces']] == ['Brazen Borrower', 'Petty Theft']
        assert raw['card_faces'][1]['type_line'] == 'Instant \u2014 Adventure'


@pytest.mark.parametrize('case', CASES, ids=[case[3] for case in CASES])
def test_original_first_consumer_receives_complete_printed_facts(monkeypatch, case):
    captured = _capture(monkeypatch, case)
    _assert_complete(captured['card'], case[4])


@pytest.mark.parametrize('case', CASES, ids=[case[3] for case in CASES])
def test_real_factory_captures_full_parent_before_the_consumer(monkeypatch, case):
    captured = _capture(monkeypatch, case)
    name = case[4]
    raw, normalized = _normalized(name)
    matches = [(decks, cards) for decks, cards in captured['births']
               if any(entry['card_name'] == name for deck in decks for entry in deck)]
    assert len(matches) == 1
    decks, cards = matches[0]
    entry = next(entry for deck in decks for entry in deck if entry['card_name'] == name)
    expected_entry = {**raw, **normalized, 'colors': raw['colors'],
                      'card_faces': json.loads(normalized['card_faces_json'])}
    assert {key: entry[key] for key in expected_entry} == expected_entry
    assert entry['oracle_text'] == normalized['oracle_text']
    assert entry['card_faces'] == json.loads(normalized['card_faces_json'])
    assert cards and all(card.characteristic_record['physical']['name'] == name for card in cards.values()), [card.characteristic_record['physical']['name'] for card in cards.values()]
    assert all(card.selected_face_index is None for card in cards.values())


@pytest.mark.parametrize('case', CASES[:3], ids=[case[3] for case in CASES[:3]])
def test_selected_adventure_and_full_parent_survive_actual_snapshot(monkeypatch, case):
    captured = _capture(monkeypatch, case)
    restored = deserialize_match_snapshot(serialize_match_snapshot(captured['state']))
    _assert_complete(restored.cards[case[3]], case[4])


@pytest.mark.parametrize('case', CASES, ids=[case[3] for case in CASES])
@pytest.mark.parametrize('field', ['oracle_text', 'card_faces'])
def test_consumer_fidelity_rejects_actual_field_corruption(monkeypatch, case, field):
    captured = _capture(monkeypatch, case)
    _assert_complete(captured['card'], case[4])
    changed = deepcopy(captured['card'])
    setattr(changed, field, 'Invented body.' if field == 'oracle_text' else [{'name': 'Invented face'}])
    with pytest.raises(AssertionError):
        _assert_complete(changed, case[4])


TYPED_CORRUPTIONS = {
    'types': ['Creature'], 'keywords': ['flash', 'flying'],
    'power': 3, 'toughness': 1, 'printed_power': '3', 'printed_toughness': '1',
    'loyalty': 4,
}
PHYSICAL_CORRUPTIONS = {
    'types': ['Sorcery', 'Creature'], 'keywords': ['menace'],
    'power': 99, 'toughness': 98, 'printed_power': '99', 'printed_toughness': '98',
    'loyalty': 99,
}


@pytest.mark.parametrize('case', CASES, ids=[case[3] for case in CASES])
@pytest.mark.parametrize('field', TYPED_CORRUPTIONS)
def test_coherent_current_and_retained_typed_corruption_rejects(monkeypatch, case, field):
    captured = _capture(monkeypatch, case)
    _assert_complete(captured['card'], case[4])
    changed = deepcopy(captured['card'])
    value = TYPED_CORRUPTIONS[field]
    setattr(changed, field, deepcopy(value))
    changed.characteristic_record['values'][field] = deepcopy(value)
    with pytest.raises(AssertionError):
        _assert_complete(changed, case[4])


@pytest.mark.parametrize('case', CASES, ids=[case[3] for case in CASES])
@pytest.mark.parametrize('field', PHYSICAL_CORRUPTIONS)
def test_independent_physical_typed_corruption_rejects(monkeypatch, case, field):
    captured = _capture(monkeypatch, case)
    _assert_complete(captured['card'], case[4])
    changed = deepcopy(captured['card'])
    changed.characteristic_record['physical'][field] = deepcopy(PHYSICAL_CORRUPTIONS[field])
    with pytest.raises(AssertionError):
        _assert_complete(changed, case[4])


@pytest.mark.parametrize('case', CASES[:3], ids=[case[3] for case in CASES[:3]])
def test_complete_borrower_creature_traits_cannot_leak_to_adventure(monkeypatch, case):
    captured = _capture(monkeypatch, case)
    _assert_complete(captured['card'], case[4])
    changed = deepcopy(captured['card'])
    front = _raw(case[4])['card_faces'][0]
    values = {'types': ['Creature'], 'keywords': ['flash', 'flying'],
              'power': int(front['power']), 'toughness': int(front['toughness']),
              'printed_power': front['power'], 'printed_toughness': front['toughness']}
    for field, value in values.items():
        setattr(changed, field, deepcopy(value))
        changed.characteristic_record['values'][field] = deepcopy(value)
    with pytest.raises(AssertionError):
        _assert_complete(changed, case[4])


@pytest.mark.parametrize('case', CASES, ids=[case[3] for case in CASES])
def test_missing_noncreature_printed_stats_are_not_printed_zero(monkeypatch, case):
    captured = _capture(monkeypatch, case)
    raw = _raw(case[4])
    selected = raw['card_faces'][1] if raw.get('card_faces') else raw
    assert selected.get('power') is selected.get('toughness') is None
    assert captured['card'].printed_power is captured['card'].printed_toughness is None
