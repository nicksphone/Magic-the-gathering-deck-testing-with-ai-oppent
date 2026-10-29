"""Cooperative backup deadlines on tiny synthetic SQLite data, never user records."""
from contextlib import closing
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest

from scripts import verify_storage_restore as storage


@pytest.fixture
def databases(tmp_path):
    source, destination = tmp_path / 'source.db', tmp_path / 'backup.db'
    with closing(sqlite3.connect(source)) as conn:
        conn.execute('CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT)')
        conn.executemany('INSERT INTO sample VALUES (?, ?)', [(1, 'first'), (2, 'second')])
        conn.commit()
    return source, destination


def late_copy(monkeypatch, destination, *, corrupt=None, early_status=None):
    clock, fingerprints, events = [0.0], [], []
    connect, fingerprint = sqlite3.connect, storage.fingerprint
    monkeypatch.setattr(storage, 'time', SimpleNamespace(monotonic=lambda: clock[0]))

    def change(conn):
        conn.execute("UPDATE sample SET value='changed' WHERE id=1")
        conn.commit()

    class Connection(sqlite3.Connection):
        def backup(self, target, **kwargs):
            progress = kwargs['progress']
            if early_status is not None:
                clock[0] = 4.0
                progress(early_status, 2, 2)

            def completed(status, remaining, total):
                events.append((status, remaining, total))
                clock[0] = 6.0
                return progress(status, remaining, total)

            kwargs['progress'] = completed
            result = super().backup(target, **kwargs)
            if corrupt == 'destination':
                change(target)
            return result

    def opened(path, *args, **kwargs):
        if corrupt == 'reopen' and str(path) == destination.as_uri() + '?mode=ro':
            with closing(connect(destination)) as conn:
                change(conn)
        return connect(path, *args, **kwargs, factory=Connection)

    def checked(conn):
        fingerprints.append(Path(conn.execute('PRAGMA database_list').fetchone()[2]))
        return fingerprint(conn)

    monkeypatch.setattr(sqlite3, 'connect', opened)
    monkeypatch.setattr(storage, 'fingerprint', checked)
    return fingerprints, events


def test_late_native_done_still_verifies_destination_and_reopen(databases, monkeypatch):
    source, destination = databases
    before = source.read_bytes()
    with closing(sqlite3.connect(source)) as conn:
        expected = storage.fingerprint(conn)
    fingerprints, events = late_copy(monkeypatch, destination)
    assert storage.backup_database(source, destination) == expected
    assert fingerprints == [source, destination, destination]
    assert events[-1][0:2] == (sqlite3.SQLITE_DONE, 0)
    assert source.read_bytes() == before
    with closing(sqlite3.connect(destination)) as conn:
        assert conn.execute('SELECT * FROM sample ORDER BY id').fetchall() == [(1, 'first'), (2, 'second')]


@pytest.mark.parametrize('phase,message', [
    ('destination', 'backup differs from source snapshot'),
    ('reopen', 'closed backup verification failed'),
])
def test_late_done_does_not_bypass_verification_or_cleanup(databases, monkeypatch, phase, message):
    source, destination = databases
    before = source.read_bytes()
    fingerprints, events = late_copy(monkeypatch, destination, corrupt=phase)
    with pytest.raises(ValueError, match=message):
        storage.backup_database(source, destination)
    assert fingerprints == [source, destination] + ([destination] if phase == 'reopen' else [])
    assert events[-1][0:2] == (sqlite3.SQLITE_DONE, 0)
    assert source.read_bytes() == before
    assert not destination.exists()
    assert not any(Path(str(destination) + suffix).exists() for suffix in ('-wal', '-shm', '-journal'))


@pytest.mark.parametrize('failing_call', [1, 2, 3], ids=['source', 'destination', 'reopen'])
def test_verification_exceptions_retain_identity_and_clean_output(databases, monkeypatch, failing_call):
    source, destination = databases
    before = source.read_bytes()
    _, events = late_copy(monkeypatch, destination)
    fingerprint, calls = storage.fingerprint, []
    failure = sqlite3.DatabaseError('injected verification failure')

    def checked(conn):
        calls.append(True)
        if len(calls) == failing_call:
            raise failure
        return fingerprint(conn)

    monkeypatch.setattr(storage, 'fingerprint', checked)
    with pytest.raises(sqlite3.DatabaseError) as caught:
        storage.backup_database(source, destination)
    assert caught.value is failure and len(calls) == failing_call
    if failing_call == 1:
        assert not events
    else:
        assert events[-1][0:2] == (sqlite3.SQLITE_DONE, 0)
    assert source.read_bytes() == before and not destination.exists()


@pytest.mark.parametrize('status,remaining', [
    (sqlite3.SQLITE_OK, 1), (sqlite3.SQLITE_BUSY, 1), (sqlite3.SQLITE_LOCKED, 1),
    (sqlite3.SQLITE_DONE, 1), (sqlite3.SQLITE_OK, 0),
], ids=['unfinished', 'busy', 'locked', 'done-with-pages', 'zero-pages-not-done'])
def test_expired_unfinished_backup_still_times_out(databases, monkeypatch, status, remaining):
    source, destination = databases
    before, clock = source.read_bytes(), [0.0]
    connect = sqlite3.connect

    class Connection(sqlite3.Connection):
        def backup(self, target, **kwargs):
            clock[0] = 6.0
            kwargs['progress'](status, remaining, 2)
            pytest.fail('An expired unfinished backup was allowed to continue')

    monkeypatch.setattr(storage, 'time', SimpleNamespace(monotonic=lambda: clock[0]))
    monkeypatch.setattr(sqlite3, 'connect', lambda *args, **kwargs: connect(*args, **kwargs, factory=Connection))
    with pytest.raises(TimeoutError, match='SQLite backup exceeded timeout'):
        storage.backup_database(source, destination)
    assert source.read_bytes() == before and not destination.exists()


@pytest.mark.parametrize('status', [sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED])
def test_predeadline_wait_can_finish_with_late_done(databases, monkeypatch, status):
    source, destination = databases
    before = source.read_bytes()
    fingerprints, events = late_copy(monkeypatch, destination, early_status=status)
    result = storage.backup_database(source, destination)
    assert result['tables']['sample']['count'] == 2
    assert fingerprints == [source, destination, destination]
    assert events[-1][0:2] == (sqlite3.SQLITE_DONE, 0)
    assert source.read_bytes() == before


def test_exhausted_budget_does_not_start_native_backup(databases, monkeypatch):
    source, destination = databases
    before, clock, started = source.read_bytes(), [0.0], []
    connect = sqlite3.connect

    class Connection(sqlite3.Connection):
        def backup(self, target, **kwargs):
            started.append(True)
            return super().backup(target, **kwargs)

    def opened(path, *args, **kwargs):
        conn = connect(path, *args, **kwargs, factory=Connection)
        if path == destination:
            clock[0] = 6.0
        return conn

    monkeypatch.setattr(storage, 'time', SimpleNamespace(monotonic=lambda: clock[0]))
    monkeypatch.setattr(sqlite3, 'connect', opened)
    with pytest.raises(TimeoutError, match='SQLite backup exceeded timeout'):
        storage.backup_database(source, destination)
    assert not started
    assert source.read_bytes() == before and not destination.exists()
