"""Guard cold public lookup order and unchanged original worker assertions."""
import ast
import hashlib
import json
from pathlib import Path

import pytest

HERE = Path(__file__).parent
ORIGINAL = json.loads((HERE / 'fixtures/lazy_restart_worker_interfaces/preimages.json').read_text())
WORKERS = sorted(ORIGINAL['workers'])


@pytest.mark.parametrize('name', WORKERS)
def test_all_original_worker_assertion_asts_retained_in_order(name):
    parsed = ast.parse((HERE / name).read_text())
    current = iter(ast.dump(node, include_attributes=False) for node in ast.walk(parsed)
                   if isinstance(node, ast.Assert))
    for old in ORIGINAL['workers'][name]['assertions']:
        assert any(assertion == old for assertion in current), name


@pytest.mark.parametrize('name', WORKERS)
def test_discovery_and_matching_public_get_precede_saved_controller_inspection(name):
    parsed = ast.parse((HERE / name).read_text())
    key = ast.dump(ast.parse("saved['mid']", mode='eval').body, include_attributes=False)
    indexed = [node for node in ast.walk(parsed) if isinstance(node, ast.Subscript)
               and isinstance(node.value, ast.Attribute) and node.value.attr == 'ACTIVE_MATCHES'
               and ast.dump(node.slice, include_attributes=False) == key]
    assert len(indexed) == 1
    gets = [node for node in ast.walk(parsed) if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute) and node.func.attr == 'get'
            and isinstance(node.func.value, ast.Name) and node.func.value.id == 'client']
    discovery = [node for node in gets if node.args and isinstance(node.args[0], ast.Constant)
                 and node.args[0].value == '/matches']
    selected = [node for node in gets if node.args and isinstance(node.args[0], ast.BinOp)
                and isinstance(node.args[0].left, ast.Constant) and node.args[0].left.value == '/matches/'
                and ast.dump(node.args[0].right, include_attributes=False) == key]
    assert len(discovery) == 1
    before_inspection = [node for node in selected
                         if discovery[0].lineno < node.lineno < indexed[0].lineno]
    assert len(before_inspection) == 1
    assert not any(isinstance(node, ast.Attribute) and node.attr in {'_restore_active_matches', '_load_saved_match'}
                   for node in ast.walk(parsed))


def test_delegation_wrappers_and_already_adapted_library_worker_unchanged():
    for name, expected in ORIGINAL['unchanged_workers'].items():
        assert hashlib.sha256((HERE / name).read_bytes()).hexdigest() == expected


def test_production_main_and_repository_unchanged_from_copied_current_b():
    backend = HERE.parent
    for name, expected in ORIGINAL['production'].items():
        assert hashlib.sha256((backend / name).read_bytes()).hexdigest() == expected
