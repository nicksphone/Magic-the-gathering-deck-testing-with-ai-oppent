"""Pure repository doubles must retain the actual encoding/reservation contract."""
import json

import pytest

from analytics.resource_budget import RESOURCE_LIMITS, SimulationResourceLimit
from analytics.service import AnalyticsService
from persistence.capacity import CapacityIntegrityError
from persistence.models import ResourceReservation, StatsSnapshot
from tests.test_analytics_batch import _DummyRepo
from tests.pure_snapshot_support import pure_snapshot_storage


DECK = [{'quantity': 60, 'card_name': 'Island'}]


def test_real_snapshot_writer_consumes_reserved_bytes_and_rows():
    repo = _DummyRepo()
    result = AnalyticsService(repo).run_batch(DECK, DECK, matches=1, max_ticks=0)
    rows = repo.session.rows[StatsSnapshot]
    assert len(rows) == 1
    row = next(iter(rows.values()))
    assert row.label == 'batch_simulation'
    assert row.stats_json == json.dumps(result)
    assert repo.last == ('batch_simulation', result)
    assert repo.session.rows[ResourceReservation] == {}
    assert repo.session.ledger.durable_bytes == len(row.stats_json.encode('utf-8'))
    assert repo.session.ledger.snapshot_rows == 1
    assert repo.session.ledger.reserved_bytes == repo.session.ledger.reserved_snapshot_rows == 0
    assert not repo.session.owner.producers


def test_progress_failure_releases_reservation_without_writing_snapshot():
    repo = _DummyRepo()
    def fail(done, total):
        assert len(repo.session.rows[ResourceReservation]) == 1
        assert repo.session.owner.producers
        raise SimulationResourceLimit('result_json')
    with pytest.raises(SimulationResourceLimit, match='resource_limit:result_json'):
        AnalyticsService(repo).run_batch(DECK, DECK, matches=1, max_ticks=0, progress_callback=fail)
    assert repo.session.rows[StatsSnapshot] == repo.session.rows[ResourceReservation] == {}
    assert repo.session.ledger.durable_bytes == repo.session.ledger.reserved_bytes == 0
    assert repo.session.ledger.snapshot_rows == repo.session.ledger.reserved_snapshot_rows == 0
    assert not repo.session.owner.producers


def test_actual_snapshot_encoding_rejects_before_storage():
    repo = _DummyRepo()
    with pytest.raises(SimulationResourceLimit, match='resource_limit:snapshot_json'):
        repo.save_snapshot('too-large', {'padding': 'x' * (RESOURCE_LIMITS['snapshot_json_bytes'] + 1)})
    assert repo.session.rows[StatsSnapshot] == repo.session.rows[ResourceReservation] == {}
    assert repo.session.ledger.durable_bytes == 0


def test_actual_writer_rejects_missing_reservation_and_fences_owner():
    repo = _DummyRepo()
    with pytest.raises(CapacityIntegrityError, match='Snapshot reservation missing'):
        repo.save_snapshot('missing-token', {'ok': True}, reservation_token='absent')
    assert repo.session.rows[StatsSnapshot] == {}
    assert repo.session.owner.uncertain
    assert not repo.session.owner.admissions_open


def test_real_owner_lookup_for_nonfixture_session_remains_fail_closed():
    from types import SimpleNamespace
    from analytics import service
    with pytest.raises(CapacityIntegrityError, match='No capacity owner for Session'):
        service.owner_for(SimpleNamespace(get_bind=lambda: object()))
