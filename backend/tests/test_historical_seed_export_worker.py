"""The fixture CLI cannot fall through to production default output/database paths."""
import hashlib
from pathlib import Path
import subprocess
import sys


def test_fixture_worker_requires_explicit_paths_and_cannot_overwrite_seed():
    seed=Path(__file__).parents[1]/'card_data/builtin_oracle_seed.json'
    before=hashlib.sha256(seed.read_bytes()).hexdigest()
    run=subprocess.run([sys.executable,str(Path(__file__).with_name('historical_seed_export_worker.py'))],capture_output=True,text=True,timeout=15)
    assert run.returncode!=0 and 'Fixture CLI requires explicit isolated paths' in run.stderr
    assert hashlib.sha256(seed.read_bytes()).hexdigest()==before
