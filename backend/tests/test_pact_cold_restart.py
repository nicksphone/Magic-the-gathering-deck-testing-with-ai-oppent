"""Real ASGI Pact choice survives two cold app starts on owned SQLite.

No application DB or source cache is used. This does not certify a live browser
or TCP connection across restart; pending-browser refresh has separate coverage.
"""
import json
import sqlite3
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("seat", [1, 2])
@pytest.mark.parametrize("option", ["pay", "decline"])
def test_pending_pact_and_accepted_receipt_survive_cold_app_processes(tmp_path, seat, option):
    backend = Path(__file__).resolve().parents[1]
    database = tmp_path / "pact.sqlite3"
    assert not database.exists()
    # Pre-create the owned file so the startup legacy-database guard (which fires for a
    # missing configured path whenever backend/mtg_lab.db exists) cannot depend on test order.
    sqlite3.connect(database).close()
    environment = {**os.environ, "MTG_DATABASE_PATH": str(database),
                   "PYTHONPATH": str(backend), "PYTHONDONTWRITEBYTECODE": "1"}
    worker = Path(__file__).with_name("pact_cold_restart_worker.py")
    result = {}
    for phase in ("seed", "resolve", "retry"):
        child = subprocess.run([sys.executable, "-B", str(worker), phase,
            str(database), str(seat), option, json.dumps(result)], cwd=backend,
            env=environment, capture_output=True, text=True, timeout=45)
        assert child.returncode == 0, child.stderr
        new = json.loads(child.stdout)
        if phase == "resolve":
            assert new["revision"] == result["revision"] + 1
            assert new["pending_revision"] == result["revision"]
            assert new["paid_count"] == int(option == "pay")
        if phase == "retry":
            assert new == result
        result = new
    assert result["retry_status"] == 200 and result["stale_status"] == 409
