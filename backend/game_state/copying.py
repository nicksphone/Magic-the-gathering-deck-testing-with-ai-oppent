"""Selective simulation copies with one memo and explicit history retention."""
from copy import deepcopy, _keep_alive

from game_state.state import CardInstance, Zone


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
