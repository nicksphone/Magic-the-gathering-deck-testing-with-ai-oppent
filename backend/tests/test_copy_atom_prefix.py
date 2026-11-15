"""Fresh internal memo prefix controls, not native end-to-end speed claims."""
import builtins
from copy import deepcopy
import sys

import pytest

from game_state import copying
from game_state.state import CardInstance, MatchState, Zone


def test_foreign_card_setter_cannot_precede_atomic_prefix(monkeypatch):
    atom = ''.join(['foreign-card-setter-', 'later-atom'])
    state = position([atom])
    original = CardInstance.__setattr__
    def setter(card, name, value):
        if name == '__dict__':
            memo = sys._getframe(1).f_locals.get('memo')
            if type(memo) is dict:
                memo[builtins.id(atom)] = 'setter replacement'
        return original(card, name, value)
    monkeypatch.setattr(CardInstance, '__setattr__', setter)
    fast = payload(copying.copy_match_state(state))
    slow = payload(copying.copy_match_state(state, memo={}))
    assert fast == slow == ['setter replacement']


def position(value):
    card = object.__new__(CardInstance)
    card.__dict__ = {'metadata': value}
    state = object.__new__(MatchState)
    state.__dict__ = {'log': [], 'cards': {'card': card}}
    return state


def payload(state):
    return state.cards['card'].metadata


def test_fresh_internal_memo_reduces_atom_id_checks(monkeypatch):
    value = {f'prefix-key-{i}': [f'prefix-value-{i}', i + 10000] for i in range(512)}
    state = position(value)
    atoms = {builtins.id(x) for k, row in value.items() for x in [k, *row]}
    calls = []
    def counted(item):
        identity = builtins.id(item)
        if identity in atoms:
            calls.append(identity)
        return identity
    monkeypatch.setattr(copying, 'id', counted, raising=False)
    slow = copying.copy_match_state(state, memo={})
    slow_count = len(calls)
    calls.clear()
    fast = copying.copy_match_state(state)
    assert payload(fast) == payload(slow) == value
    assert slow_count >= len(atoms)
    assert len(calls) == 0


@pytest.mark.parametrize('nest', ['list', 'dict', 'tuple', 'custom-key'])
def test_hook_memo_override_affects_later_sibling_and_dictionary_key(nest):
    atom = ''.join(['later-', nest, '-atom'])
    class Hook:
        def __deepcopy__(self, memo):
            memo[builtins.id(atom)] = 'replacement'
            return 17
    class Key:
        def __deepcopy__(self, memo):
            memo[builtins.id(atom)] = 'replacement'
            return 'key'
    first = {'list': [Hook()], 'dict': {atom: Hook()},
             'tuple': (Hook(),), 'custom-key': {Key(): 1}}[nest]
    state = position([first, atom, {atom: atom}, [atom]])
    slow = payload(copying.copy_match_state(state, memo={}))
    fast = payload(copying.copy_match_state(state))
    assert fast == slow
    assert fast[1:] == ['replacement', {'replacement': 'replacement'}, ['replacement']]
    if nest == 'dict':
        assert fast[0] == {'replacement': 17}


def test_unknown_metaclass_hash_cannot_leave_direct_atoms_enabled():
    atom = ''.join(['metaclass-', 'later-atom'])
    class Meta(type):
        def __hash__(cls):
            memo = sys._getframe(1).f_locals.get('memo')
            if type(memo) is dict:
                memo[builtins.id(atom)] = 'metaclass replacement'
            return type.__hash__(cls)
    class Value(metaclass=Meta):
        def __deepcopy__(self, memo):
            return 31
    state = position([Value(), atom, {atom: atom}])
    fast = payload(copying.copy_match_state(state))
    slow = payload(copying.copy_match_state(state, memo={}))
    assert fast == slow == [31, 'metaclass replacement', {'metaclass replacement': 'metaclass replacement'}]


def test_alias_cycles_and_both_preallocated_root_backedges():
    shared = []
    state = position({'left': shared, 'right': shared})
    shared.extend([shared, state, state.__dict__])
    clone = copying.copy_match_state(state)
    value = payload(clone)
    assert value['left'] is value['right'] and value['left'] is not shared
    assert value['left'][0] is value['left']
    assert value['left'][1] is clone
    attrs = value['left'][2]
    assert attrs is not clone.__dict__ and attrs['cards'] is clone.cards


