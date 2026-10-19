"""Internal audit-scope contracts; synthetic events create no SQL/socket handles."""
from contextvars import copy_context
from pathlib import Path
import _socket
import socket
import sys
import threading
from types import SimpleNamespace

import pytest

from tests import conftest as harness


CANARIES = [
    ('test_closed_damage_instruction_compiler.py', 'test_audit_denies_all_sql_and_socket_aliases', RuntimeError),
    ('test_hand_source_incarnation_causal_audit.py', 'test_denial_before_collection_includes_native_sqlite_and_socket_new', AssertionError),
    ('test_fable_optional_linked_discard.py', 'test_preimport_guard_denies_native_public_and_dbapi_sqlite_aliases', RuntimeError),
    ('test_bloodtithe_resource_debuff_audit.py', 'test_native_and_public_sqlite_socket_denial_precedes_collection', RuntimeError),
    ('test_public_graveyard_inventory.py', 'test_pure_guard_precollection_aliases_and_audit', AssertionError),
]
EVENTS = ('sqlite3.connect', 'socket.__new__', 'socket.connect', 'socket.getaddrinfo')


def item(filename, name):
    assert hasattr(harness, '_CANARY_SCOPE'), 'Guard canaries need an installed call-scoped audit hook'
    return SimpleNamespace(path=Path(__file__).parent / filename, originalname=name)


@pytest.mark.parametrize('filename,name,error', CANARIES)
def test_exact_original_canary_registry(filename, name, error):
    assert harness._canary_error(item(filename, name)) is error


@pytest.mark.parametrize('change', ('neighbor', 'foreign-path', 'null-originalname', 'missing-originalname'))
def test_unregistered_test_cannot_activate_guard(change):
    filename, name, _ = CANARIES[0]
    probe = item(filename, name)
    if change == 'neighbor':
        probe.originalname += '_neighbor'
    elif change == 'foreign-path':
        probe.path = Path('/not-the-repository') / filename
    elif change == 'null-originalname':
        probe.originalname = None
    else:
        del probe.originalname
    assert harness._canary_error(probe) is None


@pytest.mark.parametrize('event', EVENTS)
def test_ordinary_test_scope_does_not_restrict_events(event):
    item(*CANARIES[0][:2])
    assert harness._CANARY_SCOPE.get() is None
    sys.audit(event, None)


@pytest.mark.parametrize('index', (0, 1))
@pytest.mark.parametrize('event', EVENTS)
def test_enabled_scope_preserves_original_exception_contract(index, event):
    filename, name, error = CANARIES[index]
    with harness._canary_scope_for(item(filename, name)):
        with pytest.raises(error, match='SQL/socket denied'):
            sys.audit(event, None)
    assert harness._CANARY_SCOPE.get() is None


def test_scope_resets_after_test_failure():
    with pytest.raises(ValueError, match='original failure'):
        with harness._canary_scope_for(item(*CANARIES[0][:2])):
            raise ValueError('original failure')
    assert harness._CANARY_SCOPE.get() is None
    sys.audit('sqlite3.connect', None)


def test_copied_context_cannot_restrict_another_thread():
    observed = []
    with harness._canary_scope_for(item(*CANARIES[0][:2])):
        context = copy_context()
        def probe():
            sys.audit('socket.__new__', None)
            observed.append('unrestricted')
        thread = threading.Thread(target=lambda: context.run(probe))
        thread.start()
        thread.join(timeout=5)
        assert not thread.is_alive()
        assert observed == ['unrestricted']
        with pytest.raises(RuntimeError, match='SQL/socket denied'):
            sys.audit('socket.__new__', None)
    assert harness._CANARY_SCOPE.get() is None


@pytest.mark.parametrize('failed', (False, True))
def test_saved_context_is_revoked_after_scope_exit(failed):
    context = None
    try:
        with harness._canary_scope_for(item(*CANARIES[0][:2])):
            context = copy_context()
            with pytest.raises(RuntimeError, match='SQL/socket denied'):
                context.run(sys.audit, 'sqlite3.connect', None)
            if failed:
                raise ValueError('original failure')
    except ValueError:
        assert failed
    context.run(sys.audit, 'sqlite3.connect', None)
    assert harness._CANARY_SCOPE.get() is None


@pytest.mark.parametrize('native', (False, True))
def test_bare_socket_constructor_denied_before_initialization(native):
    with harness._canary_scope_for(item(*CANARIES[0][:2])):
        cls = _socket.socket if native else socket.socket
        with pytest.raises(RuntimeError, match='SQL/socket denied'):
            cls.__new__(cls)


@pytest.mark.parametrize('failed', (False, True))
def test_socket_constructor_attributes_restored_exactly(failed):
    before_native = _socket.socket
    before_new = socket.socket.__dict__.get('__new__')
    try:
        with harness._canary_scope_for(item(*CANARIES[0][:2])):
            if failed:
                raise ValueError('original failure')
    except ValueError:
        assert failed
    assert _socket.socket is before_native
    assert socket.socket.__dict__.get('__new__') is before_new
