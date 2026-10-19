"""Nested card metadata retains deepcopy semantics without generic dispatch."""
from copy import deepcopy

import pytest

from game_state import copying


@pytest.mark.parametrize('root_kind', [list, dict])
def test_nested_exact_metadata_copies_without_generic_deepcopy(root_kind, monkeypatch):
    shared = [{'oracle': ['Full unchanged text'], 'flags': [True, None, 2]}]
    value = [shared, shared] if root_kind is list else {'first': shared, 'again': shared}
    original = deepcopy(value)
    fallback_calls = []

    def fallback(item, memo):
        fallback_calls.append(type(item))
        return deepcopy(item, memo)

    monkeypatch.setattr(copying, 'deepcopy', fallback)
    result = copying._copy_card_field(value, {})
    left, right = result if root_kind is list else result.values()
    assert result == original and result is not value
    assert left is right and left is not shared
    left[0]['oracle'].append('Trial-only text')
    assert value == original
    assert fallback_calls == [], 'Exact nested metadata still uses generic deepcopy'


@pytest.mark.parametrize('kind', [list, dict, set])
def test_flat_container_respects_memo_overrides_for_immutable_items(kind):
    source = 'explicit-memo-source-value'
    replacement = 'explicit-memo-replacement-value'
    value = {'key': source} if kind is dict else kind([source])
    memo = {id(source): replacement}
    result = copying._copy_card_field(value, memo)
    assert result == deepcopy(value, {id(source): replacement})
    assert memo[id(value)] is result and memo[id(source)] is replacement


def test_nested_cycles_and_tuple_fallback_share_one_memo():
    child = []
    value = {'child': child, 'tuple': (child,)}
    child.append(value)
    clone = copying._copy_card_field(value, {})
    assert clone is not value and clone['child'] is not child
    assert clone['child'][0] is clone
    assert clone['tuple'][0] is clone['child']


def test_custom_value_runs_before_dict_key_copy_and_can_update_memo():
    key = 'custom-hook-key'

    class MemoWriter:
        def __deepcopy__(self, memo):
            memo[id(key)] = 'replacement-key'
            return 17

    value = {key: MemoWriter()}
    assert copying._copy_card_field(value, {}) == deepcopy(value) == {'replacement-key': 17}


def test_nested_container_subclass_retains_custom_copy_and_parent_alias():
    class CustomList(list):
        def __deepcopy__(self, memo):
            result = CustomList()
            memo[id(self)] = result
            result.extend(deepcopy(list(self), memo))
            result.custom_copy_used = True
            return result

    shared = []
    value = {'shared': shared, 'custom': CustomList([shared])}
    clone = copying._copy_card_field(value, {})
    assert type(clone['custom']) is CustomList and clone['custom'].custom_copy_used
    assert clone['custom'][0] is clone['shared'] and clone['shared'] is not shared
    assert not hasattr(value['custom'], 'custom_copy_used')
