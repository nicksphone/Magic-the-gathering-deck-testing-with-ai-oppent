"""Actual audit FunctionDef on public synthetic dump/rows; never import backend/SQL."""
import ast
from copy import deepcopy
import hashlib
import os
from pathlib import Path
from types import SimpleNamespace

import pytest


EPOCH = 'a' * 32
FIELDS = ('id', 'version', 'durable_bytes', 'snapshot_rows', 'reserved_bytes',
          'reserved_snapshot_rows', 'owner_epoch')
COUNTERS = FIELDS[2:6]


def ledger(epoch=EPOCH):
    return {'id': 1, 'version': 1, 'durable_bytes': 17, 'snapshot_rows': 2,
            'reserved_bytes': 3, 'reserved_snapshot_rows': 1, 'owner_epoch': epoch}


def dump(row):
    numeric = ','.join(str(row[k]) for k in FIELDS[:-1])
    return ['BEGIN TRANSACTION;',
            'CREATE TABLE "resourcecapacity" (id INTEGER, version INTEGER, durable_bytes INTEGER, snapshot_rows INTEGER, reserved_bytes INTEGER, reserved_snapshot_rows INTEGER, owner_epoch TEXT);',
            f'INSERT INTO "resourcecapacity" VALUES({numeric},\'{row["owner_epoch"]}\');',
            'CREATE TABLE "activematchrecord" (id TEXT, state_json TEXT, updated_at INTEGER);',
            f'INSERT INTO "activematchrecord" VALUES(\'PUBLIC GAME\',\'{EPOCH}\',10);',
            'COMMIT;']


def audit(tmp_path, *, rows=None, ledgers=None, epoch=EPOCH, owner_fault=None):
    public_path = tmp_path / 'PUBLIC-NOT-A-SQLITE-DATABASE'
    expected_engine, request = object(), object()
    events = []

    class Scope:
        def __init__(self, name):
            self.name = name

        def __enter__(self):
            events.append(self.name + ':enter')
            return self

        def __exit__(self, *args):
            events.append(self.name + ':exit')

    class Connection(Scope):
        def __init__(self):
            super().__init__('connection')

        def iterdump(self):
            return iter(rows if rows is not None else dump(ledger(epoch)))

        def execute(self, statement):
            assert statement == 'SELECT * FROM resourcecapacity'
            return ledgers if ledgers is not None else [ledger(epoch)]

    owner = SimpleNamespace(epoch=epoch, pid=os.getpid(), path=public_path, mutex=Scope('mutex'))
    if owner_fault == 'pid':
        owner.pid = -1
    elif owner_fault == 'path':
        owner.path = tmp_path / 'FOREIGN-PUBLIC-PATH'

    def activity(*, threaded):
        assert threaded is False
        return Scope('activity')

    owner.activity = activity
    controller = SimpleNamespace(state={'PUBLIC': 'STATE'}, revision=4)

    def authorize(actual):
        assert actual is request

    def owned(identifier):
        assert identifier == 'PUBLIC-GAME-ID'
        return controller

    def connect(path):
        assert path == public_path
        return Connection()

    def owner_for_engine(engine):
        assert engine is expected_engine
        return owner

    source = Path(__file__).with_name('private_choice_boundary_fixture_server.py')
    tree = ast.parse(source.read_text(), filename=str(source))
    functions = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in {'audit', 'restart_stable_sql_fingerprint'}:
            selected = deepcopy(node)
            selected.decorator_list = []
            functions.append(selected)
    namespace = {'authorize': authorize, 'owned': owned, 'Request': object,
                 'serialize_match_snapshot': lambda state: dict(state), 'os': os,
                 'sqlite3': SimpleNamespace(connect=connect, Row=object()),
                 'DATABASE_PATH': public_path, 'engine': expected_engine,
                 'owner_for_engine': owner_for_engine, 'hashlib': hashlib,
                 'main': SimpleNamespace(_controller_snapshot=lambda c: {'PUBLIC': 'CONTROLLER'})}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), 'exec'), namespace)
    try:
        return namespace['audit']('PUBLIC-GAME-ID', request)
    finally:
        assert events.count('connection:enter') == events.count('connection:exit')
        assert events.count('activity:enter') == events.count('activity:exit')
        assert events.count('mutex:enter') == events.count('mutex:exit')


