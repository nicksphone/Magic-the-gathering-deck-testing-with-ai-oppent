"""Actual cold HTTP authorization/404 controls and interface-only source guards."""
import ast
import hashlib
import json
from pathlib import Path

import pytest

from tests.test_private_choice_http_restart import fixture, server, stable

HERE = Path(__file__).parent
PREIMAGE = json.loads((HERE / 'fixtures/private_cold_http_interface/preimage.json').read_text())


def test_original_assertions_preserved_and_only_client_audit_changed():
    parsed = ast.parse((HERE / 'test_private_choice_http_restart.py').read_text())
    current = iter(ast.dump(node, include_attributes=False) for node in ast.walk(parsed)
                   if isinstance(node, ast.Assert))
    for old in PREIMAGE['assertions']:
        assert any(value == old for value in current)
    server_class = next(node for node in parsed.body if isinstance(node, ast.ClassDef) and node.name == 'Server')
    for node in server_class.body:
        if isinstance(node, ast.FunctionDef) and node.name != 'audit':
            assert ast.dump(node, include_attributes=False) == PREIMAGE['methods'][node.name]


def test_production_fixture_servers_and_inheritance_unchanged():
    for relative, expected in PREIMAGE['unchanged'].items():
        assert hashlib.sha256((HERE.parent / relative).read_bytes()).hexdigest() == expected


@pytest.mark.parametrize('seat', [1, 2])
def test_cold_private_audit_auth_denial_and_public_unknown_id_are_pure(server, seat):
    data = fixture(server, 'officer', seat)
    identifier = data['id']
    before = server.audit(identifier)
    server.restart()
    denied_status, _ = server.call(f'/fixture/private-choice/{identifier}/audit',
                                  headers={'X-Private-Choice-Fixture': 'invalid-test-token'})
    assert denied_status == 403
    cold_status, _ = server.call(f'/fixture/private-choice/{identifier}/audit')
    assert cold_status == 404
    public_status, public = server.call(f'/matches/{identifier}')
    assert public_status == 200
    assert all('library' not in player for player in public['players'].values())
    after = server.audit(identifier)
    assert after['pid'] != before['pid'] and stable(after) == stable(before)
    denied_status, _ = server.call(f'/fixture/private-choice/{identifier}/audit',
                                  headers={'X-Private-Choice-Fixture': 'invalid-test-token'})
    assert denied_status == 403
    assert stable(server.audit(identifier)) == stable(before)
    with pytest.raises(AssertionError):
        server.audit('unknown-saved-match-id')
    assert stable(server.audit(identifier)) == stable(before)
    rows = [json.loads(line) for line in (server.root / 'http-receipts.jsonl').read_text().splitlines()]
    assert any(row['route'] == '/matches/unknown-saved-match-id' and row['response_status'] == 404 for row in rows)
    assert not any(row['route'] == '/fixture/private-choice/unknown-saved-match-id/audit' for row in rows)
