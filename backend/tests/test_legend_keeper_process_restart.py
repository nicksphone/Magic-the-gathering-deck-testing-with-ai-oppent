"""Fresh worker HTTP resume/replay; no eager-cache assumption or external socket."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('destination', ['library', 'exile'])
def test_real_http_keeper_replacement_distinct_processes(seat, destination, tmp_path):
    worker = Path(__file__).with_name('legend_keeper_restart_worker.py')
    pids = []
    for phase in ('seed', 'keeper', 'replacement'):
        result = subprocess.run([sys.executable, str(worker), phase, str(seat), destination, str(tmp_path)],
                                env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1',
                                     'PYTHONPATH': str(worker.parents[1])},
                                capture_output=True, text=True, timeout=120)
        (tmp_path / (phase + '.log')).write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stdout + result.stderr
        pids.append(json.loads((tmp_path / (phase + '.json')).read_text())['pid'])
    assert len(set(pids)) == 3
