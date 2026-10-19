"""Strict in-memory driver doubles, not SQLite/owner-lifecycle qualification."""
from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace
import threading

import pytest
from sqlalchemy.sql import operators

from analytics import service
from persistence import capacity, repository
from persistence.models import ResourceCapacity, ResourceReservation, SimulationJobRecord, StatsSnapshot


class PureOwner:
    def __init__(self):
        self.epoch = 'pure-driver-epoch'
        self.uncertain = False
        self.admissions_open = True
        self.mutex = threading.RLock()
        self.producers = {}

    def require(self):
        if self.uncertain:
            raise capacity.CapacityIntegrityError('Pure driver storage outcome uncertain')

    @contextmanager
    def activity(self):
        self.require()
        if not self.admissions_open:
            raise capacity.CapacityAdmissionClosed('Pure driver admission closed')
        token, cancel, done = object(), threading.Event(), threading.Event()
        self.producers[token] = (cancel, done)
        try:
            yield cancel
        finally:
            self.producers.pop(token)
            done.set()

    def fence_admission(self):
        self.admissions_open = False
        for cancel, _done in self.producers.values():
            cancel.set()


class PureSession:
    def __init__(self):
        self.owner = PureOwner()
        self.binding = object()
        self.rows = {model: {} for model in (ResourceCapacity, ResourceReservation,
                                            SimulationJobRecord, StatsSnapshot)}
        self.rows[ResourceCapacity][1] = ResourceCapacity(owner_epoch=self.owner.epoch)

    @property
    def ledger(self):
        return self.rows[ResourceCapacity][1]

    def get_bind(self):
        return self.binding

    def get(self, model, key, **options):
        assert model in self.rows
        assert not options or options == {'populate_existing': True}
        return self.rows[model].get(key)

    def add(self, row):
        model = type(row)
        assert model in self.rows
        if model is StatsSnapshot and row.id is None:
            row.id = len(self.rows[model]) + 1
        key = row.token if model is ResourceReservation else row.id
        self.rows[model][key] = row

    def delete(self, row):
        key = row.token if type(row) is ResourceReservation else row.id
        assert self.rows[type(row)][key] is row
        del self.rows[type(row)][key]

    def refresh(self, row):
        key = row.token if type(row) is ResourceReservation else row.id
        assert self.rows[type(row)][key] is row

    def flush(self):
        pass

    def exec(self, statement):
        if statement.column_descriptions[0].get('entity') is ResourceReservation:
            assert len(statement._where_criteria) == 1
            clause = statement._where_criteria[0]
            assert clause.left.name == 'job_id' and clause.operator is operators.eq
            rows = [row for row in self.rows[ResourceReservation].values()
                    if row.job_id == clause.right.value]
            assert len(rows) <= 1
            def one():
                assert len(rows) == 1
                return rows[0]
            return SimpleNamespace(one=one, one_or_none=lambda: rows[0] if rows else None)
        assert [table.name for table in statement.get_final_froms()] == ['simulationjobrecord']
        assert statement.column_descriptions[0]['name'] == 'count'
        assert not statement._where_criteria
        return SimpleNamespace(one=lambda: len(self.rows[SimulationJobRecord]))


class PureSnapshotRepository(repository.Repository):
    def __init__(self):
        super().__init__(PureSession())

    def save_snapshot(self, label, stats, *, reservation_token=None):
        row = super().save_snapshot(label, stats, reservation_token=reservation_token)
        self.record_snapshot(label, stats)
        return row

    def record_snapshot(self, label, stats):
        pass


@pytest.fixture(autouse=True)
def pure_snapshot_storage(monkeypatch):
    """Patch only explicit driver doubles; other sessions retain real guards."""
    real_owner_for = capacity.owner_for
    real_write, real_transaction = repository.capacity_write, repository.capacity_transaction

    def owner_for(session):
        if not isinstance(session, PureSession):
            return real_owner_for(session)
        session.owner.require()
        return session.owner

    @contextmanager
    def write(session):
        if not isinstance(session, PureSession):
            with real_write(session):
                yield
            return
        with session.owner.activity():
            try:
                yield
            except (capacity.CapacityExceeded, capacity.CapacityAdmissionClosed):
                raise
            except BaseException:
                capacity.mark_uncertain(session.owner)
                raise

    @contextmanager
    def transaction(session):
        if not isinstance(session, PureSession):
            with real_transaction(session) as tx:
                yield tx
            return
        before = deepcopy(session.rows)
        try:
            yield capacity.CapacityTransaction(session, session.owner)
        except BaseException:
            session.rows = before
            raise

    monkeypatch.setattr(service, 'owner_for', owner_for)
    monkeypatch.setattr(repository, 'owner_for', owner_for)
    monkeypatch.setattr(repository, 'capacity_write', write)
    monkeypatch.setattr(repository, 'capacity_transaction', transaction)
