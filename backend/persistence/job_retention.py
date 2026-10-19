"""Standalone, explicit-path SQLite maintenance. Never imports the live engine.

Age AND keep compose conservatively: delete only rows strictly older than the
cutoff AND outside the newest keep terminal rows. Either rule may stand alone.
Known terminal statuses only; malformed/future finish times are protected.
"""
from __future__ import annotations

import math
from pathlib import Path
import re
import sqlite3
import stat
import time

TERMINAL = frozenset({"completed", "failed", "canceled"})
TABLE = "simulationjobrecord"
LOCAL_FILESYSTEMS = frozenset({"ext2", "ext3", "ext4", "xfs", "btrfs", "tmpfs", "overlay", "zfs"})


def local_path(value: str | Path, *, existing: bool = True) -> Path:
    """Fail closed on unknown/network mounts, symlinks and implicit paths (Linux)."""
    path = Path(value)
    if not path.is_absolute():
        raise ValueError("an absolute local path is required")
    resolved = path.resolve()
    if resolved != path:
        raise ValueError("symlinks and noncanonical paths are not allowed")
    if resolved == Path(__file__).resolve().parents[1] / "mtg_lab.db":
        raise ValueError("source-relative application database is forbidden; use an isolated copy")
    return _canonical_local_path(path, existing=existing)


def _canonical_local_path(value: str | Path, *, existing: bool = True) -> Path:
    """Shared path safety, not an offline maintenance default-DB allowance."""
    path = Path(value)
    if not path.is_absolute():
        raise ValueError("an absolute local path is required")
    resolved = path.resolve()
    if resolved != path:
        raise ValueError("symlinks and noncanonical paths are not allowed")
    mounts = []
    for line in Path("/proc/self/mountinfo").read_text().splitlines():
        left, right = line.split(" - ", 1)
        mount = Path(re.sub(r"\\([0-7]{3})", lambda m: chr(int(m[1], 8)), left.split()[4]))
        if resolved == mount or mount in resolved.parents:
            mounts.append((len(mount.parts), right.split()[0]))
    if not mounts or max(mounts)[1] not in LOCAL_FILESYSTEMS:
        raise ValueError("database must be on a recognized local filesystem")
    if existing and (not path.exists() or not stat.S_ISREG(path.stat().st_mode)):
        raise ValueError("database must be an existing regular file")
    if not existing and not path.parent.is_dir():
        raise ValueError("destination parent directory must already exist")
    return path


def _number(value, name, *, positive=False):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0 or (positive and value == 0):
        raise ValueError(f"{name} must be a finite {'positive' if positive else 'nonnegative'} number")
    return value


def _quote(name):
    return '"' + name.replace('"', '""') + '"'


def _linked_ids(conn):
    protected = set()
    for (table,) in conn.execute("SELECT name FROM sqlite_schema WHERE type='table'"):
        links = {}
        for fk in conn.execute(f"PRAGMA foreign_key_list({_quote(table)})"):
            if fk[2].lower() == TABLE:
                links.setdefault(fk[0], []).append(fk)
        for group in links.values():
            if len(group) != 1 or group[0][4] not in (None, "id"):
                raise ValueError("unsupported incoming job foreign key; refusing deletion")
            col = _quote(group[0][3])
            # Let SQLite use the parent's collation/affinity for FK equality.
            protected.update(row[0] for row in conn.execute(
                f"SELECT parent.id FROM simulationjobrecord AS parent "
                f"JOIN {_quote(table)} AS child ON parent.id = child.{col}"))
    return protected


def prune_jobs(database, *, max_age_seconds=None, keep=None, now=None,
               apply=False, timeout=5.0, protected_ids=()):
    """Plan and optionally delete in one transaction; exceptions roll everything back.

    Declared incoming FKs are protected even when CASCADE/SET NULL is configured.
    Current application schemas have no incoming job links. Future logical/JSON
    links must be supplied via protected_ids or integrated before deployment.
    This does not coordinate the API's in-memory cache or retain retry tombstones.
    """
    if type(apply) is not bool:
        raise ValueError("apply must be boolean")
    if keep is not None and (type(keep) is not int or keep < 0):
        raise ValueError("keep must be a nonnegative integer")
    if max_age_seconds is not None:
        _number(max_age_seconds, "max_age_seconds", positive=True)
    if keep is None and max_age_seconds is None:
        raise ValueError("at least one retention rule is required")
    now = _number(time.time() if now is None else now, "now")
    _number(timeout, "timeout")
    if isinstance(protected_ids, (str, bytes)):
        raise ValueError("protected_ids must be an iterable of job IDs")
    protected = set(protected_ids)
    if any(type(value) is not str or not value for value in protected):
        raise ValueError("protected_ids must contain nonempty strings")
    path = local_path(database)
    conn = sqlite3.connect(path.as_uri() + ("?mode=rw" if apply else "?mode=ro"), uri=True, timeout=timeout)
    try:
        conn.execute("PRAGMA trusted_schema=OFF")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("BEGIN IMMEDIATE" if apply else "BEGIN")
        if apply and conn.execute("SELECT 1 FROM sqlite_schema WHERE type='table' AND lower(name) IN ('resourcecapacity','resourcereservation')").fetchone():
            raise ValueError('Accounted database requires owned retirement; retry identities must be retained')
        if conn.execute("SELECT 1 FROM sqlite_schema WHERE type='trigger' AND lower(tbl_name)=?", (TABLE,)).fetchone():
            raise ValueError("job table has triggers; refusing maintenance")
        if conn.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("preexisting foreign-key violation; refusing maintenance")
        protected |= _linked_ids(conn)
        rows = conn.execute("SELECT id, status, finished_at FROM simulationjobrecord").fetchall()
        terminal = []
        reasons = {}
        for job_id, status, finish in rows:
            if status not in TERMINAL:
                reasons[job_id] = "active_or_unknown_status"
            elif type(finish) not in (float, int) or not math.isfinite(finish) or not 0 <= finish <= now:
                reasons[job_id] = "invalid_or_future_finished_at"
            else:
                terminal.append((finish, job_id))
        terminal.sort(reverse=True)  # stable tie break: descending ID
        candidates = []
        for index, (finish, job_id) in enumerate(terminal):
            if job_id in protected:
                reasons[job_id] = "linked_or_explicitly_protected"
            elif keep is not None and index < keep:
                reasons[job_id] = "keep_recent"
            elif max_age_seconds is not None and finish >= now - max_age_seconds:
                reasons[job_id] = "within_age_limit"
            else:
                candidates.append(job_id)
        if apply:
            before = conn.total_changes
            for job_id in candidates:
                if conn.execute("DELETE FROM simulationjobrecord WHERE id=?", (job_id,)).rowcount != 1:
                    raise RuntimeError("deletion count mismatch")
            # Includes SQLite FK actions: no collateral change may commit.
            if conn.total_changes - before != len(candidates):
                raise RuntimeError("unexpected collateral writes; rolling back")
            conn.commit()
        else:
            conn.rollback()
        return {"database": str(path), "applied": apply, "now": now,
                "max_age_seconds": max_age_seconds, "keep": keep,
                "total_count": len(rows), "candidate_count": len(candidates),
                "candidate_ids": candidates, "deleted_count": len(candidates) if apply else 0,
                "deleted_ids": candidates if apply else [], "protected_count": len(reasons),
                "protected": dict(sorted(reasons.items()))}
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
