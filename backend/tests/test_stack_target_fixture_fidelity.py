"""Observe the original counter tests' actual first-consumed card objects."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from tests.counter_native_frames import FACTS
import tests.test_stack_target_kinds as original


CASES = (
    (original.test_counterspell_targets_only_spells_and_does_not_move_trigger_source,
     'counter', 'Counterspell'),
    (original.test_stifle_targets_abilities_not_spells_or_their_sources,
     'stifle', 'Stifle'),
    (original.test_negate_only_counters_noncreature_spells, 'negate', 'Negate'),
    (original.test_negate_cast_path_counters_noncreature_spell, 'negate', 'Negate'),
)
CASE_IDS = ('counterspell', 'stifle', 'negate-targets', 'negate-cast')
RAW_SHA = '18ac1342277048fdbb79aa3b69c9727f9f9437e083d7c72defcbe0b4553feb0d'
PROOF_SHA = '2a3c89004304943067edd433281b4671172ce1fcc96eee5ce25bf69d12cf188d'
ROW_SHA = {
    'Counterspell': 'fe9513a8443f2f78ceb48e835c4e81d5b6d6eb995581683c73dfff9acecdb6b9',
    'Stifle': 'eccb451a0000ccd2d8209bdbb6e71bf456fb5925d0466f154cf0f19a3047bc11',
    'Negate': '90d37bb8ead523ea99cf40dff8eeb4187dd55f400a32ce4769c1001dc943b92c',
}


def capture(case, monkeypatch):
    body, card_id, name = case
    records = []
    real_hints = original.build_cast_hints
    real_moves = original.RulesEngine.legal_moves

    def observe(state):
        source = state.cards.get(card_id)
        if source is not None and source.name == name and not records:
            records.append({'card': source, 'before': deepcopy(vars(source))})

    def hints(state, source, *args, **kwargs):
        observe(state)
        return real_hints(state, source, *args, **kwargs)

    def moves(engine, state, *args, **kwargs):
        observe(state)
        return real_moves(engine, state, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(original, 'build_cast_hints', hints)
        patch.setattr(original.RulesEngine, 'legal_moves', moves)
        body()
    assert len(records) == 1
    return records[0]


@pytest.mark.parametrize('case', CASES, ids=CASE_IDS)
def test_first_real_counter_consumer_has_complete_printed_projection(case, monkeypatch):
    source = capture(case, monkeypatch)['before']
    raw = FACTS[case[2]]
    keys = ('name', 'oracle_text', 'mana_cost', 'type_line', 'colors', 'layout')
    assert {key: source[key] for key in keys} == {key: raw[key] for key in keys}
    assert source['card_faces'] == raw.get('card_faces', [])
    assert source['types'] == ['Instant'] and raw['type_line'] == 'Instant'
    assert source['keywords'] == raw['keywords'] == []
    assert (source['power'], source['toughness'], source['loyalty']) == (None, None, None)
    assert (source['printed_power'], source['printed_toughness']) == (None, None)
    assert source['selected_face_index'] is None and source['printed_characteristics'] == {}


@pytest.mark.parametrize('case', CASES, ids=CASE_IDS)
def test_original_source_runtime_identity_and_defaults_remain(case, monkeypatch):
    source = capture(case, monkeypatch)['before']
    assert (source['id'], source['owner'], source['controller'], source['zone']) == (
        case[1], 1, 1, original.Zone.HAND)
    assert source['instance_order'] == source['zone_change_sequence'] == 0
    assert source['summoning_sick'] is True and source['tapped'] is False
    assert source['counters'] == source['knowledge_snapshot'] == {}
    assert source['static_order'] == source['effect_timestamp'] == 0
    assert source['battlefield_incarnation'] is None


def test_actual_consumed_objects_and_raw_mutables_are_independent(monkeypatch):
    before = deepcopy(FACTS)
    first = capture(CASES[0], monkeypatch)['card']
    second = capture(CASES[0], monkeypatch)['card']
    assert first is not second
    # Explicit post-consumption protocol sentinels, never official/game input.
    first.types.append('Noncanonical independence sentinel')
    first.card_faces.append({'noncanonical_independence_sentinel': True})
    first.counters['independence-sentinel'] = 1
    assert second.types == ['Instant'] and second.card_faces == [] and second.counters == {}
    assert FACTS == before


def test_all_three_complete_official_rows_and_provenance_are_pinned():
    here = Path(__file__).parent / 'fixtures/counter_native_frames'
    raw_bytes = (here / 'canonical.json').read_bytes()
    proof_bytes = (here / 'provenance.json').read_bytes()
    assert hashlib.sha256(raw_bytes).hexdigest() == RAW_SHA
    assert hashlib.sha256(proof_bytes).hexdigest() == PROOF_SHA
    rows, proof = json.loads(raw_bytes), json.loads(proof_bytes)
    for name, digest in ROW_SHA.items():
        row = rows[name]
        encoded = json.dumps(row, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
        assert hashlib.sha256(encoded).hexdigest() == digest
        assert proof['cards'][name]['canonical_fullrow_sha256'] == digest
        assert row == FACTS[name] and row['object'] == 'card'
        assert row['id'] and row['oracle_id'] and row['legalities']
        assert row['rulings_uri'].startswith('https://api.scryfall.com/cards/')
