"""A failed BO3 testpilot must still release the application's real DB owner."""
import pytest
from fastapi.testclient import TestClient

import main
from ai.agent import AIAgent
from persistence.capacity import owner_for_engine
from persistence.db import engine
from tests import test_human_bo3_native_swaps as native_swaps


class StopTestpilot(RuntimeError):
    pass


def test_native_swap_fixture_exception_does_not_poison_the_next_lifespan(monkeypatch, tmp_path):
    monkeypatch.setenv('MTG_HUMAN_BO3_EVIDENCE', str(tmp_path))

    def stop_after_real_match_start(*args, **kwargs):
        owner_for_engine(engine).require()
        raise StopTestpilot('Stop at the first testpilot decision')

    monkeypatch.setattr(AIAgent, 'choose_action', stop_after_real_match_start)
    with pytest.raises(StopTestpilot):
        native_swaps.test_native_swaps_between_checked_human_games()
    with TestClient(main.app) as client:
        owner_for_engine(engine).require()
        assert client.get('/health').status_code == 200
    assert engine.pool.checkedout() == 0
