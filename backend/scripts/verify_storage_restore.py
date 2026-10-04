"""Consistent local SQLite backup/restore verification, never a live-DB replacement.

Use module invocation from a disposable backend checkout. --fixture-directory
creates real supported application records; normal backup/restore is stdlib-only.
Only closed, verified artifacts may subsequently be archived on NFS.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import time

from persistence.job_retention import local_path, _number, _quote


def fingerprint(conn):
    """Check integrity and hash every stored row plus schema, without logging data."""
    if conn.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
        raise ValueError("SQLite integrity check failed")
    if conn.execute("PRAGMA foreign_key_check").fetchone():
        raise ValueError("SQLite foreign-key check failed")
    schema = conn.execute("SELECT type, name, tbl_name, sql FROM sqlite_schema ORDER BY type, name").fetchall()
    tables = {}
    for kind, name, _, sql in schema:
        if kind != "table":
            continue
        if sql and "CREATE VIRTUAL TABLE" in sql.upper():
            raise ValueError("virtual tables are not a supported recovery surface")
        columns = list(conn.execute(f"PRAGMA table_info({_quote(name)})"))
        order = ",".join(str(i + 1) for i in range(len(columns)))
        digest = hashlib.sha256()
        count = 0
        for row in conn.execute(f"SELECT * FROM {_quote(name)} ORDER BY {order}"):
            payload = repr(row).encode("utf-8")
            digest.update(len(payload).to_bytes(8, "big"))
            digest.update(payload)
            count += 1
        tables[name] = {"count": count, "sha256": digest.hexdigest()}
    return {"schema_sha256": hashlib.sha256(repr(schema).encode()).hexdigest(), "tables": tables}


def _vacant(path):
    if path.exists() or path.is_symlink() or any(Path(str(path) + suffix).exists() for suffix in ("-wal", "-shm", "-journal")):
        raise FileExistsError(f"destination or SQLite sidecar already exists: {path}")


def backup_database(source, destination, *, timeout=5.0):
    """Backup a stable read snapshot; reserve destination exclusively, clean failures.

    Paths must be in operator-controlled local directories. Concurrent renames or
    hostile directory writers are outside this standalone maintenance contract.
    """
    _number(timeout, "timeout", positive=True)
    source = local_path(source)
    destination = local_path(destination, existing=False)
    if source == destination:
        raise ValueError("source and destination must differ")
    _vacant(destination)
    reserved = False
    try:
        fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        reserved = True
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=timeout)) as src:
            src.execute("PRAGMA trusted_schema=OFF")
            src.execute("BEGIN")
            before = fingerprint(src)
            deadline = time.monotonic() + timeout
            def progress(status, remaining, total):
                if time.monotonic() > deadline:
                    raise TimeoutError("SQLite backup exceeded timeout")
            with closing(sqlite3.connect(destination, timeout=timeout)) as dst:
                src.backup(dst, pages=128, progress=progress, sleep=0.01)
                dst.execute("PRAGMA trusted_schema=OFF")
                if fingerprint(dst) != before:
                    raise ValueError("backup differs from source snapshot")
            src.rollback()
        # Force a reopen after all backup handles have closed.
        with closing(sqlite3.connect(destination.as_uri() + "?mode=ro", uri=True)) as verified:
            if fingerprint(verified) != before:
                raise ValueError("closed backup verification failed")
        return before
    except BaseException:
        if reserved:
            for suffix in ("", "-wal", "-shm", "-journal"):
                Path(str(destination) + suffix).unlink(missing_ok=True)
        raise


def verify_restore(source, backup, restore, *, timeout=5.0):
    """Create backup if source is supplied, then restore it to a new local path.

    Restore-only mode verifies the backup's self-consistency, not its provenance.
    A successful backup is retained if the later restore fails, for diagnosis.
    """
    _number(timeout, "timeout", positive=True)
    backup = local_path(backup, existing=source is None)
    restore = local_path(restore, existing=False)
    paths = [backup, restore]
    if source is not None:
        source = local_path(source)
        paths.append(source)
    if len(set(paths)) != len(paths):
        raise ValueError("source, backup and restore must be different paths")
    _vacant(restore)
    if source is not None:
        _vacant(backup)
        expected = backup_database(source, backup, timeout=timeout)
    else:
        expected = None
    actual = backup_database(backup, restore, timeout=timeout)
    if expected is not None and actual != expected:
        raise ValueError("restored database does not match verified backup")
    return {"verified": True, "source": str(source) if source else None,
            "backup": str(backup), "restore": str(restore), **actual,
            "scope": "schema/row equality and SQLite checks; application recovery is separately tested"}


def create_fixture(path):
    """Persist actual schema + serializer records, without importing main/live engine."""
    from sqlmodel import Session, SQLModel, create_engine
    from persistence.models import DeckRecord, ActiveMatchRecord, MatchStartReceipt, SimulationJobRecord, MatchRecord, StatsSnapshot
    import knowledge.models  # noqa: F401 -- register full current metadata
    from game_state.state import MatchFactory
    from game_state.serializers import serialize_match_snapshot

    path = local_path(path, existing=False)
    _vacant(path)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}")
    try:
        SQLModel.metadata.create_all(engine)
        deck = [{"quantity": 60, "card_name": "Island", "type_line": "Basic Land — Island", "mana_cost": ""}]
        state = MatchFactory.from_decks(deck, deck, seed=8128)
        state_json = serialize_match_snapshot(state)
        # Versioned by the current _controller_snapshot / _restore_active_matches
        # contract; release_agent tests actually reconstruct and compare both.
        controller = {"controllers": {"1": "human", "2": "human"}, "mode": "human_vs_human",
                      "deck_ids": [1, 1], "mainboards": {"1": deck, "2": deck},
                      "sideboards": {"1": [], "2": []}, "game_number": 1,
                      "current_game_recorded": False, "match_complete": False,
                      "best_of": state.best_of, "root_seed": 8128, "play_draw_chooser": state.active_player,
                      "sideboarded_players": [], "seen_opponent_types": {"1": [], "2": []},
                      "difficulties": {"1": "master", "2": "master"},
                      "archetypes": {"1": "Midrange", "2": "Midrange"}, "revision": 7,
                      "mutation_receipts": {"fixture-action": "fixture-fingerprint"}}
        with Session(engine) as session:
            session.add_all([
                DeckRecord(id=1, name="Storage fixture Island", mainboard_json=json.dumps(deck)),
                ActiveMatchRecord(id=state.id, state_json=json.dumps(state_json), controller_json=json.dumps(controller)),
                MatchStartReceipt(key="fixture-start", request_hash="fixture-request", match_id=state.id),
                SimulationJobRecord(id="fixture-job", status="completed", started_at=1, finished_at=2,
                                    completed_matches=1, total_matches=1, request_json=json.dumps({"seed": 8128}),
                                    result_json=json.dumps({"fixture": True, "matches": 1})),
                MatchRecord(deck_a_id=1, deck_b_id=1, winner="draw", mode="fixture", turns=1, log_json="[]"),
                StatsSnapshot(label="fixture", stats_json='{"fixture": true}'),
            ])
            session.commit()
        return {"match_id": state.id, "state": state_json, "controller": controller}
    finally:
        engine.dispose()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", help="optional existing isolated source; omit for restore-only")
    parser.add_argument("--backup")
    parser.add_argument("--restore")
    parser.add_argument("--fixture-directory", help="existing empty local directory for fixture/backup/restore")
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args(argv)
    try:
        if args.fixture_directory:
            if args.source or args.backup or args.restore:
                raise ValueError("fixture-directory cannot be combined with explicit file paths")
            folder = local_path(args.fixture_directory, existing=False)
            if not folder.is_dir() or any(folder.iterdir()):
                raise ValueError("fixture directory must exist and be empty")
            args.source, args.backup, args.restore = [folder / name for name in ("fixture.db", "backup.db", "restored.db")]
            _number(args.timeout, "timeout", positive=True)
            create_fixture(args.source)
        if not args.backup or not args.restore:
            raise ValueError("--backup and --restore are required without fixture-directory")
        report = verify_restore(args.source, args.backup, args.restore, timeout=args.timeout)
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(json.dumps({"ok": False, "error": str(exc), "error_type": type(exc).__name__}), file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, **report}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
