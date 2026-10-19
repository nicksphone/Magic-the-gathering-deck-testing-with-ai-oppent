"""Observe original consumers; full expected prints come directly from pinned RAW."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.copiable_values import values as copiable_values
from tests import test_conditional_counter_rules as conditional
from tests import test_life_lock_boon_stack_diagnostic as paid


TESTS = Path(__file__).parent
SOURCE_BYTES = (TESTS / 'fixtures/counter_life_t57/SOURCES.json').read_bytes()
assert hashlib.sha256(SOURCE_BYTES).hexdigest() == 'e1d3c8cf033ee82426a357251453f55c09faa78c3266300c368f0286e44ba0bb'
SOURCES = json.loads(SOURCE_BYTES)['objects']


def _raw(name):
    source = SOURCES[name]
    data = (TESTS / source['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == source['file_sha256']
    for proof in source['provenance']:
        assert hashlib.sha256((TESTS / proof['file']).read_bytes()).hexdigest() == proof['sha256']
    raw = json.loads(data.splitlines()[source['line'] - 1] if source['line'] else data)
    assert hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False).encode()).hexdigest() == source['object_sha256']
    assert (raw['object'], raw['name'], raw['id'], raw['oracle_id'], raw['layout']) == (
        'card', name, source['id'], source['oracle_id'], 'normal')
    assert {'legalities', 'set', 'uri', 'scryfall_uri', 'image_uris',
            'oracle_text', 'type_line', 'mana_cost', 'colors', 'keywords'} <= raw.keys()
    return raw


def _assert_print(card, name, cid, owner, zone):
    raw = _raw(name)
    expected = {
        'name': raw['name'], 'mana_cost': raw['mana_cost'],
        'type_line': raw['type_line'], 'types': raw['type_line'].split('\u2014', 1)[0].split(),
        'power': int(raw['power']) if raw.get('power') is not None else None,
        'toughness': int(raw['toughness']) if raw.get('toughness') is not None else None,
        'printed_power': raw.get('power'), 'printed_toughness': raw.get('toughness'),
        'loyalty': int(raw['loyalty']) if raw.get('loyalty') is not None else None,
        'oracle_text': raw['oracle_text'], 'keywords': deepcopy(raw['keywords']),
        'colors': deepcopy(raw['colors']),
    }
    physical = {**deepcopy(expected), 'card_faces': deepcopy(raw.get('card_faces') or []),
                'layout': raw['layout'], 'selected_face_index': None,
                'image_uri': SOURCES[name]['display_uri']}
    assert (card.id, card.owner, card.controller, card.zone) == (cid, owner, owner, zone)
    assert {key: deepcopy(getattr(card, key)) for key in physical} == physical
    assert (card.summoning_sick, card.instance_order, card.zone_change_sequence,
            card.tapped, card.counters) == (True, 0, 0, False, {})
    assert card.printed_characteristics == {} and card.knowledge_snapshot == {}
    record = {'version': 1, 'physical': physical, 'values': expected}
    assert card.characteristic_record == record
    copied = copiable_values(card)
    assert copied == expected
    copied['colors'].append('R')
    assert card.characteristic_record == record and card.colors == raw['colors']


def test_original_spell_pierce_inference_and_hints_receive_full_print(monkeypatch):
    real_infer, real_hints = conditional.infer_effect_from_oracle, conditional.inspect_target_hints
    seen = []

    def infer(state, card, *args, **kwargs):
        _assert_print(card, 'Spell Pierce', 'pierce', 1, Zone.HAND)
        seen.append('infer')
        return real_infer(state, card, *args, **kwargs)

    def hints(state, card, *args, **kwargs):
        _assert_print(card, 'Spell Pierce', 'pierce', 1, Zone.HAND)
        seen.append('hints')
        return real_hints(state, card, *args, **kwargs)

    monkeypatch.setattr(conditional, 'infer_effect_from_oracle', infer)
    monkeypatch.setattr(conditional, 'inspect_target_hints', hints)
    conditional.test_spell_pierce_is_structured_and_filters_creature_spells()
    assert seen == ['infer', 'hints']


def _observe_first_paid_cast(monkeypatch, seat, creature):
    real = paid.checked_action
    seen = []
    cid, name = ('bear', 'Grizzly Bears') if creature else ('bolt', 'Lightning Bolt')

    def forward(state, engine, actor, action, *args, **kwargs):
        if not seen:
            assert (actor, action['type'], action['card_id']) == (3-seat, 'cast_spell', cid)
            _assert_print(state.cards['font'], 'Font of Agonies', 'font', seat, Zone.BATTLEFIELD)
            _assert_print(state.cards['boon'], 'Withering Boon', 'boon', seat, Zone.HAND)
            _assert_print(state.cards[cid], name, cid, 3-seat, Zone.HAND)
            before = serialize_match_snapshot(state)
            result = real(state, engine, actor, action, *args, **kwargs)
            assert serialize_match_snapshot(state) == before
            seen.append(cid)
            return result
        return real(state, engine, actor, action, *args, **kwargs)

    monkeypatch.setattr(paid, 'checked_action', forward)
    return seen


@pytest.mark.parametrize('seat', [1, 2])
def test_original_paid_boon_consumer_receives_full_font_boon_and_bears(monkeypatch, seat):
    seen = _observe_first_paid_cast(monkeypatch, seat, True)
    paid.test_paid_creature_counter_life_cost_font_and_snapshot_both_seats(seat)
    assert seen == ['bear']


def test_original_paid_noncreature_negative_receives_full_bolt_without_faking_outcome(monkeypatch):
    seen = _observe_first_paid_cast(monkeypatch, 1, False)
    paid.test_genuine_paid_noncreature_spell_remains_invalid_and_root_atomic()
    assert seen == ['bolt']
