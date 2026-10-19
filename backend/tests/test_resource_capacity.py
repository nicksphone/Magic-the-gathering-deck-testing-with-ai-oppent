"""Pure accounting/schema/protocol tests, NOT native SQL/owner/migration proof."""
from contextlib import nullcontext
from types import SimpleNamespace
import ast
from pathlib import Path
import threading

import pytest
from sqlalchemy.dialects import sqlite
from sqlalchemy.schema import CreateTable
from persistence.models import ResourceCapacity, ResourceReservation, StatsSnapshot
import persistence.capacity as capacity
from persistence.capacity import (
    BYTE_LIMIT, SNAPSHOT_LIMIT, CapacityExceeded, CapacityIntegrityError,
    Counters, Escrow, background_escrow, snapshot_escrow, reserve,
    consume_snapshot, settle_job, encoded_bytes,
)


def test_declared_exact_constants():
    assert BYTE_LIMIT == 1073741824 and SNAPSHOT_LIMIT == 10000


@pytest.mark.parametrize('counters', [Counters(durable_bytes=BYTE_LIMIT), Counters(reserved_bytes=BYTE_LIMIT),
    Counters(durable_bytes=BYTE_LIMIT-1, reserved_bytes=1), Counters(snapshot_rows=SNAPSHOT_LIMIT),
    Counters(reserved_snapshot_rows=SNAPSHOT_LIMIT), Counters(snapshot_rows=9999,reserved_snapshot_rows=1)])
def test_equality_allowed(counters):
    assert counters.validate() == counters


@pytest.mark.parametrize('counters,dimension', [(Counters(durable_bytes=BYTE_LIMIT,reserved_bytes=1),'bytes'),
    (Counters(snapshot_rows=10000,reserved_snapshot_rows=1),'snapshot_rows')])
def test_one_over_rejects(counters,dimension):
    with pytest.raises(CapacityExceeded) as caught:
        counters.validate()
    assert caught.value.dimension == dimension


@pytest.mark.parametrize('value', [-1, True, 1.0, '1'])
def test_invalid_counters_fail_closed(value):
    with pytest.raises(CapacityIntegrityError):
        Counters(durable_bytes=value).validate()


def test_invalid_starting_state_cannot_be_repaired_by_shift():
    with pytest.raises(CapacityIntegrityError):
        Counters(durable_bytes=-1).shifted(durable_bytes=1)


def test_encoded_utf8_and_null_exact_no_json_reencoding():
    assert encoded_bytes(None, '{}', chr(0x1F600), '\\ud83d\\ude00') == 18
    with pytest.raises(TypeError):
        encoded_bytes({'already':'not encoded'})
    with pytest.raises(UnicodeError):
        encoded_bytes(chr(0xD800))


def test_snapshot_reserve_at_exact_aggregate_boundary():
    escrow = snapshot_escrow()
    initial = Counters(durable_bytes=BYTE_LIMIT-escrow.total,snapshot_rows=9999)
    held = reserve(initial,escrow)
    assert held.durable_bytes + held.reserved_bytes == BYTE_LIMIT
    converted,remainder = consume_snapshot(held,escrow,escrow.total)
    assert converted == Counters(durable_bytes=BYTE_LIMIT,snapshot_rows=10000)
    assert remainder == Escrow()


def test_small_actual_snapshot_releases_unused_reserve_not_old_data():
    escrow = background_escrow()
    initial = Counters(durable_bytes=180)
    held = reserve(initial,escrow)
    after,remaining = consume_snapshot(held,escrow,8683)
    assert after.durable_bytes == 180+8683 and after.snapshot_rows == 1
    assert after.reserved_bytes == remaining.result_bytes+remaining.error_bytes
    settled = settle_job(after,remaining,180,180+8683)
    assert settled == Counters(durable_bytes=180+2*8683,snapshot_rows=1)
    assert initial == Counters(durable_bytes=180)


@pytest.mark.parametrize('terminal_error_bytes',[0,68,1024])
def test_failed_cancelled_job_releases_unused_reserve(terminal_error_bytes):
    escrow = background_escrow()
    held = reserve(Counters(durable_bytes=180),escrow)
    assert settle_job(held,escrow,180,180+terminal_error_bytes) == Counters(durable_bytes=180+terminal_error_bytes)


def test_committed_snapshot_remains_counted_when_job_fails():
    escrow = background_escrow()
    counted,remaining = consume_snapshot(reserve(Counters(durable_bytes=180),escrow),escrow,8683)
    settled = settle_job(counted,remaining,180,248)
    assert settled == Counters(durable_bytes=8683+248,snapshot_rows=1)


def test_snapshot_double_consume_and_double_release_fail_closed():
    escrow = snapshot_escrow()
    converted,remainder = consume_snapshot(reserve(Counters(),escrow),escrow,10)
    with pytest.raises(CapacityIntegrityError):
        consume_snapshot(converted,remainder,10)
    with pytest.raises(CapacityIntegrityError):
        settle_job(converted,escrow,0,0)


