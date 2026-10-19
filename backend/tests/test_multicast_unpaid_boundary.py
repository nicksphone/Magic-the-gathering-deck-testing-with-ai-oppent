"""Additional HTTP qualifier: canonical hidden opponent has no mana to cast."""
import pytest

from tests import test_multicast_subject_audit as audit
from tests.test_spell_trigger_surface_audit import offline_http


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('accept', [False, True])
def test_http_unpaid_clauses_with_stable_opponent_hand(request, offline_http, monkeypatch, seat, accept):
    original_position = audit.position

    def canonical_position(*args, **kwargs):
        state, source = original_position(*args, **kwargs)
        state.players[3-seat].mana_pool = {}
        return state, source

    monkeypatch.setattr(audit, 'position', canonical_position)
    audit.test_actual_private_http_multi_cast_order_life_hand_board_restart(
        request, offline_http, seat, accept)
