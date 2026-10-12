"""Execute the packaging probe's actual guard without backend or SQLite imports."""
import ast
import importlib.util
from pathlib import Path
import re
import unittest


def projected_guard():
    path = Path(__file__).with_name('release_media_packaging_probe.py')
    tree = ast.parse(path.read_text())
    run = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'run')
    guard = next(node for node in run.body if isinstance(node, ast.FunctionDef) and node.name == 'guard')
    helper_path = path.with_name('import_identity_sql_support.py')
    spec = importlib.util.spec_from_file_location('packaging_sql_decoder_controls', helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    backend = path.resolve().parents[1]
    namespace = {'Path': Path, 're': re, 'backend': backend,
                 'database': backend / 'mtg_lab.db', 'network': [],
                 'sqlite_guard_value': helper.sqlite_guard_value}
    exec(compile(ast.Module(body=[guard], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace['guard'], namespace['database']


class PackagingSQLGuardTests(unittest.TestCase):
    def test_actual_probe_accepts_canonical_database_and_capacity_backup_forms(self):
        guard, database = projected_guard()
        backup = database.with_name(database.name + '.before-capacity-' + 'a' * 32 + '.db')
        for value in (':memory:', str(database), database.as_uri() + '?mode=ro',
                      str(backup), backup.as_uri() + '?mode=ro'):
            with self.subTest(value=value):
                guard('sqlite3.connect', (value,))

    def test_actual_probe_rejects_foreign_write_alias_query_and_unrelated_database(self):
        guard, database = projected_guard()
        outside = database.parent.parent / database.name
        values = (str(outside), outside.as_uri() + '?mode=ro', 'mtg_lab.db',
                  database.as_uri() + '?mode=rw', database.as_uri() + '?mode=ro&cache=shared',
                  'file://foreign' + str(database) + '?mode=ro',
                  database.as_uri() + '?mode=ro#fragment',
                  str(database.parent / 'unrelated.db'),
                  str(database.with_name(database.name + '.before-capacity-invalid.db')),
                  str(database.parent / 'nested' / database.name))
        for value in values:
            with self.subTest(value=value), self.assertRaises(AssertionError):
                guard('sqlite3.connect', (value,))
        with self.assertRaises(AssertionError):
            guard('socket.connect', ())