def test_supplied_memo_atomic_override_and_default_helper_stay_slow():
    atom = ''.join(['explicit-', 'memo-atom'])
    state = position([atom, {atom: atom}])
    memo = {builtins.id(atom): 'explicit replacement'}
    clone = copying.copy_match_state(state, memo=memo)
    assert payload(clone) == ['explicit replacement', {'explicit replacement': 'explicit replacement'}]
    assert memo == {builtins.id(atom): 'explicit replacement'}
    assert copying._copy_card_field([atom], dict(memo)) == ['explicit replacement']


def test_custom_field_copier_keeps_two_argument_protocol():
    atom = ''.join(['custom-', 'field-atom'])
    state = position([atom])
    calls = []
    def fields(value, memo):
        calls.append(value)
        memo[builtins.id(atom)] = 'custom replacement'
        return copying._copy_card_field(value, memo)
    assert payload(copying.copy_match_state(state, _field_copier=fields)) == ['custom replacement']
    assert calls


def test_monkeypatched_helper_keeps_two_argument_protocol(monkeypatch):
    state = position([['nested']])
    original = copying._copy_card_field
    calls = []
    def fields(value, memo):
        calls.append(value)
        return original(value, memo)
    monkeypatch.setattr(copying, '_copy_card_field', fields)
    assert payload(copying.copy_match_state(state)) == [['nested']]
    assert calls


def test_custom_keep_alive_can_register_later_atomic_override(monkeypatch):
    atom = ''.join(['keep-alive-', 'atom'])
    original = copying._keep_alive
    def keep(value, memo):
        memo[builtins.id(atom)] = 'keep replacement'
        return original(value, memo)
    monkeypatch.setattr(copying, '_keep_alive', keep)
    state = position([[], atom, {atom: atom}])
    assert payload(copying.copy_match_state(state)) == payload(copying.copy_match_state(state, memo={}))
    assert payload(copying.copy_match_state(state))[1:] == ['keep replacement', {'keep replacement': 'keep replacement'}]


def test_nested_reentrant_copy_cannot_reactivate_parent_scope():
    atom = ''.join(['reentrant-', 'atom'])
    class Hook:
        def __deepcopy__(self, memo):
            copying.copy_match_state(position(['independent inner copy']))
            memo[builtins.id(atom)] = 'outer replacement'
            return 7
    state = position([Hook(), atom, {atom: atom}])
    assert payload(copying.copy_match_state(state)) == [7, 'outer replacement', {'outer replacement': 'outer replacement'}]


def test_ineligible_prefix_preserves_later_helper_replacement(monkeypatch):
    marker = []
    state = position([[]])
    state.after = marker
    original_field, original_keep = copying._copy_card_field, copying._keep_alive
    def fields(value, memo):
        return 'later helper replacement' if value is marker else original_field(value, memo)
    def keep(value, memo):
        monkeypatch.setattr(copying, '_copy_card_field', fields)
        return original_keep(value, memo)
    monkeypatch.setattr(copying, '_keep_alive', keep)
    assert copying.copy_match_state(state).after == 'later helper replacement'


def test_zone_key_hash_override_affects_later_atom(monkeypatch):
    atom = ''.join(['zone-key-', 'later-atom'])
    original = Zone.__hash__
    def foreign_hash(value):
        memo = sys._getframe(1).f_locals.get('memo')
        if type(memo) is dict:
            memo[builtins.id(atom)] = 'zone key replacement'
        return original(value)
    monkeypatch.setattr(Zone, '__hash__', foreign_hash)
    state = position([{Zone.BATTLEFIELD: []}, atom])
    fast = payload(copying.copy_match_state(state))
    slow = payload(copying.copy_match_state(state, memo={}))
    assert fast == slow
    assert fast[1] == 'zone key replacement'


