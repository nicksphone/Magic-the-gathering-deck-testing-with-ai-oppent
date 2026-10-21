"""Trusted startup protocols, not server execution or fitted-policy qualification.

The checkpoint has synthetic positive provenance for loader eligibility only.
Main/Uvicorn and supervisor children are inert protocol doubles.
"""
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import sys
from types import ModuleType, SimpleNamespace

import pytest


SOURCE = Path(__file__).resolve().parents[2]
PRIVATE = 'PRIVATE_OPERATOR_CHECKPOINT_CANARY'


def _module(path, name, monkeypatch):
    assert path.is_file(), 'Missing trusted operator startup entrypoint'
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


def _entry(monkeypatch):
    return _module(SOURCE / 'backend/operator_start.py',
                   'operator_start_protocol', monkeypatch)


@pytest.fixture
def operator(monkeypatch):
    # settings() inserts its source backend; keep that process-global change local.
    monkeypatch.setattr(sys, 'path', list(sys.path))
    return _module(SOURCE / 'ops/caddy/run.py', 'learned_operator_protocol', monkeypatch)


@pytest.fixture
def config_file(tmp_path, monkeypatch, operator):
    def private(name, data):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(0o600)
        return path

    python = private('python', b'Inert executable file; never executed.\n')
    python.chmod(0o700)
    caddy = private('caddy', b'Inert Caddy file; native calls are mocked.\n')
    dist = tmp_path / 'dist'
    dist.mkdir()
    (dist / 'index.html').write_text('<!doctype html><title>Public protocol</title>')
    checkpoint = private(PRIVATE + '/checkpoint.json', b'Not loaded by config validation.\n')
    config = {
        'origin': 'https://localhost:18443', 'backend_port': 18444,
        'runtime': str(tmp_path / 'runtime'), 'python': str(python),
        'caddy': str(caddy), 'dist': str(dist),
        'cert': str(private('cert.pem', b'Synthetic certificate protocol input.\n')),
        'key': str(private('key.pem', b'Synthetic private-key protocol input.\n')),
        'user': 'operator', 'password_hash': '$2b$12$' + 'A' * 53,
    }
    monkeypatch.setattr(operator, 'CADDY_SHA256', hashlib.sha256(caddy.read_bytes()).hexdigest())
    path = private('operator.json', b'{}')
    monkeypatch.setenv('MTG_OPERATOR_CONFIG', str(path))

    def write(value):
        path.write_text(json.dumps(value))
        return operator.settings()

    return SimpleNamespace(config=config, checkpoint=checkpoint, write=write)


def _launch(operator, config, monkeypatch):
    """Run the actual supervisor with inert children and recorded ownership calls."""
    handlers, children, calls = {}, [], []
    lock = SimpleNamespace(closed=False)
    lock.close = lambda: setattr(lock, 'closed', True)
    monkeypatch.setattr(operator, 'settings', lambda: config)
    monkeypatch.setattr(operator, 'prepare', lambda value: lock)
    monkeypatch.setattr(operator.sys, 'argv', [str(SOURCE / 'ops/caddy/run.py')])
    monkeypatch.setattr(operator.subprocess, 'run', lambda *a, **kw: SimpleNamespace(returncode=0))
    monkeypatch.setattr(operator.signal, 'signal', lambda sig, handler: handlers.update({sig: handler}))

    def popen(argv, **kwargs):
        child = SimpleNamespace(pid=890001 + len(children), code=None, waited=False)
        child.poll = lambda: child.code

        def wait(timeout=None):
            assert timeout == 30
            child.code, child.waited = 0, True
            return 0

        child.wait = wait
        children.append(child)
        calls.append((deepcopy(argv), deepcopy(kwargs)))
        return child

    def killpg(pid, sig):
        child = next(child for child in children if child.pid == pid)
        if sig == 0:
            assert child.waited
            raise ProcessLookupError
        assert sig == signal.SIGTERM

    monkeypatch.setattr(operator.subprocess, 'Popen', popen)
    monkeypatch.setattr(operator.os, 'killpg', killpg)
    monkeypatch.setattr(operator.time, 'sleep', lambda seconds: handlers[signal.SIGINT](signal.SIGINT, None))
    assert operator.main() == 0
    assert lock.closed and len(children) == 2 and all(child.waited for child in children)
    return calls


