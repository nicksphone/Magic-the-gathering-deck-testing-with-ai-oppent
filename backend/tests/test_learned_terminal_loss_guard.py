"""Public canonical stack-defense audit, not a fitted-model failure claim.

Factory birth and declared battlefield/life pose reuse existing goldens. The
opponent really pays for Bolt and passes priority; no StackItem is fabricated.
Only shortlist/Q are synthetic. Core checked outcomes must pass before routing.
"""
from copy import deepcopy

import pytest

from ai.information import decision_view
from ai.pending_effects import unanswered_action_loses, unanswered_action_wins
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_ai_strategy_fundamentals import position
from tests.test_learned_tactical_guard import _cast, _route


RULES = RulesEngine()


def _paid_threat(seat, life):
    state, cards, _, move = position(seat, ['Counterspell'], ['Island'] * 3,
                                    reserve=['Lightning Bolt', 'Mountain'])
    state.players[seat].life = life
    bolt = move('Lightning Bolt', 3-seat, Zone.HAND)
    mountain = move('Mountain', 3-seat, Zone.BATTLEFIELD)
    state.active_player = state.priority_player = 3-seat
    state = checked_action(state, RULES, 3-seat,
        {'type': 'cast_spell', 'card_id': bolt, 'targets': {'target_player': seat}})
    assert state.cards[mountain].tapped and state.stack[-1].source_card_id == bolt
    state = checked_action(state, RULES, 3-seat, {'type': 'pass_priority'})
    assert state.priority_player == seat
    counter = _cast(state, cards, seat, 'Counterspell',
                    {'target_stack_id': state.stack[-1].id})
    return state, cards, bolt, counter


def _settle(state):
    for _ in range(8):
        assert not (state.pending_mechanic_choice or state.pending_replacement_choice
                    or state.pending_trigger_order), 'Do not force unknown choices'
        if state.winner is not None or not state.stack:
            return state
        state = checked_action(state, RULES, state.priority_player,
                               {'type': 'pass_priority'})
    raise AssertionError('Checked no-response settlement exceeded audit bound')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('life', [3, 6], ids=['lethal', 'nonlethal-control'])
def test_known_terminal_stack_loss_has_a_real_counter_alternative(monkeypatch, seat, life):
    state, cards, bolt, counter = _paid_threat(seat, life)
    before = serialize_match_snapshot(state)
    wait = {'type': 'pass_priority'}
    passed = _settle(checked_action(state, RULES, seat, wait))
    defended = _settle(checked_action(state, RULES, seat, counter))
    assert passed.winner == (3-seat if life == 3 else None)
    assert passed.players[seat].life == life - 3
    assert defended.winner is None and defended.players[seat].life == life
    assert defended.cards[bolt].zone == Zone.GRAVEYARD
    assert defended.cards[cards['Counterspell']].zone == Zone.GRAVEYARD
    assert sum(defended.cards[cid].tapped for cid in defended.players[seat].battlefield) == 2
    moves = RULES.legal_moves(deepcopy(state), seat)
    view, _ = decision_view(state, seat, moves)
    assert unanswered_action_loses(view, seat, wait) is (life == 3)
    assert unanswered_action_loses(view, seat, counter) is False
    assert unanswered_action_wins(view, seat, wait) is False
    assert unanswered_action_wins(view, seat, counter) is False
    assert serialize_match_snapshot(state) == before
    action, calls = _route(monkeypatch, state, seat, [wait, counter],
                           {'pass_priority': 0.9, 'Counterspell': -0.9})
    assert calls['scored'] == ['pass_priority', 'Counterspell']
    assert serialize_match_snapshot(state) == before
    assert action == (counter if life == 3 else wait), (
        'Synthetic-Q audit: avoid a known terminal loss when an admitted counter survives')
