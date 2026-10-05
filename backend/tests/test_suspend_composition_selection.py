"""Composed production selection hooks must not be displaced by idle Suspend."""
import pickle

import pytest

from ai.action_contract import complete_action
from ai.pending_effects import planning_copy
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from game_state.state import Zone
from tests.test_ai_selection_activation_policy import position, policy_agent, STYLES
from tests.test_suspend_lifecycle import CARDS, add, restore


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('style', STYLES)
@pytest.mark.parametrize('difficulty', ['strong', 'master'])
@pytest.mark.parametrize('scenario', ['favorable', 'reservation', 'deploy'])
def test_suspend_preserves_selection_reservation_and_deployment(seat, style, difficulty, scenario):
    state, source = position(seat, scenario)
    state.turn = 1
    card = add(state, 'Ancestral Vision', seat, Zone.HAND, cards=CARDS)
    # Keep own submitted inventory coherent; no inspection of hidden instances.
    state.starting_decks[seat].append({**CARDS['Ancestral Vision'],
                                      'card_name': 'Ancestral Vision', 'quantity': 1})
    rules = RulesEngine()
    before = pickle.dumps(state, 5)
    legal = rules.legal_moves(state, seat)
    assert any(m['type'] == 'suspend' and m['card_id'] == card.id for m in legal)
    action = complete_action(policy_agent(style, difficulty).choose_action(state, legal, seat).action)
    expected = {'favorable': 'activate_ability', 'reservation': 'pass_priority', 'deploy': 'cast_spell'}
    assert action['type'] == expected[scenario], action
    if scenario == 'favorable': assert action['card_id'] == source.id
    if scenario == 'deploy': assert state.cards[action['card_id']].name == 'Serra Angel'
    accepted = checked_action(state, rules, seat, action)
    assert accepted is not state
    assert pickle.dumps(state, 5) == before
    altered = planning_copy(state)
    for player in altered.players.values(): player.library.reverse()
    altered_before = pickle.dumps(altered, 5)
    assert complete_action(policy_agent(style, difficulty).choose_action(
        altered, rules.legal_moves(altered, seat), seat).action) == action
    assert pickle.dumps(altered, 5) == altered_before
    restored = restore(state)
    assert complete_action(policy_agent(style, difficulty).choose_action(
        restored, rules.legal_moves(restored, seat), seat).action) == action
