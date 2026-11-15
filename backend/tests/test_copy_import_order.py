"""Use clean interpreters because pytest imports typing before test collection."""
import json
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize('mode', ['copying-first', 'typing-first', 'custom-reducer',
                                'preexisting-args-reducer', 'preexisting-kwargs-reducer'])
def test_native_copy_prefix_survives_stdlib_import_order(mode):
    worker = Path(__file__).with_name('copy_import_order_worker.py')
    result = subprocess.run([sys.executable, '-I', '-S', '-B', str(worker), mode],
                            stdin=subprocess.DEVNULL, capture_output=True, text=True,
                            timeout=15, check=False)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report['mode'] == mode and report['denied_events'] == []
