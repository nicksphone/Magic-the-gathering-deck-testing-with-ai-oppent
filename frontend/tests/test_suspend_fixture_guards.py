"""The dedicated fixture cannot import/start beside a Git source checkout."""
import os
from pathlib import Path
import subprocess


def test_normal_checkout_import_refused_before_sqlite_creation():
    root = Path(__file__).resolve().parents[2]
    database = root / 'backend/mtg_lab.db'
    before = database.read_bytes() if database.exists() else None
    code = ('import importlib.util;'
            f'spec=importlib.util.spec_from_file_location("suspend_fixture",{str(root / "frontend/tests/suspend_fixture_server.py")!r});'
            'module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)')
    env = {**os.environ, 'PYTHONPATH': str(root / 'backend'), 'PYTHONDONTWRITEBYTECODE': '1',
           'MTG_SUSPEND_FIXTURE_TOKEN': 'explicit-test-token', 'MTG_SUSPEND_FIXTURE_ROOT': str(root)}
    result = subprocess.run([os.sys.executable, '-c', code], env=env, capture_output=True, text=True, timeout=15)
    assert result.returncode != 0 and 'runner-owned disposable backend' in result.stderr
    assert (database.read_bytes() if database.exists() else None) == before
