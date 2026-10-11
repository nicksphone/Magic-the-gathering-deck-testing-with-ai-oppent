"""Actual cold HTTP authorization/404 controls and interface-only source guards."""
import ast
import hashlib
import json
from pathlib import Path

import pytest

from tests.test_private_choice_http_restart import assert_restart_audit, fixture, server, stable

HERE = Path(__file__).parent
PREIMAGE = json.loads((HERE / 'fixtures/private_cold_http_interface/preimage.json').read_text())
REVIEWED_PINS = json.loads((HERE / 'fixtures/private_cold_http_interface/reviewed_25ef_pins.json').read_text())


def _assert_reviewed_restart_source(parsed):
    helpers = {'_audit_json', '_validate_restart_audit', 'stable', 'assert_restart_audit'}
    helper_nodes = [node for node in parsed.body if isinstance(node, ast.FunctionDef) and node.name in helpers]
    assert len(helper_nodes) == 4 and {node.name for node in helper_nodes} == helpers
    helper_ast = ast.dump(ast.Module(body=helper_nodes, type_ignores=[]), include_attributes=False)
    assert hashlib.sha256(helper_ast.encode()).hexdigest() == 'afc68bc6456e9d177335b51f7e1b4a7a381c48c105f3fbf67c127b8014d5537f'
    substitutions = [
        ("assert restored['pid'] != before['pid'] and stable(restored) == stable(before)",
         "assert restored['pid'] != before['pid'] and stable(restored, restart=True) == stable(before, restart=True)"),
        ("assert stable(server.audit(identifier)) == stable(before)",
         "assert stable(server.audit(identifier)) == stable(restored)"),
        ("assert final['pid'] != after['pid'] and stable(final) == stable(after)",
         "assert final['pid'] != after['pid'] and stable(final, restart=True) == stable(after, restart=True)"),
    ]
    replacements = {ast.dump(ast.parse(new).body[0]): ast.dump(ast.parse(old).body[0])
                    for old, new in substitutions}
    assertions = [ast.dump(node, include_attributes=False) for node in ast.walk(parsed)
                  if isinstance(node, ast.Assert)]
    assert all(assertions.count(new) == 1 for new in replacements)
    current = iter(replacements.get(value, value) for value in assertions)
    for old in PREIMAGE['assertions']:
        assert any(value == old for value in current)
    test = next(node for node in parsed.body if isinstance(node, ast.FunctionDef) and
                node.name == 'test_real_http_explicit_choice_privacy_stale_database_and_two_restarts')
    restart_ast = ast.dump(ast.parse('server.restart()').body[0])
    sites = [i for i, node in enumerate(test.body) if ast.dump(node) == restart_ast]
    assert len(sites) == 2
    for index, before, after in zip(sites, ('before', 'after'), ('restored', 'final')):
        assert ast.dump(test.body[index - 1]) == ast.dump(ast.parse('previous_process = server.proc').body[0])
        proof = (f'assert_restart_audit({before}, {after}, previous_pid=previous_process.pid, '
                 'current_pid=server.proc.pid, previous_returncode=previous_process.poll())')
        assert ast.dump(test.body[index + 2]) == ast.dump(ast.parse(proof).body[0])
    server_class = next(node for node in parsed.body if isinstance(node, ast.ClassDef) and node.name == 'Server')
    assert {node.name for node in server_class.body if isinstance(node, ast.FunctionDef)} == set(PREIMAGE['methods'])
    for node in server_class.body:
        if isinstance(node, ast.FunctionDef) and node.name != 'audit':
            assert ast.dump(node, include_attributes=False) == PREIMAGE['methods'][node.name]


def _assert_reviewed_source_pins(root, historical, reviewed):
    assert type(reviewed) is dict and set(reviewed) == {'base_commit', 'sources'}
    assert reviewed['base_commit'] == '25ef55eab50c587ee71c34f0609b324d943693f0'
    sources = reviewed['sources']
    assert type(sources) is dict and set(sources) == set(historical['unchanged'])
    for relative, entry in sources.items():
        assert type(entry) is dict and set(entry) == {'historical_sha256', 'git_25ef_sha256', 'approved_sha256', 'authority'}
        for key in ('historical_sha256', 'git_25ef_sha256', 'approved_sha256'):
            value = entry[key]
            assert type(value) is str and len(value) == 64 and set(value) <= set('0123456789abcdef')
        assert entry['historical_sha256'] == historical['unchanged'][relative]
        if relative == 'tests/private_choice_boundary_fixture_server.py':
            assert entry['authority'] == 'Epoch20 tar56f0 / Kepler review df7f'
            assert entry['git_25ef_sha256'] == '7babe0352fe20539480d7a8b3f46f2c5255e9860eacbbc1361aacb3e737d17c9'
            assert entry['approved_sha256'] == '711e6fd8cf528a5f032d852eb4cfd5805d97a5d37c54c9832a46d49ef27d7abb'
        else:
            assert entry['authority'] == 'public Git25ef'
            assert entry['approved_sha256'] == entry['git_25ef_sha256']
        assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == entry['approved_sha256']


def test_original_assertions_preserved_and_only_client_audit_changed():
    _assert_reviewed_restart_source(ast.parse((HERE / 'test_private_choice_http_restart.py').read_text()))


def test_production_fixture_servers_and_inheritance_unchanged():
    # Historical pins remain immutable; evolved sources have explicit separate authority.
    _assert_reviewed_source_pins(HERE.parent, PREIMAGE, REVIEWED_PINS)


@pytest.mark.parametrize('seat', [1, 2])
def test_cold_private_audit_auth_denial_and_public_unknown_id_are_pure(server, seat):
    data = fixture(server, 'officer', seat)
    identifier = data['id']
    before = server.audit(identifier)
    previous_process = server.proc
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
    assert_restart_audit(before, after, previous_pid=previous_process.pid,
                         current_pid=server.proc.pid, previous_returncode=previous_process.poll())
    assert after['pid'] != before['pid'] and stable(after, restart=True) == stable(before, restart=True)
    denied_status, _ = server.call(f'/fixture/private-choice/{identifier}/audit',
                                  headers={'X-Private-Choice-Fixture': 'invalid-test-token'})
    assert denied_status == 403
    assert stable(server.audit(identifier)) == stable(after)
    with pytest.raises(AssertionError):
        server.audit('unknown-saved-match-id')
    assert stable(server.audit(identifier)) == stable(after)
    rows = [json.loads(line) for line in (server.root / 'http-receipts.jsonl').read_text().splitlines()]
    assert any(row['route'] == '/matches/unknown-saved-match-id' and row['response_status'] == 404 for row in rows)
    assert not any(row['route'] == '/fixture/private-choice/unknown-saved-match-id/audit' for row in rows)
