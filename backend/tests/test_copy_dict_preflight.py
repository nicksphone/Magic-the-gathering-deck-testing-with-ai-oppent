"""Dict preflight operation counts and copy semantics; no timing thresholds."""
import cProfile
from copy import deepcopy
import sys
from types import CodeType

from game_state import copying


def test_dict_preflight_does_not_enter_helper_local_generator_frames():
    shared = ['unchanged metadata']
    value = {'left': shared, 'right': shared}
    helper = copying._copy_card_field
    generators = tuple(code for code in helper.__code__.co_consts
                       if type(code) is CodeType and code.co_name == '<genexpr>')
    monitor = sys.monitoring
    before = {tool: (monitor.get_tool(tool), monitor.get_events(tool)) for tool in (2, 3, 4)}
    assert before[2] == (None, 0), 'Operation-count control needs an unoccupied profiler tool'
    profile_before, trace_before = sys.getprofile(), sys.gettrace()
    profiler = cProfile.Profile(subcalls=False, builtins=False)
    try:
        clone = profiler.runcall(helper, value, {})
    finally:
        assert {tool: (monitor.get_tool(tool), monitor.get_events(tool)) for tool in (2, 3, 4)} == before
        assert sys.getprofile() is profile_before and sys.gettrace() is trace_before
    entries = profiler.getstats()
    assert any(entry.code is helper.__code__ and entry.callcount > 0 for entry in entries)
    assert clone == deepcopy(value) and clone['left'] is clone['right']
    assert clone['left'] is not shared and value['left'] is shared
    # No sets occur in this input: helper-local generator entries are dict preflight.
    count = sum(entry.callcount for entry in entries
                if any(entry.code is code for code in generators))
    assert count == 0, 'Exact dict preflight still enters generator frames'


def test_late_unsupported_key_falls_back_before_memo_or_value_effects(monkeypatch):
    effects = []

    class Value:
        def __deepcopy__(self, memo):
            effects.append('value copied')
            return 17

    shared = []
    replacement = ['explicit memo replacement']
    value = {'first': Value(), ('late', 1): shared, 'again': shared}
    initial = {id(shared): replacement}
    expected = deepcopy(value, dict(initial))
    effects.clear()
    fallback_memos = []

    def observed(item, memo):
        if item is value:
            fallback_memos.append(dict(memo))
        return deepcopy(item, memo)

    monkeypatch.setattr(copying, 'deepcopy', observed)
    clone = copying._copy_card_field(value, dict(initial))
    assert fallback_memos == [initial], 'Fallback must precede allocation and value copying'
    assert effects == ['value copied']
    assert clone == expected and clone[('late', 1)] is clone['again'] is replacement
    assert shared == []


def test_supplied_memo_replacements_include_keys_values_and_falsey_roots():
    key = 'preflight-original-key'
    item = 'preflight-original-value'
    shared = []
    replacement = ['caller-owned replacement']
    value = {key: item, 'left': shared, 'right': shared}
    supplied = {id(key): 'replacement-key', id(item): None, id(shared): replacement}
    memo = dict(supplied)
    clone = copying._copy_card_field(value, memo)
    assert clone == deepcopy(value, dict(supplied))
    assert clone['replacement-key'] is None
    assert clone['left'] is clone['right'] is replacement
    assert all(memo[identity] is original for identity, original in supplied.items())
    assert value[key] is item and shared == []
    for root_replacement in (None, False, 0, [], {}, object()):
        memo = {id(value): root_replacement}
        before = dict(memo)
        assert copying._copy_card_field(value, memo) is root_replacement
        assert memo == before


def test_alias_cycles_tuple_fallback_and_empty_dict_stay_detached():
    shared = []
    value = {'left': shared, 'right': shared, 'tuple': (shared,)}
    shared.append(value)
    clone = copying._copy_card_field(value, {})
    reference = deepcopy(value)
    for copied in (clone, reference):
        assert copied is not value
        assert copied['left'] is copied['right'] is copied['tuple'][0]
        assert copied['left'] is not shared and copied['left'][0] is copied
    clone['left'].append('clone only')
    assert len(shared) == len(reference['left']) == 1 and shared[0] is value
    empty = {}
    memo = {}
    copied = copying._copy_card_field(empty, memo)
    assert copied == empty and copied is not empty and memo[id(empty)] is copied


def test_value_copy_can_replace_key_memo_before_key_is_copied():
    key = 'preflight-value-before-key'
    effects = []

    class Value:
        def __deepcopy__(self, memo):
            effects.append('value copied')
            memo[id(key)] = 'hook-replaced-key'
            return 23

    value = {key: Value()}
    expected = deepcopy(value)
    effects.clear()
    clone = copying._copy_card_field(value, {})
    assert clone == expected == {'hook-replaced-key': 23}
    assert effects == ['value copied'] and key in value


def test_dict_subclass_retains_real_custom_deepcopy_fallback():
    class Metadata(dict):
        def __deepcopy__(self, memo):
            clone = Metadata({'custom': True})
            memo[id(self)] = clone
            return clone

    value = Metadata({'original': [1]})
    memo = {}
    clone = copying._copy_card_field(value, memo)
    assert type(clone) is Metadata and clone == deepcopy(value) == {'custom': True}
    assert memo[id(value)] is clone and value == {'original': [1]}
