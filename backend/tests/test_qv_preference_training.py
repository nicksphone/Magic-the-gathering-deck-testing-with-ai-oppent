"""Preference admission is pure; real CPU learning is checked separately."""
import builtins
from copy import deepcopy
import inspect

import pytest

from scripts import train_qv_preferences as trainer
from tests.test_learned_qv import contract, number, tree


def preference():
    return {'state': number(1), 'preferred': number(1),
            'alternatives': [number(-1)], 'return': 1.0}


def options():
    return {'contract': contract(), 'dataset_sha256': 'b' * 64,
            'split_sha256': 'c' * 64, 'seed': 17, 'epochs': 1, 'seconds': 30}


def test_valid_preferences_are_read_only_and_preserve_actual_returns():
    rows = [preference()]
    before = deepcopy(rows)
    trainer.validate_preferences(rows, contract=contract())
    assert rows == before
    rows[0]['return'] = -1.0
    trainer.validate_preferences(rows, contract=contract())


@pytest.mark.parametrize('change', ['empty', 'tuple', 'unknown-field', 'no-alternative',
    'too-many-alternatives', 'duplicate-preferred', 'duplicate-alternative',
    'wrong-feature-epoch', 'preferred-bank', 'alternative-bank', 'wrong-return',
    'nonfinite-return', 'bool-return', 'bad-features'])
def test_malformed_preferences_fail_before_torch_import(change, monkeypatch):
    rows = [preference()]
    row = rows[0]
    if change == 'empty':
        rows = []
    elif change == 'tuple':
        rows = tuple(rows)
    elif change == 'unknown-field':
        row['opposing_hand'] = ['FORBIDDEN']
    elif change == 'no-alternative':
        row['alternatives'] = []
    elif change == 'too-many-alternatives':
        row['alternatives'] = [number(-i-1) for i in range(9)]
    elif change == 'duplicate-preferred':
        row['alternatives'].append(deepcopy(row['preferred']))
    elif change == 'duplicate-alternative':
        row['alternatives'] *= 2
    elif change == 'wrong-feature-epoch':
        row['preferred']['version'] = 'mtg.features.v2'
    elif change in {'preferred-bank', 'alternative-bank'}:
        pack = row['preferred'] if change == 'preferred-bank' else row['alternatives'][0]
        pack['entities'] = [{'kind': 'number', 'value': 2}]
    elif change == 'wrong-return':
        row['return'] = 2.0
    elif change == 'nonfinite-return':
        row['return'] = float('nan')
    elif change == 'bool-return':
        row['return'] = True
    else:
        row['state']['root'] = {'kind': 'number', 'value': float('inf')}
    original = builtins.__import__

    def importing(name, *args, **kwargs):
        assert name.split('.')[0] != 'torch', 'Invalid input imported Torch'
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', importing)
    with pytest.raises(ValueError):
        trainer.train_preferences(rows, **options())


@pytest.mark.parametrize('key,value', [('seed', True), ('seed', -1), ('epochs', 0),
    ('epochs', 1001), ('seconds', 0), ('seconds', 3601), ('learning_rate', True),
    ('learning_rate', float('nan')), ('temperature', 0), ('temperature', True),
    ('temperature', float('inf')), ('value_weight', -1), ('value_weight', True),
    ('value_weight', 2), ('progress', False), ('dataset_sha256', 'not-a-hash'),
    ('split_sha256', 'A' * 64)])
def test_invalid_configuration_fails_before_torch_import(key, value, monkeypatch):
    kwargs = {**options(), key: value}
    original = builtins.__import__

    def importing(name, *args, **kwargs):
        assert name.split('.')[0] != 'torch', 'Invalid configuration imported Torch'
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', importing)
    with pytest.raises(ValueError):
        trainer.train_preferences([preference()], **kwargs)


def test_training_contract_must_match_the_registered_feature_epoch():
    invalid = {**contract(), 'feature_schema_sha256': 'f' * 64}
    with pytest.raises(ValueError):
        trainer.validate_preferences([preference()], contract=invalid)


def test_callback_and_objective_parameters_are_explicit_optional_keywords():
    signature = inspect.signature(trainer.train_preferences)
    for name, value in [('temperature', .25), ('value_weight', .25), ('progress', None)]:
        parameter = signature.parameters[name]
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
        assert parameter.default == value


def test_distinct_references_with_identical_public_facts_cannot_be_negative_labels():
    bank = [{'kind': 'number', 'value': 2}, {'kind': 'number', 'value': 2}]
    row = preference()
    for pack in [row['state'], row['preferred'], *row['alternatives']]:
        pack['entities'] = deepcopy(bank)
    row['preferred']['root'] = {'kind': 'ref', 'index': 0}
    row['alternatives'][0]['root'] = {'kind': 'ref', 'index': 1}
    with pytest.raises(ValueError, match='distinct|equivalent'):
        trainer.validate_preferences([row], contract=contract())


def test_semantic_action_keys_respect_maps_sets_list_order_and_multiplicity():
    one = {'kind': 'number', 'value': 1}
    two = {'kind': 'number', 'value': 2}
    key = trainer.semantic_action_key
    assert key(number(1)) == key(number(1.0))
    assert key(tree({'kind': 'set', 'items': [one, two]})) == key(
        tree({'kind': 'set', 'items': [two, one]}))
    assert key(tree({'kind': 'map', 'items': [[one, two], [two, one]]})) == key(
        tree({'kind': 'map', 'items': [[two, one], [one, two]]}))
    assert key(tree({'kind': 'list', 'items': [one, two]})) != key(
        tree({'kind': 'list', 'items': [two, one]}))
    assert key(tree({'kind': 'set', 'items': [one]})) != key(
        tree({'kind': 'set', 'items': [one, one]}))


def test_equivalent_reference_keys_do_not_collapse_different_observable_facts():
    bank = [{'kind': 'number', 'value': 2}, {'kind': 'number', 'value': 3}]
    left = {'version': 'mtg.features.v1', 'entities': bank,
            'root': {'kind': 'ref', 'index': 0}}
    right = {**left, 'root': {'kind': 'ref', 'index': 1}}
    assert trainer.semantic_action_key(left) != trainer.semantic_action_key(right)