def test_top_level_card_fallback_retains_entry_helper_but_nested_calls_are_dynamic(monkeypatch):
    original = copying._copy_card_field
    def replacement(value, memo):
        return ['patched'] if type(value) is list and not value else original(value, memo)
    class Hook:
        def __deepcopy__(self, memo):
            monkeypatch.setattr(copying, '_copy_card_field', replacement)
            return 17
    def scene():
        state = position([Hook(), []])
        state.cards['card'].later = []
        return state
    fast = copying.copy_match_state(scene())
    monkeypatch.setattr(copying, '_copy_card_field', original)
    slow = copying.copy_match_state(scene(), memo={})
    assert payload(fast) == payload(slow) == [17, ['patched']]
    assert fast.cards['card'].later == slow.cards['card'].later == []


def test_foreign_top_level_card_key_latches_before_later_field():
    atom = ''.join(['card-attribute-key-', 'atom'])
    class Key:
        def __hash__(self):
            memo = sys._getframe(1).f_locals.get('memo')
            if type(memo) is dict:
                memo[builtins.id(atom)] = 'card key replacement'
            return object.__hash__(self)
    key = Key()
    def scene():
        state = position([])
        state.cards['card'].__dict__ = {key: [], 'later': [atom]}
        return state
    fast = copying.copy_match_state(scene())
    slow = copying.copy_match_state(scene(), memo={})
    assert fast.cards['card'].later == slow.cards['card'].later == ['card key replacement']


def test_cards_subclass_values_setup_memo_write_prevents_later_prefix():
    atom = ''.join(['cards-values-', 'later-atom'])
    calls = []
    class Cards(dict):
        def values(self):
            memo = sys._getframe(1).f_locals.get('memo')
            if type(memo) is dict:
                calls.append('values')
                memo[builtins.id(atom)] = 'setup replacement'
            return super().values()
    def scene():
        state = position([atom])
        state.cards = Cards(state.cards)
        return state
    fast = payload(copying.copy_match_state(scene()))
    fast_calls = list(calls)
    calls.clear()
    slow = payload(copying.copy_match_state(scene(), memo={}))
    assert fast == slow == ['setup replacement']
    assert fast_calls == calls == ['values']


def test_root_cards_property_setup_does_not_enable_prefix(monkeypatch):
    atom = ''.join(['cards-property-', 'atom'])
    state = position([atom])
    calls = []
    def cards(root):
        memo = sys._getframe(1).f_locals.get('memo')
        if type(memo) is dict:
            calls.append('cards')
            memo[builtins.id(atom)] = 'property replacement'
        return object.__getattribute__(root, '__dict__')['cards']
    monkeypatch.setattr(MatchState, 'cards', property(cards), raising=False)
    fast = payload(copying.copy_match_state(state))
    fast_calls = list(calls)
    calls.clear()
    slow = payload(copying.copy_match_state(state, memo={}))
    assert fast == slow == ['property replacement']
    assert fast_calls == calls == ['cards']


def test_card_attribute_access_hook_setup_does_not_enable_prefix(monkeypatch):
    atom = ''.join(['card-access-', 'atom'])
    state = position([atom])
    original = CardInstance.__getattribute__
    calls = []
    def access(card, name):
        memo = sys._getframe(1).f_locals.get('memo')
        if name == '__dict__' and type(memo) is dict:
            calls.append(name)
            memo[builtins.id(atom)] = 'access replacement'
        return original(card, name)
    monkeypatch.setattr(CardInstance, '__getattribute__', access)
    fast = payload(copying.copy_match_state(state))
    fast_calls = list(calls)
    calls.clear()
    slow = payload(copying.copy_match_state(state, memo={}))
    assert fast == slow == ['access replacement']
    assert fast_calls == calls


def test_native_prefix_reduces_standard_keep_alive_calls_without_patching_helper():
    state = position({f'keeper-{i}': [[i, str(i)]] for i in range(512)})
    code = copying._keep_alive.__code__
    def observed(**kwargs):
        calls = []
        def profile(frame, event, arg):
            if event == 'call' and frame.f_code is code:
                calls.append(frame.f_code)
        previous = sys.getprofile()
        sys.setprofile(profile)
        try:
            result = copying.copy_match_state(state, **kwargs)
        finally:
            sys.setprofile(previous)
        return result, len(calls)
    slow, slow_calls = observed(memo={})
    fast, fast_calls = observed()
    assert payload(fast) == payload(slow) == payload(state)
    assert slow_calls >= 1024
    assert fast_calls * 4 < slow_calls


