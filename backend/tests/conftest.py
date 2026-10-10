from __future__ import annotations

import os
import sys
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from pathlib import Path
from threading import get_ident
import _socket
import socket
from unittest.mock import patch

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Backend regressions reuse these committed fixtures, not their audit test cohorts.
AUDIT_ROOT = os.path.join(os.path.dirname(ROOT), "audit")
for fixture_dir in ("brainstorm", "gate2-suncleanser", "gate2-suncleanser-abi",
                    "gate2-domain-compiler"):
    fixture_path = os.path.join(AUDIT_ROOT, fixture_dir)
    if fixture_path not in sys.path:
        sys.path.append(fixture_path)


# These legacy audit canaries also run in ordinary, native-enabled backend CI.
_CANARY_SCOPE = ContextVar('guard_canary_scope', default=None)
_CANARIES = {
    'test_audit_denies_all_sql_and_socket_aliases': ('test_closed_damage_instruction_compiler.py', RuntimeError),
    'test_denial_before_collection_includes_native_sqlite_and_socket_new': ('test_hand_source_incarnation_causal_audit.py', AssertionError),
    'test_preimport_guard_denies_native_public_and_dbapi_sqlite_aliases': ('test_fable_optional_linked_discard.py', RuntimeError),
    'test_native_and_public_sqlite_socket_denial_precedes_collection': ('test_bloodtithe_resource_debuff_audit.py', RuntimeError),
    'test_pure_guard_precollection_aliases_and_audit': ('test_public_graveyard_inventory.py', AssertionError),
}


def _canary_error(item):
    spec = _CANARIES.get(getattr(item, 'originalname', None))
    if spec and Path(item.path).resolve() == Path(__file__).parent / spec[0]:
        return spec[1]
    return None


def _deny_guard_canary_io(event, _args):
    scope = _CANARY_SCOPE.get()
    if scope and scope['active'] and scope['thread'] == get_ident() and event in {
        'sqlite3.connect', 'socket.__new__', 'socket.connect', 'socket.getaddrinfo',
    }:
        raise scope['error']('SQL/socket denied')


sys.addaudithook(_deny_guard_canary_io)


@contextmanager
def _canary_scope_for(item):
    error = _canary_error(item)
    scope = {'thread': get_ident(), 'error': error, 'active': True} if error else None
    token = _CANARY_SCOPE.set(scope)
    try:
        with ExitStack() as constructors:
            if error:
                # Bare __new__ creates an uninitialized socket without an audit event.
                native_socket = _socket.socket
                public_new = socket.socket.__new__

                class CanarySocket(native_socket):
                    def __new__(cls, *args, **kwargs):
                        _deny_guard_canary_io('socket.__new__', ())
                        return native_socket.__new__(cls, *args, **kwargs)

                def guarded_new(cls, *args, **kwargs):
                    _deny_guard_canary_io('socket.__new__', ())
                    return public_new(cls, *args, **kwargs)

                constructors.enter_context(patch.object(_socket, 'socket', CanarySocket))
                constructors.enter_context(patch.object(socket.socket, '__new__', staticmethod(guarded_new)))
            yield
    finally:
        if scope:
            scope['active'] = False
        _CANARY_SCOPE.reset(token)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item):
    with _canary_scope_for(item):
        return (yield)
