"""Actual owned worker launches, explicit source/data binding, and early denials."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from tests.test_favor_target_lifecycle_http import (
    base_client, client, repo,
    test_favor_actual_http_response_choice_atomic_sql_and_cold_continuation as exercise,
)

SOURCE = Path(__file__).resolve().parents[2]
BACKEND = SOURCE / 'backend'
WORKER = BACKEND / 'tests/favor_lifecycle_http_worker.py'


@pytest.mark.parametrize('repo', ['file'], indirect=True)
@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('mode', ['none', 'veil'])
def test_actual_paid_cold_choice_needs_no_inherited_audit_env(repo, client, seat, mode, tmp_path, monkeypatch):
    monkeypatch.delenv('MTG_ISOLATED_TEST_ROOT', raising=False)
    assert not tmp_path.resolve().is_relative_to(SOURCE)
    exercise(repo, client, seat, mode, tmp_path)


@pytest.mark.parametrize('fault,reason', [
    ('missing_marker', 'permit'), ('foreign_source', 'source'),
    ('escaped_database', 'paths'), ('changed_input', 'input'),
])
def test_actual_child_rejects_bad_binding_before_backend_or_sql(tmp_path, fault, reason):
    root = tmp_path / 'cold'
    root.mkdir()
    database = root / 'owned-test.sqlite'
    database.write_bytes(b'')
    expected = root / 'cold-expected.json'
    expected.write_text('{}')
    output = root / 'cold-actual.json'
    permit = root / '.favor-cold-owned.json'
    bound = {'version': 1, 'parent_pid': os.getpid(), 'root': str(root),
             'backend': str(BACKEND), 'worker_sha256': hashlib.sha256(WORKER.read_bytes()).hexdigest(),
             'database': str(database), 'expected': str(expected), 'output': str(output),
             'expected_sha256': hashlib.sha256(expected.read_bytes()).hexdigest()}
    if fault == 'foreign_source':
        bound['backend'] = str(SOURCE / 'foreign-backend')
    elif fault == 'escaped_database':
        database = tmp_path / 'escaped.sqlite'
        database.write_bytes(b'')
        bound['database'] = str(database)
    permit.write_text(json.dumps(bound, sort_keys=True))
    env = {key: value for key, value in os.environ.items() if key != 'MTG_ISOLATED_TEST_ROOT'}
    env.update(MTG_FAVOR_COLD_ROOT=str(root), MTG_FAVOR_COLD_SOURCE=str(SOURCE),
               MTG_FAVOR_COLD_PERMIT=str(permit),
               MTG_FAVOR_COLD_PERMIT_SHA256=hashlib.sha256(permit.read_bytes()).hexdigest())
    if fault == 'missing_marker':
        permit.unlink()
    elif fault == 'changed_input':
        expected.write_text('{"changed":true}')
    result = subprocess.run([sys.executable, str(WORKER), str(database), str(expected), str(output)],
                            cwd=BACKEND, env=env, capture_output=True, text=True, timeout=60)
    (tmp_path / 'negative-worker.log').write_text(result.stdout + result.stderr)
    assert result.returncode != 0
    assert 'FAVOR_COLD_DENY:' + reason in result.stderr
    assert 'OWN_COLD_PROJECT_IMPORT' not in result.stdout
    assert 'OWN_COLD_SQL_CONNECT' not in result.stdout
    assert not output.exists()
