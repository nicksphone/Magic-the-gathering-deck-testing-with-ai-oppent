"""Shared materializer controls, independent of any stack-response selector."""
from copy import deepcopy

import pytest

from ai.agent import AIAgent
from ai.pending_effects import friendly_destruction_profit
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_ai_nonlethal_self_exile_response import response_pose
from tests.test_ai_own_only_sweeper import RAW
from tests.test_ai_recurring_engines import add
from tests.test_any_player_cast_damage import settle


RECEIPTS = []


def explicit_self_pose(seat):
    state, sword, bodies = response_pose(seat)
    enemy = add(state, 'Serra Angel', 3-seat, cards=RAW)
    enemy.summoning_sick = False
    move = next(move for move in RulesEngine().legal_moves(state, seat)
                if move.get('type') == 'cast_spell' and move.get('card_id') == sword)
    return state, {**move, 'targets': {'target_card_id': bodies[0]}}, bodies, enemy.id


@pytest.mark.parametrize('seat', [1, 2])
def test_direct_materializer_redirects_native_unprofitable_self_exile(seat):
    state, move, bodies, enemy = explicit_self_pose(seat)
    before, offered = serialize_match_snapshot(state), deepcopy(move)
    assert friendly_destruction_profit(state, seat, move) is False
    own_loss = settle(checked_action(state, RulesEngine(), seat, move))
    assert own_loss.cards[bodies[0]].zone == Zone.EXILE
    assert own_loss.players[seat].life == 11
    agent = AIAgent('master', 'Control', opponent_archetype='Burn')
    action = agent._materialize_action(state, move, seat)
    assert not action.get('_invalid_ai_choice')
    assert action['targets']['target_card_id'] == enemy
    result = settle(checked_action(state, RulesEngine(), seat, action))
    assert result.cards[enemy].zone == Zone.EXILE
    assert all(result.cards[cid].zone == Zone.BATTLEFIELD for cid in bodies)
    assert result.players[seat].life == 8 and result.players[3-seat].life == 10
    assert not result.stack and result.winner is None
    assert serialize_match_snapshot(state) == before and move == offered
    RECEIPTS.append({'case': 'native_redirect', 'seat': seat,
                     'action': action, 'root_pure': True})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('certificate', [True, None])
def test_provider_protocol_preserves_positive_or_unknown_self_exile(monkeypatch, seat, certificate):
    """Provider protocol only, not a canonical positive/unknown continuation."""
    state, move, bodies, enemy = explicit_self_pose(seat)
    before, offered = serialize_match_snapshot(state), deepcopy(move)
    calls = []

    def provider(game, player, action, *, own_choice_action=None):
        calls.append((game is state, player, action['targets']['target_card_id']))
        assert callable(own_choice_action)
        return certificate

    monkeypatch.setattr('ai.pending_effects.friendly_destruction_profit', provider)
    action = AIAgent('master', 'Control', opponent_archetype='Burn')._materialize_action(state, move, seat)
    assert calls and all(call == (True, seat, bodies[0]) for call in calls)
    assert not action.get('_invalid_ai_choice')
    assert action['targets']['target_card_id'] == bodies[0]
    assert action['targets']['target_card_id'] != enemy
    checked_action(state, RulesEngine(), seat, action)
    assert serialize_match_snapshot(state) == before and move == offered
    RECEIPTS.append({'case': 'provider_protocol_not_native_forecast', 'seat': seat,
                     'certificate': certificate, 'action': action, 'calls': len(calls),
                     'root_pure': True})
