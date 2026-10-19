"""Inert source-oracle regressions; no backend imports, SQL or actual server."""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def projected():
    tree = ast.parse((HERE / 'test_private_cold_http_interface.py').read_text())
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    for node in functions:
        node.decorator_list = []
    namespace = {'ast': ast, 'hashlib': hashlib, 'json': json, 'Path': Path,
                 'pytest': pytest, 'HERE': HERE,
                 'PREIMAGE': json.loads((HERE / 'fixtures/private_cold_http_interface/preimage.json').read_text())}
    pins = HERE / 'fixtures/private_cold_http_interface/reviewed_25ef_pins.json'
    if pins.exists():
        namespace['REVIEWED_PINS'] = json.loads(pins.read_text())
    exec(compile(ast.Module(body=functions, type_ignores=[]), '<actual-private-cold-guards>', 'exec'), namespace)
    return namespace


def helper(name):
    namespace = projected()
    assert callable(namespace.get(name)), 'Missing reviewed source contract guard'
    return namespace[name]


def legacy_source():
    return (HERE / 'test_private_choice_http_restart.py').read_text()


def test_actual_assertion_oracle_accepts_only_reviewed_adaptation():
    projected()['test_original_assertions_preserved_and_only_client_audit_changed']()


def test_actual_inherited_oracle_checks_explicit_current_reviewed_pins():
    projected()['test_production_fixture_servers_and_inheritance_unchanged']()


@pytest.mark.parametrize('old,new', [
    ("assert data['foreign_hand_id'] not in json.dumps(actor)", 'assert True'),
    ("assert after['revision'] == before['revision'] + 1", 'assert True'),
    ("assert status == 409 and stable(server.audit(identifier)) == stable(after)", 'assert True'),
    ("previous_returncode=previous_process.poll()", 'previous_returncode=0'),
    ("assert before['database_sha256'] != after['database_sha256']", 'assert True'),
    ("assert before['capacity_owner_epoch'] != after['capacity_owner_epoch']", 'assert True'),
    ('allow_nan=False', 'allow_nan=True'),
    ('previous_process = server.proc', 'previous_process = None'),
])
def test_oracle_rejects_weakened_gameplay_pair_or_actual_process_binding(old, new):
    check = helper('_assert_reviewed_restart_source')
    text = legacy_source()
    assert old in text
    with pytest.raises(AssertionError):
        check(ast.parse(text.replace(old, new)))


def fake_pins(root):
    path = root / 'main.py'
    path.write_bytes(b'public synthetic source\n')
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    historical = {'unchanged': {'main.py': '0' * 64}}
    current = {'base_commit': '25ef55eab50c587ee71c34f0609b324d943693f0',
               'sources': {'main.py': {'historical_sha256': '0' * 64,
                                      'git_25ef_sha256': sha, 'approved_sha256': sha,
                                      'authority': 'public Git25ef'}}}
    return historical, current


def test_explicit_inherited_pins_preserve_historical_operands(tmp_path):
    check = helper('_assert_reviewed_source_pins')
    historical, current = fake_pins(tmp_path)
    saved = deepcopy((historical, current))
    check(tmp_path, historical, current)
    assert (historical, current) == saved


@pytest.mark.parametrize('mutation', ['wrong_sha', 'wrong_historical', 'unknown_source',
                                     'missing_source', 'wrong_commit', 'unknown_authority',
                                     'ambient_git_substitute', 'unknown_field'])
def test_inherited_pin_guard_rejects_unadmitted_scope_or_bytes(tmp_path, mutation):
    check = helper('_assert_reviewed_source_pins')
    historical, current = fake_pins(tmp_path)
    entry = current['sources']['main.py']
    if mutation == 'wrong_sha':
        entry['approved_sha256'] = 'f' * 64
    elif mutation == 'wrong_historical':
        entry['historical_sha256'] = 'f' * 64
    elif mutation == 'unknown_source':
        current['sources']['foreign.py'] = dict(entry)
    elif mutation == 'missing_source':
        del current['sources']['main.py']
    elif mutation == 'wrong_commit':
        current['base_commit'] = '0' * 40
    elif mutation == 'unknown_authority':
        entry['authority'] = 'ambient current file'
    elif mutation == 'ambient_git_substitute':
        entry['git_25ef_sha256'] = 'f' * 64
    else:
        entry['unknown'] = None
    with pytest.raises(AssertionError):
        check(tmp_path, historical, current)
