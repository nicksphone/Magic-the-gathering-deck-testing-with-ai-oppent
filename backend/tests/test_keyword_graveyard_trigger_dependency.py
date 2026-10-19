"""STRICT dependency ledger: efbd executor has no enters_graveyard producer.

Keep ordinary reds separate; no keyword patch invents a trigger or helper ABI.
"""
import pytest

from game_state.state import Zone
from tests.test_direct_graveyard_bypass_audit import (
    pending_sacrifice, select, install, main_controller_snapshot,
    public_private_restore, repo, client, base_client,
)
from tests.test_self_graveyard_replacement_audit import act, restart


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('foreign', [False, True])
def test_canonical_from_anywhere_graveyard_trigger_remains_respondable(seat, foreign, tmp_path):
    state, victim, _, _ = pending_sacrifice(seat, 'Kozilek, Butcher of Truth', foreign)
    result = restart(act(state, seat, select(victim)), tmp_path, 'graveyard-trigger')
    assert result.cards[victim.id].zone == Zone.GRAVEYARD
    receipts = [item for item in result.stack if item.source_card_id == victim.id]
    assert len(receipts) == 1, 'Shared entry executor must produce a real from-anywhere trigger'
    assert receipts[0].controller == victim.owner
    assert result.players[victim.owner].graveyard.count(victim.id) == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_http_real_graveyard_trigger_survives_cold_restore(repo, client, seat, tmp_path):
    state, victim, _, _ = pending_sacrifice(seat, 'Kozilek, Butcher of Truth')
    controller = install(repo, client, state)
    response = client.post('/matches/' + state.id + '/action', json={'player_id': seat, 'action': select(victim)})
    assert response.status_code == 200, response.text
    controller = public_private_restore(repo, client, controller, seat, tmp_path)
    assert controller.state.cards[victim.id].zone == Zone.GRAVEYARD
    receipts = [item for item in controller.state.stack if item.source_card_id == victim.id]
    assert len(receipts) == 1, 'HTTP must persist a real graveyard-entry trigger, not silently omit it'
