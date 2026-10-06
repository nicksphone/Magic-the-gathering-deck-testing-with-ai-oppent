"""Unmarked source-overlap HTTP acceptance; memory SQLite and local ASGI only."""
import pytest

from tests.test_spell_cost_overlap_http_investigation import isolated_api
from tests import test_spell_cost_overlap_http_investigation as repro


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Village Rites', 'Tormenting Voice'])
def test_source_consumption_is_422_and_atomic(isolated_api, seat, name):
    repro.test_http_source_overlap_is_controlled_rejection_with_atomic_root_and_db(isolated_api, seat, name)
