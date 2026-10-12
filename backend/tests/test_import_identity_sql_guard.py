"""Source-extracted ACTUAL worker guard, without executing worker/game setup."""
import ast
from pathlib import Path

import pytest


def guard(root):
    path = Path(__file__).with_name('import_identity_fix_worker.py')
    tree = ast.parse(path.read_text())
    run = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run')
    fn = next(n for n in run.body if isinstance(n, ast.FunctionDef) and n.name == 'audit')
    namespace = {'Path': Path, 'root': root}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace['audit']


@pytest.mark.parametrize('kind', ['memory', 'plain', 'readonly'])
def test_actual_worker_guard_accepts_only_owned_supported_sql_forms(tmp_path, kind):
    owned = tmp_path / 'owned.sqlite'
    value = {'memory': ':memory:', 'plain': str(owned),
             'readonly': owned.as_uri() + '?mode=ro'}[kind]
    guard(tmp_path)('sqlite3.connect', (value,))


@pytest.mark.parametrize('kind', ['outside_plain', 'outside_uri', 'write_uri', 'authority',
                                 'extra_query', 'relative', 'symlink'])
def test_actual_worker_guard_rejects_unowned_or_nonreadonly_uri(tmp_path, kind):
    owned, outside = tmp_path / 'owned.sqlite', tmp_path.parent / 'outside.sqlite'
    link = tmp_path / 'alias.sqlite'
    link.symlink_to(owned)
    value = {'outside_plain': str(outside), 'outside_uri': outside.as_uri() + '?mode=ro',
             'write_uri': owned.as_uri() + '?mode=rw',
             'authority': 'file://foreign' + str(owned) + '?mode=ro',
             'extra_query': owned.as_uri() + '?mode=ro&cache=shared',
             'relative': 'owned.sqlite', 'symlink': str(link)}[kind]
    with pytest.raises(AssertionError):
        guard(tmp_path)('sqlite3.connect', (value,))
