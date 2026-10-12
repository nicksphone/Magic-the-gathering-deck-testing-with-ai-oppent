"""Finalization must not erase the canary's retained context or thread identity."""
import ast
from contextvars import ContextVar
from pathlib import Path
from threading import get_ident

import pytest


def guard_namespace():
    tree = ast.parse(Path(__file__).with_name('conftest.py').read_bytes())
    function = next(node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == '_deny_guard_canary_io')
    namespace = {'_CANARY_SCOPE': ContextVar('finalization_test', default=None),
                 'get_ident': get_ident}
    exec(compile(ast.Module(body=[function], type_ignores=[]), '<canary>', 'exec'), namespace)
    return namespace


def test_inactive_canary_survives_finalized_module_globals():
    namespace = guard_namespace()
    guard = namespace['_deny_guard_canary_io']
    namespace.update(_CANARY_SCOPE=None, get_ident=None)
    assert guard('sqlite3.connect', ()) is None


def test_active_canary_keeps_denial_when_module_globals_are_cleared():
    namespace = guard_namespace()
    context = namespace['_CANARY_SCOPE']
    token = context.set({'active': True, 'thread': get_ident(), 'error': RuntimeError})
    try:
        guard = namespace['_deny_guard_canary_io']
        namespace.update(_CANARY_SCOPE=None, get_ident=None)
        for event in ('sqlite3.connect', 'socket.__new__', 'socket.connect', 'socket.getaddrinfo'):
            with pytest.raises(RuntimeError, match='SQL/socket denied'):
                guard(event, ())
    finally:
        context.reset(token)


def test_canary_still_ignores_other_threads_and_unrelated_events():
    namespace = guard_namespace()
    context = namespace['_CANARY_SCOPE']
    guard = namespace['_deny_guard_canary_io']
    scope = {'active': True, 'thread': get_ident() + 1, 'error': RuntimeError}
    token = context.set(scope)
    try:
        namespace.update(_CANARY_SCOPE=None, get_ident=None)
        assert guard('sqlite3.connect', ()) is None
        scope['thread'] = get_ident()
        assert guard('open', ()) is None
        scope['active'] = False
        assert guard('socket.connect', ()) is None
    finally:
        context.reset(token)
