"""Real two-process production HTTP scheduler/phase/choice restoration."""
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest

@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('mode', ['turn', 'phase', 'midphase', 'pending'])
def test_actual_http_queue_phase_and_private_choice_restart(seat, mode, tmp_path):
    root = tmp_path / 'restart'
    root.mkdir()
    worker = Path(__file__).with_name('queued_sequence_restart_worker.py')
    env = {**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[1]),
           'PYTHONDONTWRITEBYTECODE': '1'}
    for phase in ('seed', 'restore'):
        proc = subprocess.run([sys.executable, str(worker), phase, str(seat), mode, str(root)],
                              env=env, capture_output=True, text=True, timeout=60)
        (root / (phase + '.log')).write_text(proc.stdout + proc.stderr)
        assert proc.returncode == 0, proc.stdout + proc.stderr
    seed = json.loads((root / 'seed-evidence.json').read_text())
    restore = json.loads((root / 'restore-evidence.json').read_text())
    assert seed['pid'] != restore['pid']
    assert restore['restored_snapshot_config_rng_receipts_exact']
    assert restore['diagnostic_and_reads_root_sql_config_rng_exact']
    assert restore['idempotent_restore_does_not_duplicate_queue']
    assert restore['invalid_action_existing_queue_root_sql_rng_config_exact']
    assert restore['resume_did_not_repeat_resolution_or_entry']
