"""Selective simulation copies with one memo and explicit history retention."""
from copy import deepcopy, _keep_alive, _deepcopy_dispatch, dispatch_table
from types import GetSetDescriptorType

from game_state.state import CardInstance, MatchState, Zone


_immutable_card_types = frozenset((str, int, float, bool, type(None), Zone))


def copy_match_state(state, *, memo=None, include_history=True, _field_copier=None):
    """Copy gameplay state, preserving history unless the caller explicitly omits it."""
    memo = {} if memo is None else dict(memo)
    supplied = set(memo)
    log = getattr(state, 'log', None)
    if isinstance(log, list) and not include_history:
        memo.setdefault(id(log), [])
    elif type(log) is list and all(type(entry) is str for entry in log):
        memo.setdefault(id(log), log.copy())
    copy_field = _copy_card_field if _field_copier is None else _field_copier
    root_attributes = None
    hooks = ('__deepcopy__', '__getstate__', '__setstate__', '__reduce__',
             '__reduce_ex__', '__getnewargs__', '__getnewargs_ex__',
             '__getattr__', '__getattribute__', '__new__')
    if (type(state) is MatchState and MatchState.__bases__ == (object,)
            and type(MatchState.__dict__.get('__dict__')) is GetSetDescriptorType
            and not any(name in MatchState.__dict__ for name in hooks)
            and MatchState not in _deepcopy_dispatch and MatchState not in dispatch_table):
        attributes = vars(state)
        if (type(attributes) is dict and not any(name in attributes for name in hooks)
                and id(state) not in memo and id(attributes) not in memo):
            root_attributes = attributes
            result = object.__new__(MatchState)
            root_dictionary = {}
            # Card metadata may reach either root before the Card prepass ends.
            memo[id(state)] = result
            memo[id(attributes)] = root_dictionary
    # Explicit attribute-dictionary overrides and subclasses retain deepcopy's
    # contract. Ordinary cards can bypass immutable-field reconstruction.
    cards = [card for card in getattr(state, 'cards', {}).values()
             if type(card) is CardInstance and type(card.__dict__) is dict
             and id(card) not in memo and id(card.__dict__) not in supplied]
    for card in cards:
        memo[id(card)] = object.__new__(CardInstance)
        memo.setdefault(id(card.__dict__), {})
        memo[id(card)].__dict__ = memo[id(card.__dict__)]
    for card in cards:
        memo[id(card)].__dict__.update({
            key: value if type(value) in _immutable_card_types else copy_field(value, memo)
            for key, value in card.__dict__.items()
        })
    if root_attributes is not None:
        # Exact sets can have registered protocols which the Card copier bypasses.
        copy_root_field = (deepcopy if set in dispatch_table or set in _deepcopy_dispatch
                           else _copy_card_field)
        for key, value in root_attributes.items():
            child = copy_root_field(value, memo)
            root_dictionary[copy_root_field(key, memo)] = child
        # deepcopy updates the new instance dictionary; aliases retain a distinct D.
        result.__dict__.update(root_dictionary)
        _keep_alive(root_attributes, memo)
        _keep_alive(state, memo)
    return deepcopy(state, memo)


def _copy_card_field(value, memo):
    """Copy exact metadata containers, preserving one memo and custom-copy fallback."""
    identity = id(value)
    if identity in memo:
        return memo[identity]
    kind = type(value)
    if kind in _immutable_card_types:
        return value
    if kind is list:
        result = []
        memo[identity] = result
        for item in value:
            result.append(memo.get(id(item), item) if type(item) in _immutable_card_types
                          else _copy_card_field(item, memo))
    elif kind is dict:
        if not all(type(key) in _immutable_card_types for key in value):
            return deepcopy(value, memo)
        result = {}
        memo[identity] = result
        for key, item in value.items():
            child = memo.get(id(item), item) if type(item) in _immutable_card_types else _copy_card_field(item, memo)
            result[memo.get(id(key), key)] = child
    elif kind is set and all(type(item) in _immutable_card_types and
            (id(item) not in memo or memo[id(item)] is item) for item in value):
        result = value.copy()
    else:
        return deepcopy(value, memo)
    memo[identity] = result
    _keep_alive(value, memo)
    return result
