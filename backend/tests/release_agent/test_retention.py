"""Run from a disposable source copy; all databases belong to tmp_path."""
import sqlite3

import pytest
from sqlmodel import SQLModel, create_engine
from persistence import models  # noqa: F401
from persistence.job_retention import prune_jobs


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "fixture.db"
    engine = create_engine(f"sqlite:///{path}")
    SQLModel.metadata.create_all(engine)
    engine.dispose()
    return path


def add(db, name, status="completed", finished=10):
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO simulationjobrecord VALUES (?, ?, 1, 1, 1, ?, NULL, '{}', '{}')", (name, status, finished))


def ids(db):
    with sqlite3.connect(db) as c:
        return [r[0] for r in c.execute("SELECT id FROM simulationjobrecord ORDER BY id")]


def test_dry_run_order_boundary_keep_and_repeat(db):
    for name, finished in [("a", 10), ("b", 20), ("c", 20), ("d", 30)]:
        add(db, name, finished=finished)
    before = db.read_bytes()
    result = prune_jobs(db, max_age_seconds=80, keep=1, now=100)
    assert result["candidate_ids"] == ["a"]  # exact age boundary is retained
    assert result["deleted_count"] == 0 and db.read_bytes() == before
    assert prune_jobs(db, keep=2, now=100)["candidate_ids"] == ["b", "a"]
    result = prune_jobs(db, keep=2, now=100, apply=True)
    assert result["deleted_ids"] == ["b", "a"] and ids(db) == ["c", "d"]
    assert prune_jobs(db, keep=2, now=100, apply=True)["deleted_count"] == 0


@pytest.mark.parametrize("status", ["queued", "running", "cancelling", "canceling", "unknown"])
def test_active_and_unknown_protected(db, status):
    add(db, "active", status)
    add(db, "old", "canceled")
    assert prune_jobs(db, keep=0, now=100, apply=True)["deleted_ids"] == ["old"]
    assert ids(db) == ["active"]


def test_age_only_terminal_whitelist(db):
    for name, status, finish in [("older", "failed", 19), ("boundary", "canceled", 20), ("newer", "completed", 21)]:
        add(db, name, status, finish)
    result = prune_jobs(db, max_age_seconds=80, now=100, apply=True)
    assert result["deleted_ids"] == ["older"]
    assert ids(db) == ["boundary", "newer"]


@pytest.mark.parametrize("finished", [None, -1, float("inf"), "bad", 101])
def test_invalid_terminal_times_protected(db, finished):
    add(db, "bad", finished=finished)
    assert prune_jobs(db, keep=0, now=100, apply=True)["deleted_count"] == 0


@pytest.mark.parametrize("action", ["CASCADE", "SET NULL", "RESTRICT"])
def test_incoming_cascade_link_and_explicit_protection(db, action):
    for name in ["linked", "explicit", "delete"]:
        add(db, name)
    with sqlite3.connect(db) as c:
        c.execute(f"CREATE TABLE receipt (job TEXT REFERENCES simulationjobrecord(id) ON DELETE {action})")
        c.execute("INSERT INTO receipt VALUES ('linked')")
    r = prune_jobs(db, keep=0, now=100, protected_ids=["explicit"], apply=True)
    assert r["deleted_ids"] == ["delete"]
    assert ids(db) == ["explicit", "linked"]
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT job FROM receipt").fetchall() == [("linked",)]


@pytest.mark.parametrize("kwargs", [{}, {"keep": -1}, {"keep": True}, {"keep": 1.5}, {"max_age_seconds": 0}, {"max_age_seconds": float("nan")}, {"keep": 0, "now": -1}, {"keep": 0, "timeout": float("inf")}, {"keep": 0, "apply": "yes"}])
def test_invalid_configuration(db, kwargs):
    with pytest.raises(ValueError):
        prune_jobs(db, **kwargs)


def test_empty_missing_and_trigger_refusal(db, tmp_path):
    assert prune_jobs(db, keep=0)["candidate_count"] == 0
    with pytest.raises(ValueError):
        prune_jobs(tmp_path / "absent.db", keep=0, apply=True)
    add(db, "keep")
    with sqlite3.connect(db) as c:
        c.execute("CREATE TRIGGER surprise AFTER DELETE ON simulationjobrecord BEGIN DELETE FROM deckrecord; END")
    with pytest.raises(ValueError, match="trigger"):
        prune_jobs(db, keep=0, apply=True)
    assert ids(db) == ["keep"]


def test_lock_failure(db):
    add(db, "keep")
    with sqlite3.connect(db) as locked:
        locked.execute("BEGIN IMMEDIATE")
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            prune_jobs(db, keep=0, apply=True, timeout=0.01)
    assert ids(db) == ["keep"]


def test_commit_lock_failure_rolls_back_deletion(db):
    add(db, "keep")
    with sqlite3.connect(db) as reader:
        reader.execute("BEGIN")
        reader.execute("SELECT * FROM simulationjobrecord").fetchall()
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            prune_jobs(db, keep=0, apply=True, timeout=0.01)
        reader.rollback()
    assert ids(db) == ["keep"]
