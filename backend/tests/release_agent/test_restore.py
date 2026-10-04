"""SQLite backup API and application restoration tests; never use live storage."""
import errno
import json
import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

import pytest
from sqlmodel import Session, create_engine
from scripts.verify_storage_restore import backup_database, create_fixture, verify_restore, fingerprint


def test_fixture_backup_restore_and_actual_controller(tmp_path):
    source, backup, restore = [tmp_path / n for n in ("source.db", "backup.db", "restore.db")]
    expected = create_fixture(source)
    result = verify_restore(source, backup, restore)
    assert result["verified"]
    assert result["tables"]["deckrecord"]["count"] == 1
    import main
    from persistence.repository import Repository
    from game_state.serializers import serialize_match_snapshot
    engine = create_engine(f"sqlite:///{restore}")
    try:
        with Session(engine) as session:
            repo = Repository(session)
            main._restore_active_matches(repo, expected["match_id"])
            match = main.ACTIVE_MATCHES.pop(expected["match_id"])
            assert match.root_seed == 8128 and match.revision == 7
            assert match.mutation_receipts == {"fixture-action": "fixture-fingerprint"}
            assert serialize_match_snapshot(match.state) == expected["state"]
            assert main._controller_snapshot(match) == expected["controller"]
            assert repo.get_match_start_receipt("fixture-start").match_id == match.state.id
            assert json.loads(repo.get_simulation_job("fixture-job").request_json)["seed"] == 8128
    finally:
        engine.dispose()


def test_wal_committed_records_are_backed_up(tmp_path):
    source, backup = tmp_path / "wal.db", tmp_path / "backup.db"
    with closing(sqlite3.connect(source)) as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("CREATE TABLE sample (id PRIMARY KEY, value)")
        c.execute("INSERT INTO sample VALUES (1, 'committed in WAL')")
        c.commit()
        assert Path(str(source) + "-wal").exists()
        backup_database(source, backup)
        with closing(sqlite3.connect(backup)) as restored:
            assert restored.execute("SELECT value FROM sample").fetchone()[0] == "committed in WAL"


def test_missing_corrupt_and_destination_collision(tmp_path):
    source, backup = tmp_path / "source.db", tmp_path / "backup.db"
    with pytest.raises(ValueError):
        backup_database(source, backup)
    assert not backup.exists()
    source.write_bytes(b"not sqlite")
    with pytest.raises(sqlite3.DatabaseError):
        backup_database(source, backup)
    assert not backup.exists()
    source.unlink()
    create_fixture(source)
    backup.write_bytes(b"do not replace")
    with pytest.raises(FileExistsError):
        backup_database(source, backup)
    assert backup.read_bytes() == b"do not replace"
    with pytest.raises(ValueError):
        verify_restore(source, tmp_path / "new.db", source)
    assert not (tmp_path / "new.db").exists()


def test_backup_exclusive_lock_has_bounded_failure(tmp_path):
    source, backup = tmp_path / "source.db", tmp_path / "backup.db"
    create_fixture(source)
    with closing(sqlite3.connect(source)) as c:
        c.execute("BEGIN EXCLUSIVE")
        with pytest.raises((sqlite3.OperationalError, TimeoutError)):
            backup_database(source, backup, timeout=0.02)
        c.rollback()
    assert not backup.exists()


def test_failed_write_cleans_only_own_output(tmp_path, monkeypatch):
    source, backup = tmp_path / "source.db", tmp_path / "backup.db"
    create_fixture(source)
    def fail(*args, **kwargs):
        raise OSError(errno.ENOSPC, "injected disk full")
    monkeypatch.setattr(os, "open", fail)
    with pytest.raises(OSError, match="disk full"):
        backup_database(source, backup)
    assert source.exists() and not backup.exists()


def test_failed_backup_after_reservation_cleanup(tmp_path, monkeypatch):
    source, backup = tmp_path / "source.db", tmp_path / "backup.db"
    create_fixture(source)
    from scripts import verify_storage_restore as module
    def fail(*args):
        raise sqlite3.DatabaseError("injected verification failure")
    monkeypatch.setattr(module, "fingerprint", fail)
    with pytest.raises(sqlite3.DatabaseError, match="verification failure"):
        backup_database(source, backup)
    assert not backup.exists()


def test_foreign_key_violation_is_not_verified(tmp_path):
    source, backup = tmp_path / "source.db", tmp_path / "backup.db"
    with closing(sqlite3.connect(source)) as c:
        c.executescript("CREATE TABLE parent(id PRIMARY KEY); CREATE TABLE child(id REFERENCES parent(id)); INSERT INTO child VALUES(1);")
    with pytest.raises(ValueError, match="foreign"):
        backup_database(source, backup)
    assert not backup.exists()


def test_cli_error_and_restore_only(tmp_path):
    backup, restored = tmp_path / "backup.db", tmp_path / "restored.db"
    cmd = [sys.executable, "-m", "scripts.verify_storage_restore", "--backup", str(backup), "--restore", str(restored)]
    missing = subprocess.run(cmd, capture_output=True, text=True)
    assert missing.returncode == 1 and json.loads(missing.stderr)["ok"] is False
    create_fixture(backup)
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["verified"]
    assert subprocess.run(cmd, capture_output=True).returncode == 1


def test_corrupt_backup_cli_nonzero(tmp_path):
    backup = tmp_path / "bad.db"
    backup.write_bytes(b"corrupt SQLite fixture")
    result = subprocess.run([sys.executable, "-m", "scripts.verify_storage_restore",
                             "--backup", str(backup), "--restore", str(tmp_path / "new.db")],
                            capture_output=True, text=True)
    assert result.returncode == 1
    assert json.loads(result.stderr)["error_type"] == "DatabaseError"
    assert not (tmp_path / "new.db").exists()


def test_backup_timeout_and_sidecar_collision(tmp_path):
    source, backup = tmp_path / "source.db", tmp_path / "backup.db"
    create_fixture(source)
    with pytest.raises(TimeoutError, match="timeout"):
        backup_database(source, backup, timeout=0.000000001)
    assert not backup.exists()
    sidecar = Path(str(backup) + "-wal")
    sidecar.write_bytes(b"do not touch")
    with pytest.raises(FileExistsError):
        backup_database(source, backup)
    assert sidecar.read_bytes() == b"do not touch" and not backup.exists()


def test_backup_actual_unwritable_parent(tmp_path):
    source = tmp_path / "source.db"
    create_fixture(source)
    folder = tmp_path / "readonly"
    folder.mkdir()
    folder.chmod(0o500)
    try:
        with pytest.raises(PermissionError):
            backup_database(source, folder / "new.db")
    finally:
        folder.chmod(0o700)
    assert not (folder / "new.db").exists()
