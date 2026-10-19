"""Public inert projections of the actual legacy audit comparison helpers."""
import ast
from copy import deepcopy
import json
from pathlib import Path
import signal

import pytest


def projected():
    tree = ast.parse(Path(__file__).with_name('test_private_choice_http_restart.py').read_text())
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    for node in functions:
        node.decorator_list = []
    namespace = {'json': json, 'signal': signal}
    exec(compile(ast.Module(body=functions, type_ignores=[]), '<actual-audit-helpers>', 'exec'), namespace)
    return namespace


def row():
    return {'pid': 101, 'state': {'cards': {}, 'players': {'1': {'hand': []}}},
            'controller': {'match_complete': False}, 'revision': 3,
            'database_sha256': 'a' * 64, 'restart_stable_database_sha256': 'b' * 64,
            'capacity_owner_epoch': 'c' * 32,
            'capacity_ledger': {'id': 1, 'version': 1, 'durable_bytes': 100,
                                'snapshot_rows': 2, 'reserved_bytes': 0,
                                'reserved_snapshot_rows': 0, 'owner_epoch': 'c' * 32}}


def pair():
    before = row()
    after = deepcopy(before)
    after.update(pid=102, database_sha256='d' * 64, capacity_owner_epoch='e' * 32)
    after['capacity_ledger']['owner_epoch'] = after['capacity_owner_epoch']
    return before, after


def prove(namespace, before, after, **overrides):
    assert callable(namespace.get('assert_restart_audit')), 'Missing strict restart pair proof'
    fields = {'previous_pid': 101, 'current_pid': 102, 'previous_returncode': -signal.SIGTERM}
    namespace['assert_restart_audit'](before, after, **(fields | overrides))


@pytest.mark.parametrize('cold', [False, True])
def test_old_schema_default_remains_every_operand_except_pid(cold):
    old = {'pid': 101, 'state': {}, 'controller': {}, 'revision': 3, 'database_sha256': 'a' * 64}
    if cold:
        old.update(raw_database_sha256='b' * 64, capacity_ledger=[{'owner_epoch': 'c' * 32}])
    saved = deepcopy(old)
    assert projected()['stable'](old) == {k: v for k, v in old.items() if k != 'pid'}
    assert old == saved


def test_default_new_projection_keeps_raw_epoch_and_whole_ledger():
    before, after = pair()
    stable = projected()['stable']
    assert stable(before) != stable(after)
    assert stable(before)['database_sha256'] == before['database_sha256']
    assert stable(before)['capacity_ledger'] == before['capacity_ledger']


def test_genuine_pair_projection_is_explicit_and_nonmutating():
    before, after = pair()
    saved = deepcopy((before, after))
    namespace = projected()
    prove(namespace, before, after)
    assert namespace['stable'](before, restart=True) == namespace['stable'](after, restart=True)
    assert (before, after) == saved


@pytest.mark.parametrize('key,value', [
    ('pid', True), ('pid', 101.0), ('pid', 0), ('revision', True), ('revision', -1),
    ('state', []), ('controller', []), ('database_sha256', 'A' * 64),
    ('database_sha256', 'x'), ('restart_stable_database_sha256', None),
    ('capacity_owner_epoch', 'g' * 32), ('capacity_owner_epoch', 'c' * 31),
    ('capacity_ledger', []),
])
def test_new_contract_rejects_malformed_members(key, value):
    candidate = row()
    candidate[key] = value
    with pytest.raises(AssertionError):
        projected()['stable'](candidate)


@pytest.mark.parametrize('key', ['restart_stable_database_sha256', 'capacity_owner_epoch',
                                'capacity_ledger', 'state'])
def test_partial_new_contract_never_falls_back(key):
    candidate = row()
    del candidate[key]
    with pytest.raises(AssertionError):
        projected()['stable'](candidate)


@pytest.mark.parametrize('key,value', [
    ('id', True), ('id', 2), ('version', 1.0), ('version', 2),
    ('durable_bytes', True), ('snapshot_rows', -1), ('reserved_bytes', '0'),
    ('reserved_snapshot_rows', 0.0), ('owner_epoch', 'f' * 32),
])
def test_full_capacity_cells_have_exact_types_and_epoch_binding(key, value):
    candidate = row()
    candidate['capacity_ledger'][key] = value
    with pytest.raises(AssertionError):
        projected()['stable'](candidate)


@pytest.mark.parametrize('where', ['audit', 'ledger'])
def test_unknown_member_is_not_discarded(where):
    candidate = row()
    target = candidate if where == 'audit' else candidate['capacity_ledger']
    target['unknown'] = None
    with pytest.raises(AssertionError):
        projected()['stable'](candidate)


@pytest.mark.parametrize('mutation', ['raw', 'canonical', 'epoch', 'ledger', 'revision',
                                     'state', 'controller', 'state_type', 'controller_type'])
def test_pair_rejects_other_changes_or_missing_rotation(mutation):
    before, after = pair()
    if mutation == 'raw':
        after['database_sha256'] = before['database_sha256']
    elif mutation == 'canonical':
        after['restart_stable_database_sha256'] = 'f' * 64
    elif mutation == 'epoch':
        after['capacity_owner_epoch'] = before['capacity_owner_epoch']
        after['capacity_ledger']['owner_epoch'] = before['capacity_owner_epoch']
    elif mutation == 'ledger':
        after['capacity_ledger']['durable_bytes'] += 1
    elif mutation == 'revision':
        after['revision'] += 1
    elif mutation == 'state':
        after['state']['players']['1']['hand'].append('public-synthetic-card')
    elif mutation == 'controller':
        after['controller']['match_complete'] = True
    elif mutation == 'state_type':
        before['state']['flag'] = False
        after['state']['flag'] = 0
    elif mutation == 'controller_type':
        before['controller']['number'] = 1
        after['controller']['number'] = 1.0
    namespace = projected()
    assert callable(namespace.get('assert_restart_audit')), 'Missing strict restart pair proof'
    with pytest.raises(AssertionError):
        prove(namespace, before, after)


@pytest.mark.parametrize('overrides', [
    {'previous_pid': True}, {'current_pid': 102.0}, {'previous_pid': 102},
    {'current_pid': 103}, {'previous_returncode': None}, {'previous_returncode': True},
    {'previous_returncode': -signal.SIGKILL}, {'previous_returncode': 1},
])
def test_pair_requires_actual_distinct_pids_and_terminal_process(overrides):
    namespace = projected()
    assert callable(namespace.get('assert_restart_audit')), 'Missing strict restart pair proof'
    with pytest.raises(AssertionError):
        prove(namespace, *pair(), **overrides)


def test_zero_returncode_is_also_genuine_terminal_closure():
    prove(projected(), *pair(), previous_returncode=0)


def test_same_epoch_raw_mutation_is_still_detected():
    before = row()
    after = deepcopy(before)
    after['database_sha256'] = 'd' * 64
    assert projected()['stable'](before) != projected()['stable'](after)


def test_nonfinite_game_value_fails_contract():
    candidate = row()
    candidate['state']['invalid'] = float('nan')
    with pytest.raises(AssertionError):
        projected()['stable'](candidate)


def test_old_schema_cannot_claim_new_restart_projection():
    namespace = projected()
    assert 'restart' in (namespace['stable'].__kwdefaults__ or {}), 'Missing explicit restart contract'
    with pytest.raises(AssertionError):
        namespace['stable']({'pid': 101, 'database_sha256': 'a' * 64}, restart=True)
