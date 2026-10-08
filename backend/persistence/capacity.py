"""Logical payload capacity. SQL/ownership qualification is a separate gate."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, replace
import fcntl
import os
from pathlib import Path
import stat
import threading
import time
import uuid
from weakref import WeakKeyDictionary

from sqlmodel import select
from analytics.resource_budget import RESOURCE_LIMITS
from persistence.job_retention import local_path, _canonical_local_path
from persistence.models import ResourceCapacity, ResourceReservation

BYTE_LIMIT = 1073741824
SNAPSHOT_LIMIT = 10000
JOB_LIMIT = 10000
TERMINAL = frozenset({'completed', 'failed', 'canceled', 'retired'})
_OWNERS = WeakKeyDictionary()
_OWNER_LOCK = threading.RLock()


def application_database_path(value, *, existing=True):
    """Only the exact default may enter the application-owned bootstrap seam."""
    path = Path(value)
    default = Path(__file__).resolve().parents[1] / 'mtg_lab.db'
    validator = _canonical_local_path if path == default else local_path
    return validator(path, existing=existing)


def validate_job_transition(row, values):
    """Generic persistence cannot create or resurrect an operator tombstone."""
    if values['status'] == 'retired' or (row is not None and row.status == 'retired'):
        raise CapacityIntegrityError('Retired jobs require explicit operator maintenance')
    if row is not None and row.status in TERMINAL:
        if any(getattr(row, key) != value for key, value in values.items()):
            raise CapacityIntegrityError('Terminal job fields are immutable')


class CapacityExceeded(RuntimeError):
    def __init__(self, dimension):
        self.dimension = dimension
        super().__init__('resource_capacity:' + dimension)


class CapacityIntegrityError(RuntimeError):
    pass


class CapacityAdmissionClosed(RuntimeError):
    pass


def encoded_bytes(*values):
    """Use the accepted strings, never encode the JSON object a second time."""
    if any(value is not None and not isinstance(value, str) for value in values):
        raise TypeError('Capacity fields must already be encoded strings')
    return sum(len(value.encode('utf-8')) for value in values if value is not None)


@dataclass(frozen=True)
class Counters:
    durable_bytes: int = 0
    snapshot_rows: int = 0
    reserved_bytes: int = 0
    reserved_snapshot_rows: int = 0

    def validate(self):
        if any(type(v) is not int or v < 0 for v in self.__dict__.values()):
            raise CapacityIntegrityError('Invalid capacity counters')
        if self.durable_bytes + self.reserved_bytes > BYTE_LIMIT:
            raise CapacityExceeded('bytes')
        if self.snapshot_rows + self.reserved_snapshot_rows > SNAPSHOT_LIMIT:
            raise CapacityExceeded('snapshot_rows')
        return self

    def shifted(self, **deltas):
        self.validate()
        if any(type(v) is not int for v in deltas.values()):
            raise CapacityIntegrityError('Invalid capacity delta')
        return replace(self, **{key: getattr(self, key) + value for key, value in deltas.items()}).validate()


@dataclass(frozen=True)
class Escrow:
    snapshot_bytes: int = 0
    result_bytes: int = 0
    error_bytes: int = 0
    snapshot_rows: int = 0

    @property
    def total(self):
        return self.snapshot_bytes + self.result_bytes + self.error_bytes

    def validate(self):
        if any(type(v) is not int or v < 0 for v in self.__dict__.values()) or self.snapshot_rows not in (0, 1):
            raise CapacityIntegrityError('Invalid escrow')
        if bool(self.snapshot_bytes) != bool(self.snapshot_rows):
            raise CapacityIntegrityError('Snapshot escrow mismatch')
        if (self.snapshot_bytes > RESOURCE_LIMITS['snapshot_json_bytes'] or
                self.result_bytes > RESOURCE_LIMITS['result_json_bytes'] or
                self.error_bytes > RESOURCE_LIMITS['error_utf8_bytes']):
            raise CapacityIntegrityError('Escrow exceeds fixed field policy')
        return self


def background_escrow():
    return Escrow(RESOURCE_LIMITS['snapshot_json_bytes'], RESOURCE_LIMITS['result_json_bytes'],
                  RESOURCE_LIMITS['error_utf8_bytes'], 1)


def snapshot_escrow():
    return Escrow(snapshot_bytes=RESOURCE_LIMITS['snapshot_json_bytes'], snapshot_rows=1)


def reserve(counters, escrow):
    escrow.validate()
    return counters.shifted(reserved_bytes=escrow.total, reserved_snapshot_rows=escrow.snapshot_rows)


def consume_snapshot(counters, escrow, size):
    escrow.validate()
    if type(size) is not int or size < 0 or not escrow.snapshot_rows or size > escrow.snapshot_bytes:
        raise CapacityIntegrityError('Snapshot outside reservation')
    after = counters.shifted(durable_bytes=size, snapshot_rows=1,
                             reserved_bytes=-escrow.snapshot_bytes, reserved_snapshot_rows=-1)
    return after, replace(escrow, snapshot_bytes=0, snapshot_rows=0)


def settle_job(counters, escrow, old_size, new_size):
    escrow.validate()
    if any(type(v) is not int or v < 0 for v in (old_size, new_size)):
        raise CapacityIntegrityError('Invalid job field size')
    delta = new_size - old_size
    if delta > escrow.result_bytes + escrow.error_bytes:
        raise CapacityIntegrityError('Job outside reservation')
    return counters.shifted(durable_bytes=delta, reserved_bytes=-escrow.total,
                            reserved_snapshot_rows=-escrow.snapshot_rows)


class DatabaseOwner:
    """Lifetime Linux lock for an explicit canonical local file, never PID expiry."""
    def __init__(self, engine):
        if engine.dialect.name != 'sqlite' or not engine.url.database or engine.url.database == ':memory:':
            raise CapacityIntegrityError('Capacity owner requires a local SQLite file')
        self.path = application_database_path(Path(engine.url.database), existing=Path(engine.url.database).exists())
        if str(self.path) != engine.url.database or engine.url.query:
            raise CapacityIntegrityError('Canonical file URL required')
        self.engine, self.fd, self.pid = engine, None, os.getpid()
        self.epoch = uuid.uuid4().hex
        self.ready = False
        self.uncertain = False
        self.pool = engine.pool
        self.database_identity = None
        self.mutex = threading.RLock()
        self.admissions_open = False
        self.producers = {}
        self.local = threading.local()
        self.lock_path = Path(str(self.path) + '.capacity-owner.lock')
        if self.path.exists():
            self.pin_database()

    def pin_database(self):
        try:
            info = self.path.stat(follow_symlinks=False)
        except OSError as exc:
            raise CapacityIntegrityError('Database file unavailable') from exc
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or self.path.resolve() != self.path:
            raise CapacityIntegrityError('Database must be a single-link canonical regular file')
        identity = (info.st_dev, info.st_ino)
        if self.database_identity is not None and identity != self.database_identity:
            raise CapacityIntegrityError('Database file identity changed')
        self.database_identity = identity

    def acquire(self):
        with _OWNER_LOCK:
            if self.fd is not None or self.engine in _OWNERS:
                raise CapacityIntegrityError('Owner already acquired')
            fd = os.open(self.lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
            try:
                info = os.fstat(fd)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise CapacityIntegrityError('Unsafe owner lock')
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                current = self.lock_path.stat(follow_symlinks=False)
                if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
                    raise CapacityIntegrityError('Owner lock changed')
                if not hasattr(self.engine.pool, 'checkedout') or self.engine.pool.checkedout():
                    raise CapacityIntegrityError('Cannot acquire ownership with checked-out connections')
                # Discard idle connections opened before this ownership epoch.
                self.engine.dispose()
                self.pool = self.engine.pool
            except BaseException:
                os.close(fd)
                raise
            self.fd, self.identity = fd, (info.st_dev, info.st_ino)
            _OWNERS[self.engine] = self
        return self

    def require(self, *, ready=True):
        if ready and self.uncertain:
            raise CapacityIntegrityError('Storage outcome uncertain; admission fenced')
        if self.fd is None or os.getpid() != self.pid or (ready and not self.ready):
            raise CapacityIntegrityError('Live initialized owner required')
        with _OWNER_LOCK:
            if _OWNERS.get(self.engine) is not self:
                raise CapacityIntegrityError('Registered owner required')
        if self.engine.dialect.name != 'sqlite' or self.engine.url.database != str(self.path) or self.engine.url.query:
            raise CapacityIntegrityError('Owner engine binding changed')
        if self.engine.pool is not self.pool:
            raise CapacityIntegrityError('Owner pool binding changed')
        info = self.lock_path.stat(follow_symlinks=False)
        descriptor = os.fstat(self.fd)
        if ((info.st_dev, info.st_ino) != self.identity or
                (descriptor.st_dev, descriptor.st_ino) != self.identity or not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1):
            raise CapacityIntegrityError('Owner lock identity changed')
        if self.path.resolve() != self.path:
            raise CapacityIntegrityError('Database path changed')
        if self.database_identity is not None:
            self.pin_database()
        elif ready:
            raise CapacityIntegrityError('Initialized database file identity required')

    def backup(self, destination, *, timeout=5.0):
        """Default-DB backup only through a registered, live locked application owner."""
        from scripts.verify_storage_restore import _backup_validated_database

        with self.mutex:
            self.require(ready=False)
            source = application_database_path(self.path)
            destination = local_path(destination, existing=False)
            return _backup_validated_database(source, destination, timeout=timeout)

    def open_admission(self):
        with self.mutex:
            self.require()
            self.admissions_open = True

    @contextmanager
    def activity(self, *, threaded=True):
        """Track actual producer/session lifetime, not threadpool thread lifetime."""
        token, cancel, done = uuid.uuid4().hex, threading.Event(), threading.Event()
        with self.mutex:
            self.require()
            depth = getattr(self.local, 'depth', 0)
            if not self.admissions_open and not depth:
                raise CapacityAdmissionClosed('Capacity admission is closed')
            self.producers[token] = (cancel, done)
            if threaded:
                self.local.depth = depth + 1
        try:
            yield cancel
        finally:
            with self.mutex:
                self.producers.pop(token)
                if threaded:
                    self.local.depth -= 1
                done.set()

    def fence_admission(self):
        with self.mutex:
            self.require(ready=False)
            self.admissions_open = False
            for cancel, _done in self.producers.values():
                cancel.set()

    def drain_producers(self, *, timeout=20.0):
        deadline = time.monotonic() + timeout
        self.fence_admission()
        with self.mutex:
            pending = [done for _cancel, done in self.producers.values()]
        for done in pending:
            if not done.wait(max(0, deadline - time.monotonic())):
                raise CapacityIntegrityError('Timed out draining actual producers; owner retained')
        with self.mutex:
            if self.producers:
                raise CapacityIntegrityError('Actual producers remain; owner retained')

    def close(self):
        with self.mutex, _OWNER_LOCK:
            self.require(ready=False)
            if self.producers or self.admissions_open:
                raise CapacityIntegrityError('Admission/producers still active; owner retained')
            if not hasattr(self.engine.pool, 'checkedout') or self.engine.pool.checkedout():
                raise CapacityIntegrityError('Database connections still checked out')
            # Caller must have joined its real producers before ending ownership.
            self.engine.dispose()
            os.close(self.fd)
            self.fd, self.ready = None, False
            del _OWNERS[self.engine]


def owner_for(session):
    binding = session.get_bind()
    engine = getattr(binding, 'engine', binding)
    with _OWNER_LOCK:
        try:
            owner = _OWNERS.get(engine)
        except TypeError:
            owner = None
    if owner is None:
        raise CapacityIntegrityError('No capacity owner for Session')
    owner.require()
    return owner


def owner_for_engine(engine):
    with _OWNER_LOCK:
        owner = _OWNERS.get(engine)
    if owner is None:
        raise CapacityAdmissionClosed('Application owner is unavailable')
    owner.require()
    return owner


def owner_uncertain(engine):
    with _OWNER_LOCK:
        owner = _OWNERS.get(engine)
        return owner is not None and owner.uncertain


def mark_uncertain(owner):
    """Latch uncertainty without depending on a now-invalid path or SQL lookup."""
    with owner.mutex:
        owner.uncertain, owner.admissions_open = True, False
        for cancel, _done in getattr(owner, 'producers', {}).values():
            cancel.set()


@contextmanager
def capacity_write(session):
    # Encoding/preflight must precede this scope; refresh must remain inside it.
    owner = owner_for(session)
    with owner.activity():
        try:
            yield
        except (CapacityExceeded, CapacityAdmissionClosed):
            raise
        except BaseException:
            mark_uncertain(owner)
            raise


def counters_from(row):
    return Counters(row.durable_bytes, row.snapshot_rows, row.reserved_bytes, row.reserved_snapshot_rows).validate()


def escrow_from(row):
    return Escrow(row.snapshot_bytes, row.result_bytes, row.error_bytes, row.snapshot_rows).validate()


class CapacityTransaction:
    def __init__(self, session, owner):
        self.session, self.owner = session, owner
        self.ledger = session.get(ResourceCapacity, 1, populate_existing=True)
        if self.ledger is None or self.ledger.version != 1 or self.ledger.owner_epoch != owner.epoch:
            raise CapacityIntegrityError('Capacity epoch/schema mismatch')
        counters_from(self.ledger)

    def counters(self, value):
        value.validate()
        for name, number in value.__dict__.items():
            setattr(self.ledger, name, number)
        self.session.add(self.ledger)

    def reservation(self, *, token=None, job_id=None):
        row = (self.session.get(ResourceReservation, token, populate_existing=True) if token is not None else
               self.session.exec(select(ResourceReservation).where(ResourceReservation.job_id == job_id)).one_or_none())
        if row is not None and row.owner_epoch != self.owner.epoch:
            raise CapacityIntegrityError('Reservation belongs to another epoch')
        return row

    def add_reservation(self, escrow, *, kind, job_id=None):
        self.counters(reserve(counters_from(self.ledger), escrow))
        row = ResourceReservation(token=uuid.uuid4().hex, job_id=job_id, kind=kind,
                                  owner_epoch=self.owner.epoch, **escrow.__dict__)
        self.session.add(row)
        return row

    def snapshot(self, size, token):
        row = self.reservation(token=token)
        if row is None:
            raise CapacityIntegrityError('Snapshot reservation missing')
        after, remainder = consume_snapshot(counters_from(self.ledger), escrow_from(row), size)
        self.counters(after)
        for name, number in remainder.__dict__.items():
            setattr(row, name, number)
        if row.kind == 'snapshot':
            self.session.delete(row)
        else:
            self.session.add(row)
        return row.job_id

    def finish_job(self, row, old_size, new_size):
        self.counters(settle_job(counters_from(self.ledger), escrow_from(row), old_size, new_size))
        self.session.delete(row)


@contextmanager
def capacity_transaction(session):
    owner = owner_for(session)
    with owner.mutex:
        owner.require()
        if session.new or session.dirty or session.deleted:
            raise CapacityIntegrityError('Capacity transaction requires a clean Session')
        commit_attempted = False
        try:
            connection = session.connection()
            owner.require()
            native = connection.connection.driver_connection
            if native.in_transaction:
                raise CapacityIntegrityError('Cannot join an existing native transaction')
            connection.exec_driver_sql('PRAGMA foreign_keys=ON')
            connection.exec_driver_sql('BEGIN IMMEDIATE')
            databases = connection.exec_driver_sql('PRAGMA database_list').all()
            if ([(row[1], row[2]) for row in databases if row[1] != 'temp'] != [('main', str(owner.path))]):
                raise CapacityIntegrityError('Native database does not match owner')
            with session.no_autoflush:
                yield CapacityTransaction(session, owner)
            commit_attempted = True
            session.commit()
        except BaseException:
            if commit_attempted:
                mark_uncertain(owner)
            try:
                session.rollback()
            except BaseException:
                mark_uncertain(owner)
            # Rollback is best effort, not proof that an attempted commit was undone.
            # Preserve the original failure even when cleanup also fails.
            raise


def _stored_counts(connection):
    durable = connection.exec_driver_sql('''
        SELECT COALESCE(SUM(length(CAST(request_json AS BLOB)) +
            COALESCE(length(CAST(result_json AS BLOB)), 0) +
            COALESCE(length(CAST(error AS BLOB)), 0)), 0)
        FROM simulationjobrecord''').scalar_one()
    snap_bytes, rows = connection.exec_driver_sql('''
        SELECT COALESCE(SUM(length(CAST(stats_json AS BLOB))), 0), COUNT(*)
        FROM statssnapshot''').one()
    return Counters(durable + snap_bytes, rows).validate()


def initialize_capacity(owner, backup_path):
    """Under real exclusive ownership, backup then atomic additive/recovery epoch."""
    import time

    with owner.mutex:
        owner.require(ready=False)
        if owner.ready:
            raise CapacityIntegrityError('Capacity already initialized for this owner')
        owner.pin_database()
        # Existing supported application tables must precede this explicit stage.
        # Backup helper uses exclusive destinations and verifies all stored rows.
        owner.backup(backup_path)
        with owner.engine.connect() as connection:
            owner.require(ready=False)
            commit_attempted = False
            try:
                connection.exec_driver_sql('PRAGMA foreign_keys=ON')
                connection.exec_driver_sql('BEGIN IMMEDIATE')
                if connection.exec_driver_sql('PRAGMA encoding').scalar_one() != 'UTF-8':
                    raise CapacityIntegrityError('UTF-8 database required')
                if connection.exec_driver_sql("""SELECT 1 FROM sqlite_schema WHERE type='trigger'
                    AND lower(tbl_name) IN ('simulationjobrecord','statssnapshot','resourcecapacity','resourcereservation')""").first():
                    raise CapacityIntegrityError('Unexpected resource table trigger')
                before = _stored_counts(connection)
                jobs = connection.exec_driver_sql('SELECT COUNT(*) FROM simulationjobrecord').scalar_one()
                if jobs > JOB_LIMIT:
                    raise CapacityExceeded('job_rows')
                unfinished = connection.exec_driver_sql(
                    "SELECT COUNT(*) FROM simulationjobrecord WHERE status IN ('queued','running')").scalar_one()
                # Worst-case added bounded terminal error must fit BEFORE mutation.
                before.shifted(reserved_bytes=unfinished * RESOURCE_LIMITS['error_utf8_bytes'])
                tables = set(connection.exec_driver_sql("SELECT name FROM sqlite_schema WHERE type='table'").scalars())
                present = {'resourcecapacity', 'resourcereservation'} & tables
                if present and len(present) != 2:
                    raise CapacityIntegrityError('Partial capacity schema')
                if present:
                    for model in (ResourceCapacity, ResourceReservation):
                        columns = {row[1] for row in connection.exec_driver_sql('PRAGMA table_info(' + model.__tablename__ + ')')}
                        if columns != set(model.__table__.columns.keys()):
                            raise CapacityIntegrityError('Unknown capacity schema columns')
                    ledger = connection.exec_driver_sql('SELECT * FROM resourcecapacity').mappings().all()
                    if len(ledger) != 1 or ledger[0]['id'] != 1 or ledger[0]['version'] != 1:
                        raise CapacityIntegrityError('Unknown capacity schema version')
                    recorded = Counters(**{name: ledger[0][name] for name in before.__dict__}).validate()
                    reservations = connection.exec_driver_sql('SELECT * FROM resourcereservation').mappings().all()
                    reserved = sum(Escrow(**{name: row[name] for name in Escrow.__dataclass_fields__}).validate().total
                                   for row in reservations)
                    reserved_rows = sum(row['snapshot_rows'] for row in reservations)
                    if (recorded.durable_bytes, recorded.snapshot_rows, recorded.reserved_bytes, recorded.reserved_snapshot_rows) != (
                            before.durable_bytes, before.snapshot_rows, reserved, reserved_rows):
                        raise CapacityIntegrityError('Capacity ledger drift')
                    if any(row['owner_epoch'] != ledger[0]['owner_epoch'] for row in reservations):
                        raise CapacityIntegrityError('Mixed reservation owners')
                snapshot_columns = {row[1] for row in connection.exec_driver_sql('PRAGMA table_info(statssnapshot)')}
                if 'job_id' not in snapshot_columns:
                    connection.exec_driver_sql('ALTER TABLE statssnapshot ADD COLUMN job_id TEXT REFERENCES simulationjobrecord(id)')
                links = connection.exec_driver_sql('PRAGMA foreign_key_list(statssnapshot)').all()
                if not any(row[2] == 'simulationjobrecord' and row[3] == 'job_id' and row[4] == 'id' for row in links):
                    raise CapacityIntegrityError('Snapshot ownership foreign key missing')
                connection.exec_driver_sql('CREATE INDEX IF NOT EXISTS ix_statssnapshot_job_id ON statssnapshot(job_id)')
                ResourceCapacity.__table__.create(connection, checkfirst=True)
                ResourceReservation.__table__.create(connection, checkfirst=True)
                connection.exec_driver_sql("""UPDATE simulationjobrecord SET status='failed', error=?, finished_at=?
                    WHERE status IN ('queued','running')""",
                    ('Backend restarted before the simulation completed.', time.time()))
                after = _stored_counts(connection)
                connection.exec_driver_sql('DELETE FROM resourcereservation')
                connection.exec_driver_sql('DELETE FROM resourcecapacity')
                connection.execute(ResourceCapacity.__table__.insert().values(
                    id=1, version=1, owner_epoch=owner.epoch, **after.__dict__))
                if connection.exec_driver_sql('PRAGMA foreign_key_check').first() is not None:
                    raise CapacityIntegrityError('Foreign key violation')
                commit_attempted = True
                connection.commit()
            except BaseException:
                if commit_attempted:
                    mark_uncertain(owner)
                try:
                    connection.rollback()
                except BaseException:
                    mark_uncertain(owner)
                raise
        owner.ready = True
