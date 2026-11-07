"""Selective simulation copies with one memo and explicit history retention."""
from copy import deepcopy, _keep_alive, _deepcopy_dispatch, dispatch_table
from types import GetSetDescriptorType

from game_state.state import CardInstance, MatchState, Zone


_immutable_card_types = frozenset((str, int, float, bool, type(None), Zone))


def copy_match_state(state, *, memo=None, include_history=True, _field_copier=None):
    """Copy gameplay state, preserving history unless the caller explicitly omits it."""
    fresh_memo = memo is None
    native_setup = (fresh_memo and (_field_copier is None or _field_copier is _native_copy_bindings[2])
                    and _native_card_setup(state))
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
    active = None
    if (native_setup and (_field_copier is None or _field_copier is _native_copy_bindings[2])
            and root_attributes is not None
            and all(current is native for current, native in zip(
                (deepcopy, _keep_alive, _copy_card_field, _immutable_card_types, MatchState, CardInstance, Zone),
                _native_copy_bindings))
            and _keep_alive.__code__ is _native_keep_alive_code
            and not any(name in CardInstance.__dict__ for name in hooks)
            and all(type(table) is dict and len(table) == len(layout)
                    and all(key is old_key and value is old_value
                            for (key, value), (old_key, old_value) in zip(table.items(), layout))
                    for table, layout in zip((_deepcopy_dispatch, dispatch_table), _native_dispatch_layouts))):
        active = [True, id(memo)]
        entry_copy_field = copy_field
        def copy_field(value, memo):
            if active[0] and _copy_card_field is _native_copy_bindings[2]:
                return _copy_card_field_prefix(value, memo, active)
            active[0] = False
            return entry_copy_field(value, memo)
    for card in cards:
        memo[id(card)] = object.__new__(CardInstance)
        memo.setdefault(id(card.__dict__), {})
        memo[id(card)].__dict__ = memo[id(card.__dict__)]
    for card in cards:
        fields = {}
        for key, value in card.__dict__.items():
            kind = type(value)
            if active is not None and active[0] and (type(key) is not str or not (
                    kind is str or kind is int or kind is float or kind is bool or kind is _none_type
                    or kind is Zone or kind is list or kind is dict or kind is set)):
                active[0] = False
            fields[key] = value if kind in _immutable_card_types else copy_field(value, memo)
        memo[id(card)].__dict__.update(fields)
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
        for key in value:
            if type(key) not in _immutable_card_types:
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


def _native_card_setup(state):
    """Qualify setup before getters or cards.values() can observe the new memo."""
    if (MatchState is not _native_copy_bindings[4] or CardInstance is not _native_copy_bindings[5]
            or type(state) is not MatchState):
        return False
    for cls, descriptor, setter in zip((MatchState, CardInstance), _native_setup_descriptors,
                                       _native_setup_setters):
        if (cls.__bases__ != (object,) or cls.__dict__.get('__dict__') is not descriptor
                or cls.__getattribute__ is not object.__getattribute__ or '__getattr__' in cls.__dict__
                or cls.__setattr__ is not setter):
            return False
    if 'cards' in MatchState.__dict__ or 'log' in MatchState.__dict__:
        return False
    attributes = object.__getattribute__(state, '__dict__')
    return (type(attributes) is dict and all(type(key) is str for key in attributes)
            and type(attributes.get('cards')) is dict
            and (attributes.get('log') is None or type(attributes.get('log')) is list))


def _copy_card_field_prefix(value, memo, active):
    """Skip atomic memo probes only until this copy first enters foreign code."""
    kind = type(value)
    if kind is str or kind is int or kind is float or kind is bool or kind is _none_type or kind is Zone:
        return value if active[0] else memo.get(id(value), value)
    if kind is not list and kind is not dict and kind is not set:
        active[0] = False
        return _copy_card_field(value, memo)
    identity = id(value)
    if identity in memo:
        return memo[identity]
    if kind is list:
        result = []
        memo[identity] = result
        for item in value:
            if active[0]:
                item_kind = type(item)
                child = item if (item_kind is str or item_kind is int or item_kind is float
                    or item_kind is bool or item_kind is _none_type or item_kind is Zone) else _copy_card_field_prefix(item, memo, active)
            else:
                child = memo.get(id(item), item) if type(item) in _immutable_card_types else _copy_card_field(item, memo)
            result.append(child)
    else:
        for key in value:
            key_kind = type(key)
            if not (key_kind is str or key_kind is int or key_kind is float or key_kind is bool
                    or key_kind is _none_type):
                active[0] = False
                return _copy_card_field(value, memo)
        if kind is set:
            result = value.copy()
        else:
            result = {}
            memo[identity] = result
            for key, item in value.items():
                if active[0]:
                    item_kind = type(item)
                    child = item if (item_kind is str or item_kind is int or item_kind is float
                        or item_kind is bool or item_kind is _none_type or item_kind is Zone) else _copy_card_field_prefix(item, memo, active)
                else:
                    child = memo.get(id(item), item) if type(item) in _immutable_card_types else _copy_card_field(item, memo)
                result[key if active[0] else memo.get(id(key), key)] = child
    memo[identity] = result
    if (active[0] and _keep_alive is _native_copy_bindings[1]
            and _keep_alive.__code__ is _native_keep_alive_code):
        try:
            memo[active[1]].append(value)
        except KeyError:
            memo[active[1]] = [value]
    else:
        active[0] = False
        _keep_alive(value, memo)
    return result


_none_type = type(None)
_native_copy_bindings = (deepcopy, _keep_alive, _copy_card_field, _immutable_card_types, MatchState, CardInstance, Zone)
_native_dispatch_layouts = (tuple(_deepcopy_dispatch.items()), tuple(dispatch_table.items()))
_native_setup_descriptors = (MatchState.__dict__['__dict__'], CardInstance.__dict__['__dict__'])
_native_keep_alive_code = _keep_alive.__code__
_native_setup_setters = (MatchState.__setattr__, CardInstance.__setattr__)
