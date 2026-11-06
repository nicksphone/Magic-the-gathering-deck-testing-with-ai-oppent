"""Endpoint utility only: native paid outcomes, not combat forecasts.

The existing Crypt Rats/Bolt fixture genuinely resolves the draw, loss and win.
Deliver those checked endpoints at the finishing seam to isolate retention of a
draw from rejection of a losing partial incumbent. No claim that these outcomes
are combat forecasts for the separate Hill Giant/Bears declaration fixture.
"""
from copy import deepcopy

import pytest

from ai.agent import AIAgent
from ai.pending_effects import combat_expansion_available, decision_projection_scope
from game_state.serializers import serialize_match_snapshot
from tests.test_ai_retained_block_intent import declared_combat
from tests.test_ai_terminal_draw_product import endpoints


@pytest.mark.parametrize('outcome', ['draw', 'loss', 'win'])
def test_partial_endpoint_retention_distinguishes_draw_from_defeat(endpoints, outcome, monkeypatch):
    seat, _, _, draw, loss, win = endpoints
    state, rules = declared_combat(seat, 3)
    terminal = {'draw': draw, 'loss': loss, 'win': win}[outcome]
    before, endpoint_before = serialize_match_snapshot(state), serialize_match_snapshot(terminal)
    assert terminal.winner == {'draw': 0, 'loss': 3 - seat, 'win': seat}[outcome]
    actor = AIAgent('master', archetype='Control')

    def finish_with_checked_endpoint(projected, original):
        assert original is state and projected is not state
        projected.__dict__.clear()
        projected.__dict__.update(deepcopy(terminal.__dict__))
        return True

    monkeypatch.setattr(actor, '_finish_combat_projection', finish_with_checked_endpoint)
    offered = next(move for move in rules.legal_moves(state, seat) if move['type'] == 'block')
    with decision_projection_scope(state, seat, 1):
        selected = actor._search_block_assignments(
            state, offered['attackers'], offered['blockers'], consider_next_combat=False)
        assert not combat_expansion_available()
    assert selected == (None if outcome == 'loss' else {})
    assert serialize_match_snapshot(state) == before
    assert serialize_match_snapshot(terminal) == endpoint_before
