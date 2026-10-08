"""Actual configuration function in isolation: no engine import or SQL access."""
import ast
from pathlib import Path
from types import SimpleNamespace

import pytest


def configure(default, values):
    source = Path(__file__).resolve().parents[1] / 'persistence/db.py'
    node = next(n for n in ast.parse(source.read_text()).body
                if isinstance(n, ast.FunctionDef) and n.name == 'configured_database_path')
    namespace = dict(Path=Path, os=SimpleNamespace(environ=values),
                     DEFAULT_DATABASE_PATH=default, __file__=str(source))
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), namespace)
    return namespace['configured_database_path']()


def test_unset_operator_path_preserves_original_default(tmp_path):
    default = tmp_path / 'legacy.txt'
    assert configure(default, {}) == default


@pytest.mark.parametrize('value', ['', ' ', '/tmp/x ', ' /tmp/x', '../db',
                                  'file::memory:?cache=shared', ':memory:'])
def test_invalid_operator_path_is_rejected_without_engine_creation(tmp_path, value):
    with pytest.raises(ValueError):
        configure(tmp_path / 'legacy.txt', {'MTG_DATABASE_PATH': value})


def test_explicit_new_external_local_path_with_no_legacy_file(tmp_path):
    candidate = tmp_path / 'new.txt'
    assert configure(tmp_path / 'legacy.txt', {'MTG_DATABASE_PATH': str(candidate)}) == candidate
    assert not candidate.exists()


def test_source_tree_path_is_not_an_operator_database(tmp_path):
    source = Path(__file__).resolve().parents[1] / 'operator-db.txt'
    with pytest.raises(ValueError, match='outside the source tree'):
        configure(tmp_path / 'legacy.txt', {'MTG_DATABASE_PATH': str(source)})
    assert not source.exists()


def test_legacy_file_is_not_silently_abandoned_for_empty_new_path(tmp_path):
    legacy = tmp_path / 'legacy.txt'
    legacy.write_text('non-SQL fixture: only path presence is under test')
    with pytest.raises(ValueError, match='relocate and verify'):
        configure(legacy, {'MTG_DATABASE_PATH': str(tmp_path / 'new.txt')})
    assert legacy.read_text() == 'non-SQL fixture: only path presence is under test'


def test_explicit_existing_external_regular_path_is_accepted(tmp_path):
    legacy = tmp_path / 'legacy.txt'
    legacy.write_text('non-SQL fixture')
    relocated = tmp_path / 'relocated.txt'
    relocated.write_text('non-SQL fixture')
    assert configure(legacy, {'MTG_DATABASE_PATH': str(relocated)}) == relocated


def test_symlink_external_path_remains_rejected(tmp_path):
    target = tmp_path / 'target.txt'
    target.write_text('non-SQL fixture')
    link = tmp_path / 'alias.txt'
    link.symlink_to(target)
    with pytest.raises(ValueError, match='symlinks and noncanonical'):
        configure(tmp_path / 'legacy.txt', {'MTG_DATABASE_PATH': str(link)})
