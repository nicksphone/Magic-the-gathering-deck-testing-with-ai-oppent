"""PYTEST_DONT_REWRITE: actual pinned binary and private config boundaries."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

import pytest

SECURITY_SHA256 = 'e8d6545c8485f7bd723fc3a6a2fb5662e89a235ae0d32ccde3f43d81577b0db0'
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('security_operator', HERE / 'run.py')
operator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(operator)


@pytest.fixture
def private_config(tmp_path, monkeypatch):
    binary = Path(os.environ['MTG_CADDY_BINARY']).resolve()
    assert hashlib.sha256(binary.read_bytes()).hexdigest() == SECURITY_SHA256
    dist = tmp_path / 'dist'
    dist.mkdir()
    (dist / 'index.html').write_text('<html>settings boundary only</html>')
    cert, key = tmp_path / 'cert.pem', tmp_path / 'key.pem'
    cert.write_text('settings-only certificate file fixture')
    key.write_text('settings-only key file fixture')
    key.chmod(0o600)
    # Shape-only settings operands; verify-config.py separately generates real material.
    config = dict(origin='https://localhost:18443', backend_port=18444,
                  runtime=str(tmp_path / 'runtime'), python=sys.executable,
                  caddy=str(binary), dist=str(dist), cert=str(cert), key=str(key),
                  user='operator', password_hash='$2b$10$' + 'A' * 53)
    path = tmp_path / 'operator.json'
    path.write_text(json.dumps(config))
    path.chmod(0o600)
    monkeypatch.setenv('MTG_OPERATOR_CONFIG', str(path))
    yield config, path
    assert hashlib.sha256(binary.read_bytes()).hexdigest() == SECURITY_SHA256


def test_actual_verified_security_binary_is_accepted(private_config):
    config, _ = private_config
    checked = operator.settings()
    assert checked['caddy'] == Path(config['caddy'])
    assert operator.CADDY_SHA256 == SECURITY_SHA256


def test_one_bit_changed_actual_binary_is_rejected(private_config, tmp_path):
    config, path = private_config
    changed = tmp_path / 'one-bit-changed-caddy'
    shutil.copyfile(config['caddy'], changed)
    with changed.open('r+b') as stream:
        old = stream.read(1)
        stream.seek(0)
        stream.write(bytes([old[0] ^ 1]))
    config['caddy'] = str(changed)
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match='operator precheck failed'):
        operator.settings()


@pytest.mark.parametrize('boundary', ['public-config', 'public-key', 'served-key', 'unknown-field'])
def test_private_config_boundaries_remain_fail_closed(private_config, boundary):
    config, path = private_config
    operator.settings()  # A valid real-binary baseline must precede each negative.
    if boundary == 'public-config':
        path.chmod(0o644)
    elif boundary == 'public-key':
        Path(config['key']).chmod(0o644)
    elif boundary == 'served-key':
        served = Path(config['dist']) / 'key.pem'
        shutil.copyfile(config['key'], served)
        served.chmod(0o600)
        config['key'] = str(served)
        path.write_text(json.dumps(config))
    else:
        config['unexpected'] = True
        path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match='operator precheck failed'):
        operator.settings()


def test_credentials_stay_out_of_backend_environment(private_config):
    _, _path = private_config
    backend, caddy = operator.environment(operator.settings())
    assert set(backend) == {'PATH', 'HOME', 'LANG', 'PYTHONDONTWRITEBYTECODE', 'MTG_TRUSTED_ORIGINS'}
    assert not any('AUTH' in name or 'TLS' in name for name in backend)
    assert all(name in caddy for name in ('MTG_AUTH_USER', 'MTG_AUTH_HASH', 'MTG_TLS_CERT', 'MTG_TLS_KEY'))