@pytest.mark.parametrize('prior_containers', [False, True])
def test_keep_alive_bucket_stays_lazy_and_retains_input_order(prior_containers):
    observed = []
    class Hook:
        def __deepcopy__(self, memo):
            key = builtins.id(memo)
            observed.append((key in memo, [builtins.id(v) for v in memo.get(key, [])]))
            return 17
    prefix = [[1], {'nested': [2]}] if prior_containers else []
    state = position(prefix + [Hook(), [3]])
    fast = payload(copying.copy_match_state(state))
    fast_events = list(observed)
    observed.clear()
    slow = payload(copying.copy_match_state(state, memo={}))
    assert fast == slow
    assert fast_events == observed
    assert observed[0][0] is prior_containers


@pytest.mark.parametrize('error_type', [KeyError, ValueError])
def test_foreign_bucket_append_keeps_standard_exception_semantics(error_type):
    error = error_type('same bucket error')
    events = []
    class Bucket:
        def append(self, value):
            events.append(builtins.id(value))
            raise error
    class Hook:
        def __deepcopy__(self, memo):
            memo[builtins.id(memo)] = Bucket()
            return 17
    state = position([[], Hook(), ['after']])
    def observed(**kwargs):
        if error_type is ValueError:
            with pytest.raises(ValueError) as caught:
                copying.copy_match_state(state, **kwargs)
            assert caught.value is error
            return None
        return payload(copying.copy_match_state(state, **kwargs))
    fast = observed()
    fast_events = list(events)
    events.clear()
    slow = observed(memo={})
    assert fast == slow
    assert fast_events == events and len(events) == 1


def test_actual_planning_copy_uses_canonical_explicit_field_prefix():
    from ai import pending_effects
    state = position({f'planning-{i}': [[i, str(i)]] for i in range(512)})
    state.log = ['Diagnostic history must be omitted']
    code = copying._keep_alive.__code__
    def observed(**kwargs):
        calls = []
        def profile(frame, event, arg):
            if event == 'call' and frame.f_code is code:
                calls.append(frame.f_code)
        previous = sys.getprofile()
        sys.setprofile(profile)
        try:
            result = pending_effects.planning_copy(state, **kwargs)
        finally:
            sys.setprofile(previous)
        return result, len(calls)
    assert pending_effects._copy_card_field is copying._native_copy_bindings[2]
    slow, slow_calls = observed(memo={})
    fast, fast_calls = observed()
    assert payload(fast) == payload(slow) == payload(state)
    assert fast.log == slow.log == [] and state.log == ['Diagnostic history must be omitted']
    assert slow_calls >= 1024
    assert fast_calls * 4 < slow_calls


def test_planning_copy_foreign_field_wrapper_retains_original_callback_route(monkeypatch):
    from ai import pending_effects
    original = copying._copy_card_field
    calls = []
    def wrapper(value, memo):
        calls.append(builtins.id(value))
        return original(value, memo)
    monkeypatch.setattr(pending_effects, '_copy_card_field', wrapper)
    state = position([[], {'field': [1, 2]}])
    fast = pending_effects.planning_copy(state)
    fast_calls = list(calls)
    calls.clear()
    slow = pending_effects.planning_copy(state, memo={})
    assert payload(fast) == payload(slow)
    assert fast_calls == calls and calls


@pytest.mark.parametrize('api', ['copy_match_state', 'planning_copy'])
def test_explicit_native_alias_with_replaced_global_helper_keeps_captured_fallback(monkeypatch, api):
    from ai import pending_effects
    original = copying._copy_card_field
    calls = []
    def replacement(value, memo):
        calls.append(builtins.id(value))
        return ['patched'] if type(value) is list and not value else original(value, memo)
    monkeypatch.setattr(copying, '_copy_card_field', replacement)
    state = position([[]])
    state.cards['card'].later = []
    def observed(**kwargs):
        if api == 'planning_copy':
            assert pending_effects._copy_card_field is original
            return pending_effects.planning_copy(state, **kwargs)
        return copying.copy_match_state(state, include_history=False, _field_copier=original, **kwargs)
    fast = observed()
    fast_calls = list(calls)
    calls.clear()
    slow = observed(memo={})
    assert payload(fast) == payload(slow) == [['patched']]
    assert fast.cards['card'].later == slow.cards['card'].later == []
    assert fast_calls == calls
