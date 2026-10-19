"""File-only LAN option contracts; no listener, certificate or LAN proof."""
import json
from pathlib import Path

import pytest

from test_security_candidate_config import private_config, operator


def configured(private_config, value, **extra):
    config, path = private_config
    config.update(bind_address=value, **extra)
    path.write_text(json.dumps(config))
    return config


def admitted():
    try:
        return operator.settings()
    except ValueError:
        pytest.fail("Declared canonical loopback/private bind must be admitted")


def test_legacy_ten_keys_default_to_exact_loopback(private_config):
    assert len(private_config[0]) == 10
    assert admitted().get('bind_address') == '127.0.0.1'


@pytest.mark.parametrize('address', ['127.0.0.1', '10.1.2.3', '172.16.1.2',
                                    '172.31.255.254', '192.168.1.2'])
def test_declared_canonical_private_and_loopback_are_admitted(private_config, address):
    configured(private_config, address)
    assert admitted().get('bind_address') == address


def test_public_ipv4_is_rejected(private_config):
    operator.settings()  # Genuine valid baseline before the explicit negative.
    configured(private_config, '8.8.8.8')
    with pytest.raises(ValueError, match='operator precheck failed'):
        operator.settings()


def test_wildcard_ipv4_is_rejected(private_config):
    operator.settings()
    configured(private_config, '0.0.0.0')
    with pytest.raises(ValueError, match='operator precheck failed'):
        operator.settings()


@pytest.mark.parametrize('address', [None, True, 0, [], {}, '', 'localhost',
    '127.0.0.2', '::1', '169.254.1.2', '100.64.1.2', '172.32.1.2',
    '192.0.0.1', '224.0.0.1', '10.01.2.3', ' 10.1.2.3', '10.1.2.3 ',
    '10.1.2.3\n', '10.1.2.3\x00', '10.1.2.3 127.0.0.1', '10.1.2.3{'])
def test_invalid_bind_types_and_non_rfc1918_forms_reject(private_config, address):
    configured(private_config, address)
    with pytest.raises(ValueError):
        operator.settings()


def test_optional_bind_does_not_allow_other_extra_keys(private_config):
    configured(private_config, '192.168.1.2', unexpected=True)
    with pytest.raises(ValueError, match='operator precheck failed'):
        operator.settings()


def test_private_bind_changes_only_caddy_environment(private_config):
    configured(private_config, '192.168.1.2')
    checked = admitted()
    backend, caddy = operator.environment(checked)
    expected_backend = {'PATH': '/usr/bin:/bin', 'HOME': str(checked['runtime']),
        'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1',
        'MTG_TRUSTED_ORIGINS': checked['origin']}
    assert backend == expected_backend
    assert caddy.get('MTG_FRONTEND_BIND') == '192.168.1.2'
    assert caddy['MTG_BACKEND_PORT'] == str(checked['backend_port'])
    assert caddy['MTG_SITE_ORIGIN'] == checked['origin']
    assert caddy['MTG_TLS_CERT'] == str(checked['cert'])
    assert caddy['MTG_TLS_KEY'] == str(checked['key'])
    assert caddy['MTG_AUTH_HASH'] == checked['password_hash']


def test_legacy_environment_exports_validated_loopback(private_config):
    backend, caddy = operator.environment(admitted())
    assert caddy.get('MTG_FRONTEND_BIND') == '127.0.0.1'
    assert 'MTG_FRONTEND_BIND' not in backend


def test_private_bind_retains_runtime_dist_containment(private_config):
    config = configured(private_config, '192.168.1.2')
    path = private_config[1]
    config['runtime'] = str(Path(config['dist']) / 'private/runtime')
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match='operator precheck failed'):
        operator.settings()


def test_caddy_bind_has_explicit_loopback_default():
    text = Path(__file__).with_name('Caddyfile').read_text()
    assert text.count('bind {$MTG_FRONTEND_BIND:127.0.0.1}') == 1
    assert 'reverse_proxy 127.0.0.1:{$MTG_BACKEND_PORT}' in text
    assert 'skip_install_trust' in text and 'admin off' in text