def fingerprint(result):
    assert {'restart_stable_database_sha256', 'capacity_owner_epoch', 'capacity_ledger'} <= result.keys()
    return result['restart_stable_database_sha256']


def test_epoch_only_rotation_preserves_stable_hash_but_retains_raw_and_full_ledger(tmp_path):
    before = audit(tmp_path)
    next_epoch = 'b' * 32
    after = audit(tmp_path, epoch=next_epoch)
    assert fingerprint(before) == fingerprint(after)
    assert before['database_sha256'] != after['database_sha256']
    assert before['database_sha256'] == hashlib.sha256('\n'.join(dump(ledger())).encode()).hexdigest()
    assert after['database_sha256'] == hashlib.sha256('\n'.join(dump(ledger(next_epoch))).encode()).hexdigest()
    assert before['capacity_owner_epoch'] == EPOCH and after['capacity_owner_epoch'] == next_epoch
    assert before['capacity_ledger'] == ledger()
    assert after['capacity_ledger'] == {**before['capacity_ledger'], 'owner_epoch': next_epoch}


@pytest.mark.parametrize('field', COUNTERS)
def test_every_non_epoch_capacity_value_remains_significant(tmp_path, field):
    before = audit(tmp_path)
    changed = ledger()
    changed[field] += 1
    after = audit(tmp_path, rows=dump(changed), ledgers=[changed])
    assert fingerprint(before) != fingerprint(after)


@pytest.mark.parametrize('mutation', ['game_value', 'game_count', 'schema'])
def test_other_game_rows_timestamps_counts_and_schema_are_not_normalized(tmp_path, mutation):
    before = audit(tmp_path)
    rows = dump(ledger())
    if mutation == 'game_value':
        rows[-2] = rows[-2].replace(',10);', ',11);')
    elif mutation == 'game_count':
        rows.insert(-1, "INSERT INTO \"activematchrecord\" VALUES('PUBLIC SECOND GAME','PUBLIC OTHER',10);")
    else:
        rows[3] = rows[3].replace('updated_at INTEGER', 'updated_at REAL')
    after = audit(tmp_path, rows=rows)
    assert fingerprint(before) != fingerprint(after)


@pytest.mark.parametrize('fault', ['missing', 'duplicate', 'epoch', 'bool', 'id', 'version',
                                   'extra_field', 'missing_field', 'dump_mismatch', 'dump_duplicate'])
def test_unknown_or_unbound_ledger_dump_contract_is_rejected(tmp_path, fault):
    row, rows = ledger(), dump(ledger())
    ledgers = [row]
    if fault == 'missing':
        ledgers = []
    elif fault == 'duplicate':
        ledgers = [row, dict(row)]
    elif fault == 'epoch':
        row['owner_epoch'] = 'c' * 32
    elif fault == 'bool':
        row['durable_bytes'] = True
    elif fault in {'id', 'version'}:
        row[fault] = 2
    elif fault == 'extra_field':
        row['unknown'] = 0
    elif fault == 'missing_field':
        del row['reserved_bytes']
    elif fault == 'dump_mismatch':
        rows[2] = rows[2].replace(',17,', ',18,')
    else:
        rows.insert(3, rows[2])
    with pytest.raises(AssertionError):
        audit(tmp_path, rows=rows, ledgers=ledgers)


@pytest.mark.parametrize('fault', ['pid', 'path'])
def test_actual_current_owner_must_bind_process_and_selected_database(tmp_path, fault):
    with pytest.raises(AssertionError):
        audit(tmp_path, owner_fault=fault)
