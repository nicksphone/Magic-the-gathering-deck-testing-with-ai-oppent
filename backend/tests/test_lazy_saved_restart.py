"""Separate acceptance of cold public HTTP, retaining original assertions."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from tests.test_match_recovery import game


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Index', 'Ponder'])
def test_cold_http_fresh_process_exact_original_continuation(seat, name, tmp_path):
    root = tmp_path / 'cold-restart'
    root.mkdir()
    worker = Path(__file__).with_name('lazy_saved_restart_worker.py')
    env = {**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[1]),
           'PYTHONDONTWRITEBYTECODE': '1'}
    for phase in ('seed', 'restore'):
        result = subprocess.run([sys.executable, str(worker), phase, str(seat), name, str(root)],
                                env=env, capture_output=True, text=True, timeout=90)
        (root / (phase + '.log')).write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stdout + result.stderr
    first = json.loads((root / 'seed-evidence.json').read_text())
    second = json.loads((root / 'restore-evidence.json').read_text())
    assert first['pid'] != second['pid']
    assert second['cold_http_loaded_only_requested_id']
    assert second['restored_snapshot_config_rng_exact']
    assert second['actual_order_draw_and_source_departure']


def test_explicit_eager_legacy_receipt_fixture_keeps_original_assertions(game, monkeypatch):
    import main
    from persistence.db import engine
    from persistence.repository import Repository
    from sqlmodel import Session
    from tests import test_match_recovery as original

    with Session(engine) as session:
        main._restore_active_matches(Repository(session))
    original.test_start_receipt_storage_failure_leaves_no_match_or_receipt(game, monkeypatch)
