"""Ordinary pytest scope controls; no provider, child, file SQL or network IO."""
import builtins
from contextvars import copy_context
import os
from pathlib import Path
import _socket
import socket
import sys
import threading
from types import ModuleType, SimpleNamespace

import pytest

from tests import conftest as harness
from tests import test_log_priors_archetype as original


def target():
    return SimpleNamespace(path=Path(original.__file__), originalname='test_precollection_pure_io_canaries')


def test_direct_original_target_executes_without_skip_and_twelve_denials():
    assert harness._canary_error(target()) is RuntimeError
    with harness._canary_scope_for(target()):
        assert os.environ.get('TASK33_PURE_GUARD') == '1'
        try:
            original.test_precollection_pure_io_canaries()  # Original ten calls unchanged.
        except pytest.skip.Exception:
            pytest.fail('Ordinary-CI canary body must execute, never skip')
        with pytest.raises(RuntimeError, match='pure guard'):
            socket.getaddrinfo('localhost', 1)
        # An uninitialized socket rejects its address before emitting this audit
        # event; test the event without allocating a real network socket.
        with pytest.raises(RuntimeError, match='pure guard'):
            sys.audit('socket.connect', None, ('127.0.0.1', 1))


@pytest.mark.parametrize('prior', [None, 'outer-value'])
@pytest.mark.parametrize('failed', [False, True])
def test_environment_scope_and_import_socket_identities_restore(monkeypatch, prior, failed):
    if prior is None:
        monkeypatch.delenv('TASK33_PURE_GUARD', raising=False)
    else:
        monkeypatch.setenv('TASK33_PURE_GUARD', prior)
    saved_import, saved_native = builtins.__import__, _socket.socket
    saved_new = socket.socket.__dict__.get('__new__')
    prior_scope = harness._CANARY_SCOPE.get()
    try:
        with harness._canary_scope_for(target()):
            assert os.environ.get('TASK33_PURE_GUARD') == '1'
            assert harness._CANARY_SCOPE.get()['active'] is True
            if failed:
                raise ValueError('public fixture failure')
    except ValueError:
        assert failed
    assert os.environ.get('TASK33_PURE_GUARD') == prior
    assert harness._CANARY_SCOPE.get() is prior_scope
    assert builtins.__import__ is saved_import
    assert _socket.socket is saved_native
    assert socket.socket.__dict__.get('__new__') is saved_new


def test_preloaded_provider_import_is_denied_only_inside_target(monkeypatch):
    dummy = ModuleType('openai')
    monkeypatch.setitem(sys.modules, 'openai', dummy)
    assert harness._canary_error(target()) is RuntimeError
    with harness._canary_scope_for(target()):
        with pytest.raises(RuntimeError, match='pure guard'):
            __import__('openai')
    assert __import__('openai') is dummy  # No actual provider module imported.


@pytest.mark.parametrize('change', ['neighbor', 'foreign-path', 'missing-name'])
def test_wrong_file_or_name_cannot_enable_task33_flag(change, monkeypatch):
    monkeypatch.delenv('TASK33_PURE_GUARD', raising=False)
    item = target()
    if change == 'neighbor':
        item.originalname += '_neighbor'
    elif change == 'foreign-path':
        item.path = Path('/not-the-repository') / item.path.name
    else:
        del item.originalname
    assert harness._canary_error(item) is None
    with harness._canary_scope_for(item):
        assert harness._CANARY_SCOPE.get() is None
        assert 'TASK33_PURE_GUARD' not in os.environ


def test_original_scope_keeps_old_prefix_and_no_task33_process_provider_rules(monkeypatch):
    monkeypatch.delenv('TASK33_PURE_GUARD', raising=False)
    item = SimpleNamespace(path=Path(__file__).with_name('test_closed_damage_instruction_compiler.py'),
                           originalname='test_audit_denies_all_sql_and_socket_aliases')
    with harness._canary_scope_for(item):
        assert 'TASK33_PURE_GUARD' not in os.environ
        with pytest.raises(RuntimeError, match='SQL/socket denied'):
            harness._deny_guard_canary_io('sqlite3.connect', (None,))
        assert harness._deny_guard_canary_io('subprocess.Popen', (None,)) is None
        assert harness._deny_guard_canary_io('import', ('openai',)) is None


def test_task33_copied_context_stays_thread_bound_and_revokes_after_exit():
    assert harness._canary_error(target()) is RuntimeError
    with harness._canary_scope_for(target()):
        context = copy_context()
        seen = []
        def other_thread():
            for event, args in [('sqlite3.connect', (None,)), ('subprocess.Popen', (None,)),
                                ('import', ('openai',))]:
                assert harness._deny_guard_canary_io(event, args) is None
            seen.append('unrestricted')
        thread = threading.Thread(target=lambda: context.run(other_thread))
        thread.start()
        thread.join(timeout=5)
        assert not thread.is_alive()
        assert seen == ['unrestricted']
    assert context.run(harness._deny_guard_canary_io, 'import', ('openai',)) is None
