"""Root metadata follows registered set protocols; no gameplay qualification."""
from contextlib import contextmanager
import copy
import copyreg

import pytest

from game_state import copying
from game_state.state import CardInstance, Zone
from tests.test_root_metadata_copy_contract import state_with_metadata


@contextmanager
def registered_set(*, reducer=None, dispatcher=None):
    missing = object()
    registry = copyreg.dispatch_table
    dispatch = copy._deepcopy_dispatch
    before_reducer = registry.get(set, missing)
    before_dispatcher = dispatch.get(set, missing)
    try:
        if reducer is not None:
            copyreg.pickle(set, reducer)
        if dispatcher is not None:
            dispatch[set] = dispatcher
        yield
    finally:
        for table, before in ((registry, before_reducer), (dispatch, before_dispatcher)):
            if before is missing:
                table.pop(set, None)
            else:
                table[set] = before


def as_list(value):
    return list, (tuple(value),)


def test_registered_root_set_reducer_preserves_type_values_and_aliases():
    state = state_with_metadata()
    state.root_set = {2, 5}
    state.root_set_alias = state.root_set
    calls = []

    def reducer(value):
        calls.append(id(value))
        return as_list(value)

    with registered_set(reducer=reducer):
        reference = copy.deepcopy(state)
        expected_calls = list(calls)
        calls.clear()
        clone = copying.copy_match_state(state)
        assert type(clone.root_set) is list
        assert clone.root_set == reference.root_set
        assert clone.root_set is clone.root_set_alias
        assert calls == expected_calls and calls.count(id(state.root_set)) == 1
        clone.root_set.append(9)
        assert state.root_set == {2, 5}


@pytest.mark.parametrize('container', ['list', 'dict', 'tuple'])
def test_nested_root_containers_do_not_bypass_registered_sets(container):
    state = state_with_metadata()
    child = {2, 5}
    state.root_container = {'list': [child], 'dict': {'child': child},
                            'tuple': (child,)}[container]
    state.root_alias = child
    with registered_set(reducer=as_list):
        reference = copy.deepcopy(state)
        clone = copying.copy_match_state(state)
        actual = clone.root_container['child'] if container == 'dict' else clone.root_container[0]
        assert type(actual) is list
        assert actual is clone.root_alias and actual == reference.root_alias
        actual.append(9)
        assert child == {2, 5}


def test_registered_sets_keep_early_card_root_dictionary_cycles_complete():
    state = state_with_metadata()
    card = CardInstance('set-cycle-protocol', '', 1, 1, Zone.HAND)
    state.cards[card.id] = card
    card.backedges = [state.__dict__, state]
    state.self = state
    state.root_set = {2, 5}
    state.after_card_metadata = {'set_alias': state.root_set, 'root': state}
    with registered_set(reducer=as_list):
        clone = copying.copy_match_state(state)
        reference = copy.deepcopy(state)
        for result in (clone, reference):
            assert set(result.__dict__) == set(state.__dict__)
            assert result.cards[card.id].backedges[1] is result is result.self
            attrs = result.cards[card.id].backedges[0]
            assert attrs is not result.__dict__ and attrs['self'] is result
            assert attrs['after_card_metadata'] is result.after_card_metadata
            assert result.after_card_metadata['root'] is result
            assert result.root_set is result.after_card_metadata['set_alias']
            assert type(result.root_set) is list
        clone.root_set.append(9)
        assert state.root_set == {2, 5} and 9 not in reference.root_set


def test_supplied_set_memo_override_precedes_registered_reducer():
    state = state_with_metadata()
    state.root_set = {2, 5}
    replacement = ['explicit-memo']
    memo = {id(state.root_set): replacement}
    calls = []

    def reducer(value):
        calls.append(id(value))
        return as_list(value)

    with registered_set(reducer=reducer):
        clone = copying.copy_match_state(state, memo=memo)
        assert clone.root_set is replacement
        assert id(state.root_set) not in calls
        assert memo == {id(state.root_set): replacement}


@pytest.mark.parametrize('also_register_reducer', [False, True])
def test_actual_set_deepcopy_dispatch_has_stdlib_precedence(also_register_reducer):
    state = state_with_metadata()
    state.root_set = {2, 5}
    state.root_alias = state.root_set
    calls = []

    def dispatcher(value, memo):
        calls.append(id(value))
        return {'dispatch_values': list(value)}

    def forbidden_reducer(value):
        raise AssertionError('A registered dispatcher takes precedence')

    with registered_set(reducer=forbidden_reducer if also_register_reducer else None,
                        dispatcher=dispatcher):
        reference = copy.deepcopy(state)
        expected_calls = list(calls)
        calls.clear()
        clone = copying.copy_match_state(state)
        assert type(clone.root_set) is dict
        assert clone.root_set == reference.root_set
        assert clone.root_set is clone.root_alias
        assert calls == expected_calls
        clone.root_set['dispatch_values'].append(9)
        assert state.root_set == {2, 5}


def test_registered_reducer_results_are_independent_across_siblings():
    state = state_with_metadata()
    state.root_set = {2, 5}
    with registered_set(reducer=as_list):
        first, second = copying.copy_match_state(state), copying.copy_match_state(state)
        assert type(first.root_set) is type(second.root_set) is list
        assert first.root_set is not second.root_set
        first.root_set.append(9)
        assert 9 not in second.root_set and state.root_set == {2, 5}


def test_registered_reducer_error_identity_and_source_are_preserved():
    state = state_with_metadata()
    state.root_set = {2, 5}
    failure = RuntimeError('public registered-set protocol failure')

    def reducer(value):
        if value is state.root_set:
            raise failure
        return as_list(value)

    with registered_set(reducer=reducer):
        with pytest.raises(RuntimeError) as caught:
            copying.copy_match_state(state)
        assert caught.value is failure
        assert state.root_set == {2, 5}


def test_no_registration_keeps_normal_set_alias_and_independence():
    state = state_with_metadata()
    state.root_set = {2, 5}
    state.root_alias = state.root_set
    clone = copying.copy_match_state(state)
    assert type(clone.root_set) is set and clone.root_set is clone.root_alias
    assert clone.root_set is not state.root_set and clone.root_set == {2, 5}


def test_registered_root_set_does_not_expand_card_field_ablation_hook():
    state = state_with_metadata()
    state.root_set = {2, 5}
    card = CardInstance('set-card-ablation-protocol', '', 1, 1, Zone.HAND)
    card.metadata = {'card_values': [1]}
    state.cards[card.id] = card
    visited = []

    def fields(value, memo):
        visited.append(id(value))
        return copy.deepcopy(value, memo)

    with registered_set(reducer=as_list):
        clone = copying.copy_match_state(state, _field_copier=fields)
        assert id(card.metadata) in visited and id(state.root_set) not in visited
        assert type(clone.root_set) is list and clone.cards[card.id].metadata == card.metadata
