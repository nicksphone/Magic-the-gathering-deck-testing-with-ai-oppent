"""Native restart, raw read-only hashes, and independent persisted corruption REDs."""
import json

import pytest
from sqlmodel import create_engine

from tests.cold_restart_http_support import audit_identity, bootstrap_transition, facts, stable
from tests.temporary_characteristics_http_fixture import owned_database
from tests.test_optional_land_choice_http_stage import server


def position(server, seat):
    status, data = server.call(f'/fixture/private-choice?family=Growth%20Spiral&seat={seat}&slice_only=true', {})
    assert status == 200 and data['slice_only'] is True
    # Handler-only fixture; the original 58 retain the genuine paid/activation paths.
    return data['id']


@pytest.mark.parametrize('seat', [1, 2])
def test_native_bootstrap_complete_sql_readonly_child_and_same_epoch_raw_422(server, seat):
    identifier = position(server, seat)
    before = server.audit(identifier)
    status, _ = server.call(f'/matches/{identifier}/action', {'player_id': seat,
                          'action': {'type': 'choose_mechanic', 'card_ids': [], 'unknown': None}})
    assert status == 422 and stable(server.audit(identifier)) == stable(before)
    restored = server.restart(identifier, before)
    assert audit_identity(restored) == audit_identity(before)
    assert restored['raw_database_sha256'] != before['raw_database_sha256']
    assert restored['capacity_ledger'][0]['owner_epoch'] != before['capacity_ledger'][0]['owner_epoch']
    status, _ = server.call(f'/matches/{identifier}/action', {'player_id': seat,
                          'action': {'type': 'choose_mechanic', 'card_ids': [], 'unknown': None}})
    assert status == 422 and stable(server.audit(identifier)) == stable(restored)
    assert server.audit(identifier)['raw_database_sha256'] == restored['raw_database_sha256']


@pytest.mark.parametrize('kind', ['sql', 'ledger'])
def test_corrupted_persistent_sql_and_capacity_ledger_fail_independently(server, kind):
    identifier = position(server, 1)
    before = server.audit(identifier)
    path = server.data / f'negative-{kind}.sqlite3'
    server.restart(identifier, before, copy_to=path)
    copied = facts(path)
    engine = create_engine('sqlite:///' + str(path), connect_args={'check_same_thread': False})
    with owned_database(engine) as owner:
        clean = facts(path)
        bootstrap_transition(copied, clean, owner.epoch)
        with owner.mutex, owner.activity(threaded=False), engine.begin() as connection:
            if kind == 'sql':
                connection.exec_driver_sql("UPDATE activematchrecord SET updated_at='1999-01-01 00:00:00.000000' WHERE id=?", (identifier,))
            else:
                connection.exec_driver_sql('UPDATE resourcecapacity SET durable_bytes=durable_bytes+1 WHERE id=1')
        corrupted = facts(path)
        assert facts(path, identifier)['match']['state'] == before['state']
        assert facts(path, identifier)['match']['controller'] == before['controller']
        if kind == 'sql':
            assert corrupted['ledger'] == clean['ledger']
        else:
            without_capacity = lambda rows: [r for r in rows if not r.startswith('INSERT INTO "resourcecapacity"')]
            assert without_capacity(corrupted['sql']) == without_capacity(clean['sql'])
            with pytest.raises(AssertionError, match='Unauthorized capacity ledger transition'):
                bootstrap_transition(copied, corrupted, owner.epoch)
    assert owner.fd is None and not owner.producers and engine.pool.checkedout() == 0
    assert facts(path) == corrupted
    if kind == 'sql':
        # Give the worker the actual altered raw hash: only the complete SQL proof fails.
        expected = {**clean, 'raw_sha256': corrupted['raw_sha256']}
        index = len(list(server.data.glob('readonly-*.input.json')))
        with pytest.raises(AssertionError, match='Persistent gameplay SQL changed'):
            server.readonly(expected, identifier, before['pid'], audit=before, path=path)
        result = json.loads((server.data / f'readonly-{index}.output.json').read_text())
        assert result['facts'] == corrupted and result['connections_closed']
        assert result['failure'] == 'Persistent gameplay SQL changed in readonly worker'
