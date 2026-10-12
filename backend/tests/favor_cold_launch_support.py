"""Explicit per-child test inputs; never reuse a global audit root."""
import hashlib
import json
import os
from pathlib import Path


def cold_environment(root, database, expected, output):
    root = Path(root).resolve()
    backend = Path(__file__).resolve().parents[1]
    worker = backend / 'tests/favor_lifecycle_http_worker.py'
    bound = {'version': 1, 'parent_pid': os.getpid(), 'root': str(root),
             'backend': str(backend), 'worker_sha256': hashlib.sha256(worker.read_bytes()).hexdigest(),
             'database': str(Path(database).resolve()), 'expected': str(Path(expected).resolve()),
             'output': str(Path(output).resolve()),
             'expected_sha256': hashlib.sha256(Path(expected).read_bytes()).hexdigest()}
    permit = root / '.favor-cold-owned.json'
    permit.write_text(json.dumps(bound, sort_keys=True))
    permit.chmod(0o600)
    return {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1',
            'MTG_FAVOR_COLD_ROOT': str(root), 'MTG_FAVOR_COLD_SOURCE': str(backend.parent),
            'MTG_FAVOR_COLD_PERMIT': str(permit),
            'MTG_FAVOR_COLD_PERMIT_SHA256': hashlib.sha256(permit.read_bytes()).hexdigest()}