@pytest.mark.parametrize('escrow,size',[(snapshot_escrow(),1048577),(Escrow(),0),(snapshot_escrow(),-1)])
def test_snapshot_outside_reservation(escrow,size):
    with pytest.raises(CapacityIntegrityError):
        consume_snapshot(Counters(),escrow,size)


def test_failed_transition_does_not_mutate_input():
    escrow = snapshot_escrow()
    original = Counters(durable_bytes=BYTE_LIMIT-escrow.total+1)
    with pytest.raises(CapacityExceeded):
        reserve(original,escrow)
    assert original.durable_bytes == BYTE_LIMIT-escrow.total+1


def test_replacement_frees_only_replaced_payload_bytes():
    original = Counters(durable_bytes=1000)
    assert original.shifted(durable_bytes=100-200).durable_bytes == 900


@pytest.mark.parametrize('model',[ResourceCapacity,ResourceReservation,StatsSnapshot])
def test_static_schema_compiles_without_sql(model):
    ddl = str(CreateTable(model.__table__).compile(dialect=sqlite.dialect()))
    if model is ResourceCapacity:
        assert '1073741824' in ddl and '10000' in ddl and 'CHECK' in ddl
    else:
        assert 'REFERENCES simulationjobrecord' in ddl


def test_owner_missing_denies_before_session_sql():
    calls=[]
    session=SimpleNamespace(get_bind=lambda:object(),connection=lambda:calls.append('SQL'))
    with pytest.raises(CapacityIntegrityError,match='No capacity owner'):
        with capacity.capacity_transaction(session):
            pytest.fail('body reached')
    assert calls == []


@pytest.mark.parametrize('commit_fails',[False,True])
def test_transaction_protocol_commit_failure_rolls_back_escrow(monkeypatch,commit_fails):
    # Explicit spy protocol, NOT a real Session, SQLite transaction or native lock.
    initial = dict(durable_bytes=180,snapshot_rows=0,reserved_bytes=1024,reserved_snapshot_rows=0)
    ledger=ResourceCapacity(owner_epoch='a'*32,**initial)
    calls=[]
    owner=SimpleNamespace(epoch='a'*32,path=Path('/fake-protocol.db'),mutex=threading.RLock(),require=lambda:calls.append('owner'))
    monkeypatch.setattr(capacity,'owner_for',lambda session:owner)
    def execute(text):
        calls.append(text)
        return SimpleNamespace(all=lambda:[(0,'main','/fake-protocol.db')])
    connection=SimpleNamespace(connection=SimpleNamespace(driver_connection=SimpleNamespace(in_transaction=False)),
                               exec_driver_sql=execute)
    def commit():
        calls.append('commit')
        if commit_fails:raise RuntimeError('injected commit failure')
    def rollback():
        calls.append('rollback')
        for key,value in initial.items():setattr(ledger,key,value)
    session=SimpleNamespace(new=set(),dirty=set(),deleted=set(),connection=lambda:connection,
                            no_autoflush=nullcontext(),get=lambda *args,**kw:ledger,
                            add=lambda row:None,commit=commit,rollback=rollback)
    if commit_fails:
        with pytest.raises(RuntimeError,match='injected commit failure'):
            with capacity.capacity_transaction(session) as tx:
                tx.counters(Counters(durable_bytes=248))
        assert capacity.counters_from(ledger) == Counters(**initial)
        assert calls[-2:] == ['commit','rollback']
    else:
        with capacity.capacity_transaction(session) as tx:
            tx.counters(Counters(durable_bytes=248))
        assert capacity.counters_from(ledger) == Counters(durable_bytes=248)
        assert calls[-1]=='commit' and 'rollback' not in calls
    assert 'BEGIN IMMEDIATE' in calls


def test_static_initializer_backup_precedes_transaction_and_reconcile():
    tree=ast.parse(Path(capacity.__file__).read_text())
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='initialize_capacity')
    text=ast.unparse(node)
    assert text.index('owner.backup(backup_path)') < text.index('BEGIN IMMEDIATE')
    assert text.index('owner.require(ready=False)') < text.index('owner.backup(backup_path)')
    assert text.index('before.shifted') < text.index('ALTER TABLE') < text.index('UPDATE simulationjobrecord')
    assert text.index('connection.commit()') < text.index('owner.ready = True')


def test_static_reconcile_never_erases_job_payloads_or_auto_prunes():
    tree=ast.parse(Path(capacity.__file__).read_text())
    sql=[n.value for n in ast.walk(tree) if isinstance(n,ast.Constant) and isinstance(n.value,str)]
    deletes=[s for s in sql if s.startswith('DELETE FROM')]
    assert sorted(deletes)==['DELETE FROM resourcecapacity','DELETE FROM resourcereservation']
    recovery=next(s for s in sql if s.startswith('UPDATE simulationjobrecord'))
    assert 'result_json' not in recovery and 'request_json' not in recovery