@pytest.fixture
def checkpoint(tmp_path):
    from ai import learned_qv, learned_policy
    from tests.test_learned_qv import blank_checkpoint

    payload = blank_checkpoint(learned_qv)
    payload['contract'] = learned_policy._current_contract()
    # Synthetic eligibility metadata, NOT evidence of actual fitting or strength.
    payload['provenance']['updates'] = 1
    payload['provenance']['samples'] = 1
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    path = tmp_path / (PRIVATE + '.json')
    path.write_bytes(raw)
    path.chmod(0o600)
    return SimpleNamespace(path=path, raw=raw, digest=hashlib.sha256(raw).hexdigest(), payload=payload)


def _services(monkeypatch, calls, configure=None):
    main = ModuleType('main')
    main.app = object()
    main.configure_new_match_policy = configure or (lambda binding: calls.append(('configure', binding)))
    uvicorn = ModuleType('uvicorn')
    uvicorn.run = lambda app, **kwargs: calls.append(('serve', app, kwargs))
    monkeypatch.setitem(sys.modules, 'main', main)
    monkeypatch.setitem(sys.modules, 'uvicorn', uvicorn)
    return main


def _arguments(checkpoint):
    return ['--checkpoint', str(checkpoint.path), '--checkpoint-sha256', checkpoint.digest,
            '--host', '127.0.0.1', '--port', '18444']


def test_absent_config_preserves_original_backend_and_caddy_commands(operator, config_file, monkeypatch):
    config = config_file.write(config_file.config)
    assert 'learned_policy' not in config
    calls = _launch(operator, config, monkeypatch)
    assert calls[0][0] == [str(config['python']), '-m', 'uvicorn', 'main:app',
                          '--host', '127.0.0.1', '--port', '18444', '--workers', '1',
                          '--no-access-log', '--no-proxy-headers', '--log-level', 'critical']
    assert calls[1][0] == [str(config['caddy']), 'run', '--config',
                          str(SOURCE / 'ops/caddy/Caddyfile'), '--adapter', 'caddyfile']
    assert calls[0][1]['env'] == {
        'PATH': '/usr/bin:/bin', 'HOME': str(config['runtime']), 'LANG': 'C.UTF-8',
        'PYTHONDONTWRITEBYTECODE': '1', 'MTG_TRUSTED_ORIGINS': config['origin']}


def test_private_learned_config_accepts_only_checkpoint_and_sha256(operator, config_file):
    learned = {'checkpoint': str(config_file.checkpoint), 'sha256': 'a' * 64}
    config = config_file.write({**config_file.config, 'learned_policy': learned})
    assert config['learned_policy'] == {'checkpoint': config_file.checkpoint, 'sha256': 'a' * 64}


@pytest.mark.parametrize('mutation', ['extra-name', 'missing-hash', 'missing-path',
                                     'uppercase-hash', 'boolean-hash', 'relative-path'])
def test_private_learned_config_rejects_malformed_closed_fields(operator, config_file, mutation):
    learned = {'checkpoint': str(config_file.checkpoint), 'sha256': 'a' * 64}
    if mutation == 'extra-name': learned['name'] = 'latest'
    elif mutation == 'missing-hash': del learned['sha256']
    elif mutation == 'missing-path': del learned['checkpoint']
    elif mutation == 'uppercase-hash': learned['sha256'] = 'A' * 64
    elif mutation == 'boolean-hash': learned['sha256'] = True
    else: learned['checkpoint'] = 'relative-checkpoint.json'
    with pytest.raises((ValueError, OSError)):
        config_file.write({**config_file.config, 'learned_policy': learned})


