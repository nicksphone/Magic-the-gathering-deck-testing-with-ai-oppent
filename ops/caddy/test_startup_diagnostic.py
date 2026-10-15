"""Real supervisor flow with inert children; no service, SQL or native execution."""
import importlib.util
from pathlib import Path
import signal
import subprocess
from types import SimpleNamespace

import pytest


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('startup_operator', HERE / 'run.py')
operator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(operator)
PRIVATE = 'PRIVATE_CREDENTIAL_KEY_CONFIG_ERROR_SENTINEL'


@pytest.fixture
def supervisor(monkeypatch, capsys):
    lock = SimpleNamespace(closed=False)
    lock.close = lambda: setattr(lock, 'closed', True)
    config = dict(runtime=Path('/' + PRIVATE), python=Path('/private/python'),
                  caddy=Path('/private/caddy'), origin='https://private.invalid:18443',
                  bind_address='127.0.0.1', backend_port=18444,
                  dist=Path('/private/dist'), cert=Path('/private/cert'),
                  key=Path('/private/key'), user=PRIVATE, password_hash=PRIVATE)
    monkeypatch.setenv('MTG_OPERATOR_CONFIG', '/' + PRIVATE + '/operator.json')
    monkeypatch.setattr(operator, 'settings', lambda: config)
    monkeypatch.setattr(operator, 'prepare', lambda cfg: lock)
    monkeypatch.setattr(operator.subprocess, 'run', lambda *a, **kw: SimpleNamespace(returncode=0))
    handlers, children, signals = {}, [], []
    monkeypatch.setattr(operator.signal, 'signal', lambda signum, handler: handlers.update({signum: handler}))
    monkeypatch.setattr(operator.os, 'killpg', lambda pid, signum: signals.append((pid, signum)))

    def drive(codes=(None, None), *, spawn_error=None, timeout=False, check=False):
        class Child:
            def __init__(self, index):
                self.pid, self.code, self.waits = 700001 + index, codes[index], []

            def poll(self):
                return self.code

            def wait(self, timeout=None):
                self.waits.append(timeout)
                if drive_timeout and self.pid == 700001 and len(self.waits) == 1:
                    raise subprocess.TimeoutExpired(PRIVATE, timeout)
                if self.code is None:
                    self.code = 0
                return self.code

        drive_timeout = timeout

        def popen(*args, **kwargs):
            index = len(children)
            if spawn_error is not None and index == spawn_error[0]:
                raise spawn_error[1](PRIVATE)
            child = Child(index)
            children.append(child)
            return child

        monkeypatch.setattr(operator.subprocess, 'Popen', popen)
        monkeypatch.setattr(operator.time, 'sleep', lambda seconds: handlers[signal.SIGINT](signal.SIGINT, None))
        monkeypatch.setattr(operator.sys, 'argv', [str(HERE / 'run.py')] + (['--check'] if check else []))
        error, code = None, None
        try:
            code = operator.main()
        except OSError as caught:
            error = caught
        captured = capsys.readouterr()
        assert PRIVATE not in captured.out + captured.err
        assert '/private/' not in captured.out + captured.err
        return SimpleNamespace(code=code, error=error, out=captured.out, err=captured.err,
                               lock=lock, children=children, signals=signals)

    return drive


@pytest.mark.parametrize('codes,message', [
    ((0, None), 'Backend exited unexpectedly (exit code 0).'),
    ((2, None), 'Backend exited unexpectedly (exit code 2).'),
    ((-15, None), 'Backend exited unexpectedly (exit code -15).'),
    ((None, 0), 'HTTPS exited unexpectedly (exit code 0).'),
    ((None, 2), 'HTTPS exited unexpectedly (exit code 2).'),
    ((None, -15), 'HTTPS exited unexpectedly (exit code -15).'),
])
def test_service_exit_is_named_without_private_output(supervisor, codes, message):
    result = supervisor(codes)
    assert result.code == 1 and result.error is None
    assert result.err.strip() == message
    assert result.lock.closed
    assert all(child.waits == [30] for child in result.children)


@pytest.mark.parametrize('index,error_class,message', [
    (0, FileNotFoundError, 'Backend could not start (FileNotFoundError).'),
    (0, PermissionError, 'Backend could not start (PermissionError).'),
    (1, FileNotFoundError, 'HTTPS could not start (FileNotFoundError).'),
    (1, PermissionError, 'HTTPS could not start (PermissionError).'),
])
def test_spawn_error_names_only_service_and_class(supervisor, index, error_class, message):
    result = supervisor(spawn_error=(index, error_class))
    assert type(result.error) is error_class
    assert result.err.strip() == message
    assert result.lock.closed
    assert len(result.children) == index
    assert all(child.waits == [30] for child in result.children)


def test_ctrl_c_remains_normal_and_releases_lock(supervisor):
    result = supervisor()
    assert result.code == 0 and result.err == '' and result.error is None
    assert result.lock.closed
    assert result.signals == [(700001, signal.SIGTERM), (700002, signal.SIGTERM)]
    assert all(child.waits == [30] for child in result.children)


def test_both_exited_services_are_named(supervisor):
    result = supervisor((2, -15))
    assert result.code == 1 and result.lock.closed
    assert result.err.splitlines() == ['Backend exited unexpectedly (exit code 2).',
                                       'HTTPS exited unexpectedly (exit code -15).']


def test_shutdown_timeout_retains_kill_and_nonzero(supervisor):
    result = supervisor(timeout=True)
    assert result.code == 1 and result.lock.closed
    assert result.err.strip() == 'Child exceeded shutdown timeout; recovery inspection required.'
    assert result.signals == [(700001, signal.SIGTERM), (700002, signal.SIGTERM),
                              (700001, signal.SIGKILL)]
    assert result.children[0].waits == [30, None]


def test_check_remains_configuration_only(supervisor):
    result = supervisor(check=True)
    assert result.code == 0 and result.error is None and result.err == ''
    assert result.out.strip() == 'Operator configuration valid; no server started.'
    assert result.children == [] and not result.lock.closed
