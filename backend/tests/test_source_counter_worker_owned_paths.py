"""Actual worker preimport projection: no project/dependency imports or SQL."""
import ast
import os
from pathlib import Path
from types import SimpleNamespace

import pytest


WORKER = Path(__file__).with_name('source_counter_http_restart_worker.py')


def preamble(tmp_path, monkeypatch, directory, declared='TMPDIR', invalid=None):
    work = tmp_path / 'work'
    source = work / 'source'
    script = source / 'backend/tests/worker.py'
    script.parent.mkdir(parents=True)
    temp = work / directory
    temp.mkdir(exist_ok=True)
    monkeypatch.setenv('MTG_ISOLATED_TEST_ROOT', str(source))
    for key in ('TMPDIR', 'PYTEST_DEBUG_TEMPROOT'):
        monkeypatch.delenv(key, raising=False)
    if declared:
        value = str(temp)
        if invalid == 'foreign':
            value = str(tmp_path)
        elif invalid == 'relative':
            value = directory
        elif invalid == 'symlink-root':
            link = work / 'link'
            link.symlink_to(temp, target_is_directory=True)
            value = str(link)
        monkeypatch.setenv(declared, value)
    database = temp / 'owned.sqlite'
    expected = temp / 'expected.json'
    if invalid == 'escape':
        database = work / 'foreign.sqlite'
    elif invalid == 'symlink-input':
        database.symlink_to(source / 'other.sqlite')
    tree = ast.parse(WORKER.read_text())
    prefix = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == 'fastapi.testclient':
            break
        # Isolate only the real preimport checks and guard; never install a
        # persistent audit hook in this test process or replace their logic.
        if isinstance(node, ast.Import) and any(x.name == 'sys' for x in node.names):
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and (
                isinstance(node.value.func, ast.Attribute) and node.value.func.attr == 'addaudithook'):
            continue
        prefix.append(node)
    namespace = {'__file__': str(script), 'sys': SimpleNamespace(
        argv=[str(script), str(database), str(expected)], path=[])}
    exec(compile(ast.Module(body=prefix, type_ignores=[]), str(WORKER), 'exec'), namespace)
    return namespace, database, work


@pytest.mark.parametrize('declared', ['TMPDIR', 'PYTEST_DEBUG_TEMPROOT'])
def test_declared_owned_ci_temp_and_sqlite_are_admitted(tmp_path, monkeypatch, declared):
    n, database, _ = preamble(tmp_path, monkeypatch, 'pytest-tmp', declared)
    n['guard']('sqlite3.connect', (str(database),))
    n['guard']('sqlite3.connect', (':memory:',))


def test_source_local_legacy_contract_still_works(tmp_path, monkeypatch):
    n, database, _ = preamble(tmp_path, monkeypatch, 'source', None)
    n['guard']('sqlite3.connect', (str(database),))


@pytest.mark.parametrize('invalid', ['foreign', 'relative', 'symlink-root', 'escape', 'symlink-input'])
def test_invalid_contracts_reject_before_dependency_import(tmp_path, monkeypatch, invalid):
    with pytest.raises(AssertionError):
        preamble(tmp_path, monkeypatch, 'pytest-tmp', invalid=invalid)


def test_undeclared_sibling_is_not_admitted(tmp_path, monkeypatch):
    with pytest.raises(AssertionError):
        preamble(tmp_path, monkeypatch, 'pytest-tmp', None)


def test_sqlite_and_network_guard_stay_strict(tmp_path, monkeypatch):
    n, _, work = preamble(tmp_path, monkeypatch, 'source', None)
    with pytest.raises(AssertionError):
        n['guard']('sqlite3.connect', (str(work / 'outside.sqlite'),))
    with pytest.raises(AssertionError):
        n['guard']('socket.connect', ())


@pytest.mark.parametrize('invalid', ['foreign', 'relative', 'symlink-root', 'symlink-input'])
def test_source_inputs_cannot_hide_invalid_declared_root_or_link(tmp_path, monkeypatch, invalid):
    with pytest.raises(AssertionError):
        preamble(tmp_path, monkeypatch, 'source', invalid=invalid)
