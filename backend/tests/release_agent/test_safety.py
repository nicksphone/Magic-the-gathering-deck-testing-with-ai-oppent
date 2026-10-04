import json
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

import pytest
from persistence.job_retention import local_path, prune_jobs
from tests.release_agent.test_retention import db, add, ids  # noqa: F401


def test_partial_delete_error_rolls_back_every_row(db, monkeypatch):
    add(db, "first")
    add(db, "second")
    original = sqlite3.connect
    class FailingConnection(sqlite3.Connection):
        deletions = 0
        def execute(self, sql, *args):
            if sql.startswith("DELETE FROM simulationjobrecord"):
                self.deletions += 1
                if self.deletions == 2:
                    raise sqlite3.OperationalError("injected disk I/O error on second delete")
            return super().execute(sql, *args)
    with monkeypatch.context() as patcher:
        patcher.setattr(sqlite3, "connect", lambda *a, **k: original(*a, **k, factory=FailingConnection))
        with pytest.raises(sqlite3.OperationalError, match="disk I/O"):
            prune_jobs(db, keep=0, apply=True)
    assert ids(db) == ["first", "second"]


def test_unrelated_application_records_are_unchanged(tmp_path):
    from scripts.verify_storage_restore import create_fixture, fingerprint
    db = tmp_path / "all-records.db"
    create_fixture(db)
    with closing(sqlite3.connect(db)) as c:
        before = fingerprint(c)
    assert prune_jobs(db, keep=0, apply=True)["deleted_ids"] == ["fixture-job"]
    with closing(sqlite3.connect(db)) as c:
        after = fingerprint(c)
    before["tables"].pop("simulationjobrecord")
    after["tables"].pop("simulationjobrecord")
    assert before == after


def test_paths_and_cli_are_explicit_and_dry_by_default(db, tmp_path):
    add(db, "old")
    cmd = [sys.executable, "-m", "scripts.prune_simulation_jobs"]
    assert subprocess.run(cmd + ["--keep", "0"], capture_output=True).returncode == 2
    result = subprocess.run(cmd + ["--database", str(db), "--keep", "0"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["candidate_ids"] == ["old"]
    assert ids(db) == ["old"]
    result = subprocess.run(cmd + ["--database", str(db), "--keep", "-1", "--apply"], capture_output=True, text=True)
    assert result.returncode == 1 and json.loads(result.stderr)["ok"] is False
    alias = tmp_path / "alias.db"
    alias.symlink_to(db)
    with pytest.raises(ValueError, match="symlinks"):
        prune_jobs(alias, keep=0, apply=True)
    with pytest.raises(ValueError, match="absolute"):
        prune_jobs("relative.db", keep=0)
    import persistence.job_retention as module
    with pytest.raises(ValueError, match="source-relative"):
        local_path(Path(module.__file__).resolve().parents[1] / "mtg_lab.db")


def test_read_only_database_is_not_changed(db):
    add(db, "keep")
    db.chmod(0o400)
    try:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            prune_jobs(db, keep=0, apply=True)
        assert prune_jobs(db, keep=0)["candidate_ids"] == ["keep"]
    finally:
        db.chmod(0o600)


def test_network_filesystem_refusal(db, monkeypatch):
    original = Path.read_text
    def mounts(path, *a, **kw):
        if str(path) == "/proc/self/mountinfo":
            return "1 0 0:1 / / rw - nfs4 server:/share rw\n"
        return original(path, *a, **kw)
    monkeypatch.setattr(Path, "read_text", mounts)
    with pytest.raises(ValueError, match="local filesystem"):
        prune_jobs(db, keep=0, apply=True)