@pytest.mark.parametrize('location', ['source', 'served-dist'])
def test_checkpoint_cannot_be_inside_source_or_served_dist(operator, config_file, tmp_path, monkeypatch, location):
    fake_source = tmp_path / 'source'
    fake_source.mkdir()
    monkeypatch.setattr(operator, 'SOURCE', fake_source)
    parent = fake_source if location == 'source' else Path(config_file.config['dist'])
    path = parent / 'checkpoint.json'
    path.write_bytes(b'Synthetic owned policy probe, not real source data.')
    path.chmod(0o600)
    learned = {'checkpoint': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    with pytest.raises((ValueError, OSError)):
        config_file.write({**config_file.config, 'learned_policy': learned})


def test_enabled_operator_launch_uses_explicit_cli_and_unchanged_caddy(operator, config_file, monkeypatch, capsys):
    config = config_file.write({**config_file.config, 'learned_policy': {
        'checkpoint': str(config_file.checkpoint), 'sha256': 'b' * 64}})
    calls = _launch(operator, config, monkeypatch)
    assert calls[0][0] == [str(config['python']), '-m', 'operator_start',
                          '--checkpoint', str(config_file.checkpoint), '--checkpoint-sha256', 'b' * 64,
                          '--host', '127.0.0.1', '--port', '18444']
    assert calls[0][1]['cwd'] == config['runtime'] / 'backend'
    assert calls[0][1]['start_new_session'] is True
    assert calls[1][0] == [str(config['caddy']), 'run', '--config',
                          str(SOURCE / 'ops/caddy/Caddyfile'), '--adapter', 'caddyfile']
    backend_env, caddy_env = operator.environment(config)
    assert calls[0][1]['env'] == backend_env and calls[1][1]['env'] == caddy_env
    base = {'PATH': '/usr/bin:/bin', 'HOME': str(config['runtime']),
            'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1'}
    assert backend_env == {**base, 'MTG_TRUSTED_ORIGINS': config['origin']}
    assert caddy_env == {
        **base, 'XDG_DATA_HOME': str(config['runtime'] / 'caddy-data'),
        'XDG_CONFIG_HOME': str(config['runtime'] / 'caddy-config'),
        'MTG_FRONTEND_BIND': config['bind_address'], 'MTG_SITE_ORIGIN': config['origin'],
        'MTG_BACKEND_PORT': '18444', 'MTG_FRONTEND_DIST': str(config['dist']),
        'MTG_TLS_CERT': str(config['cert']), 'MTG_TLS_KEY': str(config['key']),
        'MTG_AUTH_USER': config['user'], 'MTG_AUTH_HASH': config['password_hash']}
    assert not any('POLICY' in key or 'CHECKPOINT' in key for env in (backend_env, caddy_env) for key in env)
    assert PRIVATE not in json.dumps([backend_env, caddy_env])
    captured = capsys.readouterr()
    assert PRIVATE not in captured.out + captured.err


def test_loader_reads_once_and_binds_the_same_hash_checked_buffer(checkpoint, monkeypatch):
    from ai import learned_qv, learned_policy
    read, bind = learned_qv.read_bytes, learned_policy.bind_live_policy
    calls = []

    def reader(path, limit):
        assert limit == learned_qv.MAX_CHECKPOINT_BYTES == 2 * 1024 * 1024
        raw = read(path, limit)
        calls.append(('read', raw))
        return raw

    def binder(raw):
        assert len(calls) == 1 and raw is calls[0][1]
        assert hashlib.sha256(raw).hexdigest() == checkpoint.digest
        calls.append(('bind', raw))
        return bind(raw)

    monkeypatch.setattr(learned_qv, 'read_bytes', reader)
    monkeypatch.setattr(learned_policy, 'bind_live_policy', binder)
    loaded = _entry(monkeypatch).load_binding(checkpoint.path, checkpoint.digest)
    assert isinstance(loaded, learned_policy.LivePolicyBinding)
    assert isinstance(loaded._policy, learned_qv.QVPolicy)
    assert loaded.checkpoint_sha256 == checkpoint.digest
    assert loaded.contract == checkpoint.payload['contract']
    assert [kind for kind, _ in calls] == ['read', 'bind']


def test_hash_mismatch_is_rejected_before_binding(checkpoint, monkeypatch):
    from ai import learned_policy
    calls = []
    monkeypatch.setattr(learned_policy, 'bind_live_policy', lambda raw: calls.append(raw))
    with pytest.raises(ValueError):
        _entry(monkeypatch).load_binding(checkpoint.path, '0' * 64)
    assert calls == []


@pytest.mark.parametrize('mutation', ['stale-engine', 'zero-updates'])
def test_real_binder_rejects_invalid_checkpoint_contract_or_eligibility(checkpoint, monkeypatch, mutation):
    payload = deepcopy(checkpoint.payload)
    if mutation == 'stale-engine': payload['contract']['engine_hash'] = '0' * 64
    else: payload['provenance']['updates'] = 0
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    checkpoint.path.write_bytes(raw)
    with pytest.raises(ValueError):
        _entry(monkeypatch).load_binding(checkpoint.path, hashlib.sha256(raw).hexdigest())


@pytest.mark.parametrize('kind', ['symlink', 'hardlink', 'directory', 'oversize'])
def test_loader_retains_existing_bounded_regular_file_intake(checkpoint, tmp_path, monkeypatch, kind):
    from ai.learned_qv import MAX_CHECKPOINT_BYTES
    path = tmp_path / 'rejected-input'
    if kind == 'symlink': path.symlink_to(checkpoint.path)
    elif kind == 'hardlink': os.link(checkpoint.path, path)
    elif kind == 'directory': path.mkdir()
    else: path.write_bytes(b'X' * (MAX_CHECKPOINT_BYTES + 1))
    with pytest.raises((ValueError, OSError)):
        _entry(monkeypatch).load_binding(path, checkpoint.digest)


def test_entrypoint_configures_real_binding_before_fixed_uvicorn_run(checkpoint, monkeypatch):
    from ai.learned_policy import LivePolicyBinding
    calls = []
    main = _services(monkeypatch, calls)
    entry = _entry(monkeypatch)
    assert entry.main(_arguments(checkpoint)) == 0
    assert [call[0] for call in calls] == ['configure', 'serve']
    assert isinstance(calls[0][1], LivePolicyBinding)
    assert calls[0][1].checkpoint_sha256 == checkpoint.digest
    assert calls[1] == ('serve', main.app, {
        'host': '127.0.0.1', 'port': 18444, 'workers': 1,
        'access_log': False, 'proxy_headers': False, 'log_level': 'critical'})


@pytest.mark.parametrize('failure', ['wrong-hash', 'invalid-json'])
def test_failed_intake_never_configures_serves_or_echoes_private_input(checkpoint, monkeypatch, capsys, failure):
    calls = []
    _services(monkeypatch, calls)
    if failure == 'wrong-hash': checkpoint.digest = '0' * 64
    else:
        checkpoint.path.write_text(PRIVATE)
        checkpoint.digest = hashlib.sha256(checkpoint.path.read_bytes()).hexdigest()
    assert _entry(monkeypatch).main(_arguments(checkpoint)) == 2
    assert calls == []
    captured = capsys.readouterr()
    assert captured.out == '' and captured.err == 'Learned policy startup rejected.\n'


def test_configuration_failure_never_serves_or_exposes_exception(checkpoint, monkeypatch, capsys):
    calls = []

    def rejected(binding):
        calls.append(('configure', binding))
        raise RuntimeError(PRIVATE)

    _services(monkeypatch, calls, rejected)
    assert _entry(monkeypatch).main(_arguments(checkpoint)) == 2
    assert [call[0] for call in calls] == ['configure']
    captured = capsys.readouterr()
    assert captured.out == '' and captured.err == 'Learned policy startup rejected.\n'
