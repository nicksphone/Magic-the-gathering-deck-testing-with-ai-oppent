"""Keep all application wheel hashes and runtime inventory aligned with the lock."""
import ast
from copy import deepcopy
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[3]


def lock_rows():
    rows = {}
    for line in (ROOT/'backend/requirements-py312-linux.lock').read_text().splitlines():
        if not line or line.startswith('#') or line.startswith('--'):
            continue
        match = re.fullmatch(r'([a-z0-9-]+)==([0-9.]+) --hash=sha256:([0-9a-f]{64})', line)
        assert match, line
        name, version, sha = match.groups()
        assert name not in rows
        rows[name] = (version, sha)
    return rows


def validate_inventory(rows, wheels):
    assert len(rows) == 28 and len(wheels) == 29
    assert set(rows) == set(wheels) - {'pip'}
    for name, (version, sha) in rows.items():
        wheel = wheels[name]
        assert (wheel['version'], wheel['sha256']) == (version, sha), name
        assert wheel['filename'].startswith(name.replace('-', '_')+'-'+version+'-'), name
        assert wheel['filename'].endswith('.whl')
        assert re.fullmatch('[0-9a-f]{64}', wheel['metadata_sha256'])
        assert type(wheel['bytes']) is int and wheel['bytes'] > 0


class ApplicationWheelLockTests(unittest.TestCase):
    def test_all_28_versions_and_hashes_match_wheel_inventory(self):
        validate_inventory(lock_rows(), json.loads((ROOT/'ops/ci/hosted-clean/python5/wheels.json').read_text())['wheel_rows'])

    def test_mismatched_wheel_hash_is_rejected(self):
        wheels = json.loads((ROOT/'ops/ci/hosted-clean/python5/wheels.json').read_text())['wheel_rows']
        changed = deepcopy(wheels)
        changed['opentelemetry-api']['sha256'] = '0'*64
        with self.assertRaises(AssertionError):
            validate_inventory(lock_rows(), changed)

    def test_runtime_package_names_are_exact_lock_closure(self):
        tree = ast.parse((ROOT/'.github/scripts/ci_backend_metadata.py').read_text())
        names = ast.literal_eval(next(n.value for n in tree.body if isinstance(n, ast.Assign)
                                      and any(isinstance(t, ast.Name) and t.id == 'RUNTIME_PACKAGES' for t in n.targets)))
        self.assertEqual(len(names), 28)
        self.assertEqual(set(names), set(lock_rows()))


if __name__ == '__main__':
    unittest.main()
