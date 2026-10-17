"""Observe original named-positive fixtures before their actual rules consumer."""
from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path

import pytest

from card_data.sync import ScryfallSyncService
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, _infer_keywords
from rules_engine.card_types import printed_card_types
from rules_engine.copiable_values import FIELDS


FIXTURES = Path(__file__).parent / 'fixtures'
SOURCES_SHA = '9739e307c7839509b60d2aa0ea58c61bd969c5ccfdb058385c0f36cdff1d8923'
CASES = (
    ('test_variable_life_cost_audit', 'test_toxic_deluge_does_not_infer_an_unrelated_draw_effect', 'build_spell_spec', 'deluge', 'Toxic Deluge', 1),
    ('test_variable_life_cost_audit', 'test_variable_life_payment_trigger_is_above_spell', 'checked_action', 'font', 'Font of Agonies', 1),
    ('test_variable_life_cost_audit', 'test_life_total_lock_allows_zero_x_but_not_positive_x', 'build_cast_hints', 'lock', 'Platinum Emperion', 1),
    ('test_variable_life_cost_audit', 'test_temporary_pt_modifier_does_not_follow_bounced_creature', 'checked_action', 'spider', 'Giant Spider', 2),
    ('test_additional_costs', 'test_sacrifice_additional_cost_respects_die_replacement', 'take_action', 'rep', 'Rest in Peace', 1),
)


class ConsumerCaptured(BaseException):
    pass


def _raw(name):
    data = (FIXTURES / 'life_cost_022758/SOURCES.json').read_bytes()
    assert hashlib.sha256(data).hexdigest() == SOURCES_SHA
    record = json.loads(data)['cards'][name]
    data = (FIXTURES / record['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == record['sha256']
    for proof in record['provenance']:
        assert hashlib.sha256((FIXTURES / proof['file']).read_bytes()).hexdigest() == proof['sha256']
    if record['line'] is not None:
        data = data.splitlines()[record['line'] - 1]
    raw = json.loads(data)
    assert hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest() == record['object_sha256']
    assert raw['object'] == 'card' and raw['name'] == name
    assert raw['id'] == record['id'] and raw['oracle_id'] == record['oracle_id']
    assert len(raw) == record['fields'] >= 60
    return raw


def _normalized(name):
    raw = _raw(name)
    normalized = ScryfallSyncService._normalize_payload(
        raw, ScryfallSyncService._extract_remote_image_uri(raw))
    return raw, normalized


def _capture(monkeypatch, case):
    module_name, function_name, consumer, cid, name, seat = case
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

    def observe_action(engine, state, *args, **kwargs):
        return observe_consumer(state, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(MatchFactory, 'from_decks', staticmethod(observe_factory))
        if consumer == 'take_action':
            patch.setattr(module.RulesEngine, consumer, observe_action)
        else:
            patch.setattr(module, consumer, observe_consumer)
        with pytest.raises(ConsumerCaptured):
            getattr(module, function_name)()
    assert captured['card'].id == cid
    assert captured['card'].owner == captured['card'].controller == seat
    return captured


def _assert_complete(card, name):
    raw, normalized = _normalized(name)
    expected = {
        'name': raw['name'], 'oracle_text': raw['oracle_text'],
        'mana_cost': raw['mana_cost'], 'type_line': raw['type_line'],
        'types': printed_card_types(raw['type_line']),
        'power': int(raw['power']) if raw.get('power') is not None else None,
        'toughness': int(raw['toughness']) if raw.get('toughness') is not None else None,
        'printed_power': raw.get('power'), 'printed_toughness': raw.get('toughness'),
        'loyalty': None, 'colors': raw['colors'], 'keywords': _infer_keywords(raw['oracle_text']),
    }
    assert set(expected) == set(FIELDS)
    assert {key: getattr(card, key) for key in FIELDS} == expected
    assert card.card_faces == json.loads(normalized['card_faces_json'])
    assert card.layout == raw['layout'] and card.selected_face_index is None
    assert card.characteristic_record['physical'] == {
        **expected, 'card_faces': card.card_faces, 'layout': raw['layout'],
        'selected_face_index': None, 'image_uri': normalized['image_uri'],
    }
    assert card.characteristic_record['values'] == expected


@pytest.mark.parametrize('case', CASES, ids=[case[3] for case in CASES])
def test_existing_complete_raw_is_unmodified_and_pinned(case):
    raw = _raw(case[4])
    assert raw['layout'] == 'normal'


@pytest.mark.parametrize('case', CASES, ids=[case[3] for case in CASES])
def test_original_first_consumer_receives_complete_printed_facts(monkeypatch, case):
    captured = _capture(monkeypatch, case)
    _assert_complete(captured['card'], case[4])


@pytest.mark.parametrize('case', CASES, ids=[case[3] for case in CASES])
def test_actual_factory_birth_has_all_official_fields_before_consumer(monkeypatch, case):
    captured = _capture(monkeypatch, case)
    name = case[4]
    raw, normalized = _normalized(name)
    matches = [(decks, cards) for decks, cards in captured['births']
               if any(entry['card_name'] == name for deck in decks for entry in deck)]
    assert len(matches) == 1
    decks, cards = matches[0]
    entry = next(entry for deck in decks for entry in deck if entry['card_name'] == name)
    expected = {**raw, **normalized, 'colors': raw['colors'],
                'card_faces': json.loads(normalized['card_faces_json'])}
    assert {key: entry[key] for key in expected} == expected
    assert len(cards) == 8
    for card in cards.values():
        _assert_complete(card, name)


@pytest.mark.parametrize('case', CASES[:4], ids=[case[3] for case in CASES[:4]])
def test_full_printed_facts_survive_real_snapshot(monkeypatch, case):
    captured = _capture(monkeypatch, case)
    restored = deserialize_match_snapshot(serialize_match_snapshot(captured['state']))
    _assert_complete(restored.cards[case[3]], case[4])


@pytest.mark.parametrize('case', CASES, ids=[case[3] for case in CASES])
@pytest.mark.parametrize('field', ['oracle_text', 'mana_cost', 'colors'])
def test_fidelity_rejects_actual_printed_field_corruption(monkeypatch, case, field):
    captured = _capture(monkeypatch, case)
    _assert_complete(captured['card'], case[4])
    changed = deepcopy(captured['card'])
    setattr(changed, field, ['invented-color'] if field == 'colors' else 'Invented field.')
    with pytest.raises(AssertionError):
        _assert_complete(changed, case[4])
