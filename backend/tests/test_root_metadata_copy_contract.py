"""Public copy-protocol controls, not gameplay or native-speed acceptance."""
from copy import deepcopy
import copy
import copyreg
import pickle
import random

import pytest

from game_state import copying
from game_state.state import CardInstance, MatchFactory, MatchState, PlayerState, Zone


def state_with_metadata():
    state = MatchState('root-copy-protocol',
                       {seat: PlayerState(seat, str(seat)) for seat in (1, 2)}, {}, [])
    state.rng = random.Random(193)
    state.log = ['Retained protocol history']
    shared = [{'values': [1, 2], 'flags': {True, None}}]
    state.dynamic = {'left': shared, 'right': shared, 'tuple': (shared,)}
    state.log_alias = state.log
    return state


def assert_root_values(actual, expected):
    values = []
    for root in (actual, expected):
        row = dict(root.__dict__)
        if type(row.get('rng')) is random.Random:
            row['rng'] = row['rng'].getstate()
        values.append(row)
    assert values[0] == values[1]


def canonical120():
    from card_data.sync import ScryfallSyncService
    from tests.canonical_positive_fixtures import raw_card
    entries = []
    for name in ('Grizzly Bears', 'Island', 'Lightning Bolt'):
        raw = raw_card(name)
        row = ScryfallSyncService._normalize_payload(raw, '/card-images/public-copy-fixture.jpg')
        entries.append({**row, 'card_name': raw['name'], 'quantity': 20})
    return MatchFactory.from_decks(entries, entries, seed=193, game_id='canonical-copy-120')


def test_exact_root_metadata_avoids_stdlib_per_atomic_dict_leaf(monkeypatch):
    """A real operation count, with no global dispatch-table changes."""
    state = state_with_metadata()
    state.atomic_metadata = {f'root-key-{i}': f'root-value-{i}' for i in range(128)}
    targets = {id(v) for pair in state.atomic_metadata.items() for v in pair}
    calls = []
    original = copy._deepcopy_dict.__defaults__
    delegate = original[0]

    def observed(value, memo):
        if id(value) in targets:
            calls.append(id(value))
        return delegate(value, memo)

    # Only this controlled stdlib protocol counts calls; restoration is automatic.
    monkeypatch.setattr(copy._deepcopy_dict, '__defaults__', (observed,))
    clone = copying.copy_match_state(state)
    assert clone.atomic_metadata == state.atomic_metadata
    assert clone.atomic_metadata is not state.atomic_metadata
    assert calls == [], 'Ordinary root metadata still invokes stdlib deepcopy per atomic leaf'


@pytest.mark.parametrize('history', [True, False])
def test_all_values_rng_history_and_mutation_match_reference(history):
    state = state_with_metadata()
    before = pickle.dumps(state, protocol=5)
    expected = deepcopy(state)
    if not history:
        expected.log = []
        expected.log_alias = expected.log
    clone = copying.copy_match_state(state, include_history=history)
    assert_root_values(clone, expected)
    assert clone.rng.getstate() == state.rng.getstate() and clone.rng is not state.rng
    assert clone.log_alias is clone.log
    left = clone.dynamic['left']
    assert left is clone.dynamic['right'] is clone.dynamic['tuple'][0]
    assert left is not state.dynamic['left']
    left[0]['values'].append(3)
    clone.rng.random()
    assert pickle.dumps(state, protocol=5) == before


def test_root_self_and_attribute_dictionary_cycles_match_stdlib_update_semantics():
    state = state_with_metadata()
    state.self = state
    state.attributes = state.__dict__
    state.dynamic['root'] = state
    state.dynamic['attributes'] = state.__dict__
    clone = copying.copy_match_state(state)
    reference = deepcopy(state)
    for result in (clone, reference):
        assert result.self is result and result.dynamic['root'] is result
        assert result.attributes is result.dynamic['attributes']
        assert result.attributes is not result.__dict__
        assert result.attributes['self'] is result
        assert result.attributes['attributes'] is result.attributes
        assert set(result.__dict__) == set(state.__dict__)


@pytest.mark.parametrize('attrs_first', [False, True])
def test_card_metadata_root_and_attribute_cycles_are_complete(attrs_first):
    state = state_with_metadata()
    card = CardInstance('protocol-card', '', 1, 1, Zone.HAND)
    state.cards[card.id] = card
    state.self = state
    pairs = [('root', state), ('attributes', state.__dict__)]
    card.dynamic = dict(reversed(pairs) if attrs_first else pairs)
    clone = copying.copy_match_state(state)
    assert set(clone.__dict__) == set(state.__dict__)
    assert clone.self is clone
    assert clone.cards[card.id].dynamic['root'] is clone
    assert clone.cards[card.id].dynamic['attributes']['self'] is clone
    assert clone.cards[card.id].dynamic is not card.dynamic


@pytest.mark.parametrize('override', ['root', 'attributes', 'atomic', 'key'])
def test_supplied_memo_overrides_and_caller_dictionary_are_retained(override):
    state = state_with_metadata()
    key = 'root-owned-atomic-key'
    value = 'root-owned-atomic-value'
    state.extra = {key: value}
    replacement = {'root': object(), 'attributes': {'explicit': [1]},
                   'atomic': 'replacement-value', 'key': 'replacement-key'}[override]
    source = {'root': state, 'attributes': state.__dict__,
              'atomic': value, 'key': key}[override]
    memo = {id(source): replacement}
    before = dict(memo)
    expected = deepcopy(state, dict(memo))
    clone = copying.copy_match_state(state, memo=memo)
    assert memo == before
    if override == 'root':
        assert clone is replacement is expected
    elif override == 'attributes':
        assert clone.__dict__ == expected.__dict__ == replacement
        assert clone.explicit is replacement['explicit']
    else:
        assert clone.extra == expected.extra


