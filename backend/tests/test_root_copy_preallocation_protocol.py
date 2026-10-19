"""Additional root-allocation protocol controls; no played-game claims."""
from copy import deepcopy

import pytest

from game_state import copying
from game_state.state import CardInstance, MatchState, Zone
from tests.test_root_metadata_copy_contract import state_with_metadata


def test_card_custom_copy_sees_real_root_and_attribute_dictionary_memo():
    state = state_with_metadata()
    card = CardInstance('memo-protocol', '', 1, 1, Zone.HAND)
    state.cards[card.id] = card

    class ObserveMemo:
        def __deepcopy__(self, memo):
            return [memo.get(id(state)), memo.get(id(state.__dict__))]

    card.memo_observation = ObserveMemo()
    clone = copying.copy_match_state(state)
    reference = deepcopy(state)
    for result in (clone, reference):
        root, attrs = result.cards[card.id].memo_observation
        assert root is result
        assert attrs is not result.__dict__ and attrs['cards'] is result.cards


@pytest.mark.parametrize('history', [True, False])
def test_card_root_dict_backedges_keep_all_later_attributes_and_history(history):
    state = state_with_metadata()
    card = CardInstance('cycle-protocol', '', 1, 1, Zone.HAND)
    state.cards[card.id] = card
    card.backedges = [state.__dict__, state]
    state.self = state
    state.after_card_metadata = {'history': state.log, 'root': state}
    clone = copying.copy_match_state(state, include_history=history)
    assert set(clone.__dict__) == set(state.__dict__)
    assert clone.cards[card.id].backedges[1] is clone is clone.self
    attrs = clone.cards[card.id].backedges[0]
    assert attrs is not clone.__dict__ and attrs['self'] is clone
    assert attrs['after_card_metadata'] is clone.after_card_metadata
    assert clone.after_card_metadata['root'] is clone
    assert clone.after_card_metadata['history'] is clone.log
    assert clone.log == (state.log if history else [])
    clone.after_card_metadata['extra'] = [1]
    assert 'extra' not in state.after_card_metadata


def test_custom_root_subclass_newargs_uses_real_constructor_fallback():
    events = []

    class Root(MatchState):
        def __new__(cls, marker):
            events.append(marker)
            obj = object.__new__(cls)
            obj.constructed_marker = marker
            return obj

        def __getnewargs__(self):
            return ('real-newargs',)

    state = object.__new__(Root)
    state.__dict__.update(state_with_metadata().__dict__)
    reference = deepcopy(state)
    wanted = list(events)
    events.clear()
    clone = copying.copy_match_state(state)
    assert events == wanted == ['real-newargs']
    assert clone.constructed_marker == reference.constructed_marker == 'real-newargs'
    assert clone.dynamic == state.dynamic


def test_non_string_dynamic_attribute_keys_and_nested_key_aliases_are_preserved():
    state = state_with_metadata()

    class Key:
        pass

    key = Key()
    key.note = [1]
    state.__dict__[key] = ['value']
    state.key_alias = key
    clone = copying.copy_match_state(state)
    assert clone.key_alias in clone.__dict__ and clone.key_alias is not key
    assert clone.__dict__[clone.key_alias] == ['value']
    clone.key_alias.note.append(2)
    assert key.note == [1] and state.__dict__[key] == ['value']


def test_explicit_root_override_keeps_existing_card_field_ablation_contract():
    state = state_with_metadata()
    card = CardInstance('override-protocol', '', 1, 1, Zone.HAND)
    card.metadata = {'independent': [1]}
    state.cards[card.id] = card
    replacement = object()
    memo = {id(state): replacement}
    visited = []

    def fields(value, actual_memo):
        visited.append(actual_memo.get(id(state)))
        return deepcopy(value, actual_memo)

    assert copying.copy_match_state(state, memo=memo, _field_copier=fields) is replacement
    assert visited and all(value is replacement for value in visited)
    assert memo == {id(state): replacement}
