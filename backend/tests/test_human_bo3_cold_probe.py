"""Cold public reads use the committed worker, never an external audit gate."""
import os
from pathlib import Path

import pytest

import main
from tests.test_api_input_contracts import game, snapshot
from tests.test_human_bo3_readiness import finished


@pytest.mark.parametrize('seat', [1, 2])
def test_cold_read_preserves_each_partial_confirmation_and_complete_roots(game, seat):
    from tests.human_bo3_cold_probe import read_cold_match

    client, controller = game
    finished(controller, 3-seat)
    url = '/matches/' + controller.state.id
    assert client.post(url + '/sideboard', json={
        'player_id': seat, 'cards_out': [], 'cards_in': []}).status_code == 200
    before = snapshot(controller)
    read = read_cold_match(controller.state.id)
    assert read['pid'] != os.getpid() and read['readonly'] is True
    assert read['view']['sideboarding'][str(seat)]['applied']
    assert not read['view']['sideboarding'][str(3-seat)]['applied']
    assert snapshot(controller) == before
    assert read['controller'] == main._controller_snapshot(controller)


@pytest.mark.parametrize('bad_input', ['source', 'database'])
def test_cold_worker_rejects_foreign_source_or_database_before_project_read(monkeypatch, bad_input):
    from tests.human_bo3_cold_probe import run

    root = Path(__file__).resolve().parents[2]
    database = root / 'backend/mtg_lab.db'
    if bad_input == 'source':
        monkeypatch.setenv('MTG_ISOLATED_TEST_ROOT', '/tmp/not-this-source')
    else:
        database = root.parent / 'not-owned.sqlite'
    with pytest.raises(AssertionError):
        run(str(database), 'not-a-live-match')