def test_custom_memo_observations_are_not_added_by_root_path():
    events = []

    class Memo(dict):
        def keys(self):
            events.append('keys')
            return super().keys()

        def __getitem__(self, key):
            events.append(key)
            return super().__getitem__(key)

    state = state_with_metadata()
    memo = Memo({id(state.log): ['supplied']})
    copying.copy_match_state(state, memo=memo)
    observed = list(events)
    events.clear()
    dict(memo)
    assert events == observed and list(memo.values()) == [['supplied']]


@pytest.mark.parametrize('hook', ['__deepcopy__', '__getstate__', '__reduce__', '__reduce_ex__',
                                 '__getnewargs__', '__getnewargs_ex__'])
def test_exact_root_custom_hooks_retain_stdlib_protocol(hook, monkeypatch):
    state = state_with_metadata()
    seen = []
    if hook == '__deepcopy__':
        def custom(self, memo):
            seen.append(hook)
            return {'custom': hook}
    elif hook == '__getstate__':
        def custom(self):
            seen.append(hook)
            return {**self.__dict__, 'custom': hook}
    elif hook in ('__reduce__', '__reduce_ex__'):
        def custom(self, *args):
            seen.append(hook)
            return (dict, (), None, None, iter([('custom', hook)]))
    elif hook == '__getnewargs__':
        def custom(self):
            seen.append(hook)
            return ()
    else:
        def custom(self):
            seen.append(hook)
            return (), {}
    monkeypatch.setattr(MatchState, hook, custom, raising=False)
    expected = deepcopy(state)
    expected_events = list(seen)
    seen.clear()
    result = copying.copy_match_state(state)
    assert seen == expected_events
    if isinstance(expected, dict):
        assert result == expected
    else:
        assert_root_values(result, expected)


def test_dynamic_hook_fallback_does_not_suppress_or_add_observations(monkeypatch):
    state = state_with_metadata()
    calls = []

    def dynamic(self, name):
        calls.append(name)
        raise AttributeError(name)

    monkeypatch.setattr(MatchState, '__getattr__', dynamic, raising=False)
    expected = deepcopy(state)
    wanted = list(calls)
    calls.clear()
    clone = copying.copy_match_state(state)
    assert calls == wanted
    assert_root_values(clone, expected)


def test_instance_deepcopy_hook_and_copyreg_are_not_bypassed(monkeypatch):
    state = state_with_metadata()
    state.__deepcopy__ = lambda memo: {'instance_hook': True}
    assert copying.copy_match_state(state) == deepcopy(state) == {'instance_hook': True}
    del state.__deepcopy__
    monkeypatch.setitem(copyreg.dispatch_table, MatchState,
                        lambda value: (dict, (), None, None, iter([('registered', 1)])))
    assert copying.copy_match_state(state) == deepcopy(state) == {'registered': 1}


def test_subclass_and_root_dict_subclass_fallback():
    class Root(MatchState):
        def __deepcopy__(self, memo):
            return {'subclass': True}

    state = Root('subclass', {}, {}, [])
    assert copying.copy_match_state(state) == deepcopy(state) == {'subclass': True}

    class Attributes(dict):
        def __deepcopy__(self, memo):
            return {'custom_attributes': [1]}

    state = state_with_metadata()
    state.__dict__ = Attributes(state.__dict__)
    assert copying.copy_match_state(state).__dict__ == deepcopy(state).__dict__


def test_nested_hooks_see_the_root_memo_and_run_before_key_copy():
    state = state_with_metadata()
    key = 'custom-root-key'
    events = []

    class Hook:
        def __deepcopy__(self, memo):
            events.append(id(state) in memo)
            memo[id(key)] = 'hook-changed-key'
            return 17

    state.unknown = {key: Hook()}
    expected = deepcopy(state)
    wanted = list(events)
    events.clear()
    clone = copying.copy_match_state(state)
    assert events == wanted == [True]
    assert clone.unknown == expected.unknown == {'hook-changed-key': 17}


def test_card_only_ablation_is_not_applied_to_root_metadata():
    state = state_with_metadata()
    card = CardInstance('protocol-card', '', 1, 1, Zone.HAND)
    card.dynamic = {'card': [1]}
    state.cards[card.id] = card
    visited = []

    def fields(value, memo):
        visited.append(id(value))
        return deepcopy(value, memo)

    clone = copying.copy_match_state(state, _field_copier=fields)
    assert id(card.dynamic) in visited and id(state.dynamic) not in visited
    assert clone.dynamic == state.dynamic and clone.cards[card.id].dynamic == card.dynamic


def test_complete_canonical120_values_and_siblings_keep_factory_capture():
    state = canonical120()
    before = pickle.dumps(state, protocol=5)
    clone, sibling = copying.copy_match_state(state), copying.copy_match_state(state)
    assert len(state.cards) == len(clone.cards) == 120
    assert clone.sideboard_facts == state.sideboard_facts
    assert clone.rng.getstate() == state.rng.getstate()
    assert pickle.dumps(clone, protocol=5) == pickle.dumps(deepcopy(state), protocol=5)
    card = next(iter(clone.cards.values()))
    card.counters['protocol'] = 1
    clone.starting_decks[1][0]['quantity'] = 999
    assert pickle.dumps(state, protocol=5) == before
    assert pickle.dumps(sibling, protocol=5) == pickle.dumps(deepcopy(state), protocol=5)
