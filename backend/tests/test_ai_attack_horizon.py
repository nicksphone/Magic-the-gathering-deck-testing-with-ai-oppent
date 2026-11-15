"""Conditional combat valuation must not erase genuine response windows."""
from copy import deepcopy

import pytest

from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from game_state.state import Step, Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_ai_strategy_fundamentals import position


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('boundary', ['own-permanent', 'opponent-hand'])
def test_master_values_unanswered_winning_attack_past_the_priority_horizon(seat, boundary):
    state, _, _, move = position(seat, [], ['Forest'] * 8,
        reserve=['Sheoldred, the Apocalypse', 'Shark Typhoon', 'Lightning Bolt'])
    attacker = move('Sheoldred, the Apocalypse', seat, Zone.BATTLEFIELD)
    if boundary == 'own-permanent':
        move('Shark Typhoon', seat, Zone.BATTLEFIELD)
    else:
        move('Lightning Bolt', 3-seat, Zone.HAND)
    state.turn = 14
    state.step = Step.DECLARE_ATTACKERS
    state.players[3-seat].life = 4
    before = serialize_match_snapshot(state)
    agent = AIAgent(difficulty='master', archetype='Ramp')
    decision = agent.choose_action(state, RulesEngine().legal_moves(deepcopy(state), seat), seat)
    assert serialize_match_snapshot(state) == before
    assert decision.action['type'] == 'attack' and attacker in decision.action['attackers']
    announced = checked_action(state, RulesEngine(), seat, decision.action)
    assert announced.winner is None and announced.players[3-seat].life == 4
    assert announced.attackers_declared and announced.attackers == [attacker]
    assert agent._complete_strategic_combat_leaf(announced, seat) is None


@pytest.mark.parametrize('seat', [1, 2])
def test_horizon_preserves_a_real_paid_response_and_does_not_assume_empty_blocks(seat):
    state, _, enemy, move = position(seat, [], ['Forest'] * 8,
        enemy=['Sheoldred, the Apocalypse'], reserve=['Sheoldred, the Apocalypse', 'Lightning Bolt', 'Mountain'])
    attacker = move('Sheoldred, the Apocalypse', seat, Zone.BATTLEFIELD)
    bolt = move('Lightning Bolt', 3-seat, Zone.HAND)
    move('Mountain', 3-seat, Zone.BATTLEFIELD)
    state.turn = 14
    state.step = Step.DECLARE_ATTACKERS
    state.players[3-seat].life = 4
    engine = RulesEngine()
    announced = checked_action(state, engine, seat, {'type': 'attack', 'attackers': [attacker]})
    reply = checked_action(announced, engine, seat, {'type': 'pass_priority'})
    paid = checked_action(reply, engine, 3-seat, {'type': 'cast_spell', 'card_id': bolt,
        'targets': {'target_player': seat}})
    assert paid.stack and paid.cards[bolt].zone == Zone.STACK
    agent = AIAgent(difficulty='master', archetype='Ramp')
    outcome = agent._forecast_strategic_combat(announced)
    assert outcome is not None and outcome.winner != seat
    assert outcome.cards[enemy['Sheoldred, the Apocalypse']].zone == Zone.GRAVEYARD
    assert outcome.cards[attacker].zone == Zone.GRAVEYARD
    assert agent._forecast_strategic_combat(paid) is None
