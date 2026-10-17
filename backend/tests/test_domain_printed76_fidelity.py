"""Whole legacy consumers must receive complete, genuinely born printed facts."""
from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path

import pytest

from game_state.state import MatchFactory, _infer_keywords, _infer_power, _infer_toughness
from rules_engine.card_types import printed_card_types
from rules_engine.copiable_values import FIELDS


SEED = Path(__file__).parent / 'fixtures/knowledge_profiles/seed155-scryfall.jsonl'
SEED_SHA = '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732'
WIRE = SEED.read_bytes()
assert hashlib.sha256(WIRE).hexdigest() == SEED_SHA
ROWS = {row['name']: row for row in map(json.loads, WIRE.splitlines())}
CASES = [
    ('test_domain_costs', 'test_domain_discount_is_oracle_driven_and_does_not_change_mana_value'),
    ('test_domain_costs', 'test_domain_discount_applies_to_real_cast_payment'),
    ('test_domain_costs', 'test_domain_discount_combines_with_opponent_spell_tax'),
    ('test_domain_tokens', 'test_domain_counts_distinct_subtypes_not_names_or_opponent_lands'),
    ('test_domain_tokens', 'test_domain_token_count_is_evaluated_when_effect_resolves'),
    ('test_domain_tokens', 'test_activated_only_spell_text_does_not_trigger_name_guess'),
    ('test_domain_tokens', 'test_herd_migration_cast_creates_domain_tokens_not_search_effect'),
]
LAND_ROLES = {'forest': 'Forest', 'garden': "Jetmir's Garden", 'tower': "Raffine's Tower",
              'duplicate': 'Forest', 'name-only': 'Waterlogged Grove', 'opponent': 'Plains'}


def printed(card, name):
    raw = ROWS[name]
    kinds = printed_card_types(raw['type_line'])
    expected = {'name': name, 'mana_cost': raw['mana_cost'], 'oracle_text': raw['oracle_text'],
                'type_line': raw['type_line'], 'types': kinds,
                'power': _infer_power(name, raw.get('power'), kinds),
                'toughness': _infer_toughness(name, raw.get('toughness'), kinds),
                'printed_power': raw.get('power'), 'printed_toughness': raw.get('toughness'),
                'loyalty': int(raw['loyalty']) if raw.get('loyalty') is not None else None,
                'keywords': _infer_keywords(raw['oracle_text']), 'colors': raw['colors']}
    assert {field: getattr(card, field) for field in FIELDS} == expected
    assert card.layout == raw['layout'] and card.card_faces == raw.get('card_faces', [])
    assert card.selected_face_index is None and card.printed_characteristics == {}
    record = card.characteristic_record
    assert type(record) is dict and record['version'] == 1
    assert record['values'] == expected
    assert {field: record['physical'][field] for field in FIELDS} == expected


@pytest.mark.parametrize('module,function', CASES)
def test_original_Factory_inputs_and_born_stock_are_full_RAW(monkeypatch, module, function):
    original = MatchFactory.from_decks
    seen = []
    def inspect(left, right, *args, **kwargs):
        for deck in (left, right):
            for row in deck:
                raw = ROWS[row['card_name']]
                assert {k: v for k, v in row.items() if k not in {'card_name', 'quantity'}} == raw
        state = original(left, right, *args, **kwargs)
        for card in state.cards.values():
            printed(card, card.name)
        assert state.starting_decks == {1: left, 2: right} and state.sideboard_facts
        seen.append(True)
        return state
    monkeypatch.setattr(MatchFactory, 'from_decks', inspect)
    getattr(importlib.import_module('tests.' + module), function)()
    assert seen == [True]


@pytest.mark.parametrize('module,function', CASES[:3] + [CASES[4], CASES[6]])
def test_original_spell_first_consumer_receives_complete_RAW(monkeypatch, module, function):
    target = importlib.import_module('tests.' + module)
    seen = []
    if module == 'test_domain_costs' and function != CASES[1][1]:
        original = target.can_pay_with_pool_and_lands
        def inspect(state, seat, cost, *args, **kwargs):
            card = next(c for c in state.cards.values() if c.name == 'Leyline Binding')
            printed(card, 'Leyline Binding')
            seen.append(True)
            return original(state, seat, cost, *args, **kwargs)
        monkeypatch.setattr(target, 'can_pay_with_pool_and_lands', inspect)
    elif function == CASES[4][1]:
        original = target.infer_effect_from_oracle
        def inspect(state, card, *args, **kwargs):
            if card.name == 'Herd Migration':
                printed(card, card.name)
                seen.append(True)
            return original(state, card, *args, **kwargs)
        monkeypatch.setattr(target, 'infer_effect_from_oracle', inspect)
    else:
        original = target.RulesEngine.take_action
        def inspect(engine, state, seat, action, *args, **kwargs):
            printed(state.cards[action['card_id']],
                    'Leyline Binding' if module == 'test_domain_costs' else 'Herd Migration')
            seen.append(True)
            return original(engine, state, seat, action, *args, **kwargs)
        monkeypatch.setattr(target.RulesEngine, 'take_action', inspect)
    getattr(target, function)()
    assert seen


def test_original_domain_count_consumes_true_full_land_roles(monkeypatch):
    from tests import test_domain_tokens as target
    original = target.basic_land_type_count
    seen = []
    def inspect(state, seat):
        for cid, name in LAND_ROLES.items():
            printed(state.cards[cid], name)
        seen.append(seat)
        return original(state, seat)
    monkeypatch.setattr(target, 'basic_land_type_count', inspect)
    target.test_domain_counts_distinct_subtypes_not_names_or_opponent_lands()
    assert seen == [1, 2]
