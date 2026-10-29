"""Real opening transitions; synthetic binding/spy tests, not trained-weight proof."""
from copy import deepcopy

import pytest

from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from game_state.state import MatchFactory, pregame_actor
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_live_learned_policy import _binding, _subject
from training.environment import _deck


def opening(seat):
    decks = [_deck('Burn'), _deck('Tribal')]
    if seat == 2:
        decks.reverse()
    state = MatchFactory.from_decks(*decks, seed=2063100 + seat)
    state.active_player = state.priority_player = seat
    return state


def forbid_pregame_projection(*_args, **_kwargs):
    raise AssertionError('Unqualified learned ranking entered opening-hand selection')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('phase', ['initial', 'bottom', 'after-bottom'])
def test_opening_decisions_preserve_normal_heuristics(monkeypatch, seat, phase):
    rules, state = RulesEngine(), opening(seat)
    baseline = AIAgent(difficulty='master', archetype='Burn', opponent_archetype='Tribal')
    if phase != 'initial':
        state = checked_action(state, rules, seat, {'type': 'mulligan'})
        state = checked_action(state, rules, 3-seat, {'type': 'keep_hand'})
        assert state.pending_mechanic_choice['kind'] == 'mulligan_bottom'
        if phase == 'after-bottom':
            decision = baseline.choose_action(state, rules.legal_moves(deepcopy(state), seat), seat)
            state = checked_action(state, rules, seat, decision.action)
            assert state.pending_mechanic_choice is None
    assert state.pregame_pending and pregame_actor(state) == seat
    moves = rules.legal_moves(deepcopy(state), seat)
    before, original_moves = serialize_match_snapshot(state), deepcopy(moves)
    expected = baseline.choose_action(state, moves, seat)
    module = _subject()
    binding = _binding(module)
    monkeypatch.setattr(module, 'decision_inputs_from_view', forbid_pregame_projection)
    agent = AIAgent(difficulty='master', archetype='Burn', opponent_archetype='Tribal',
                    learned_binding=binding)
    actual = agent.choose_action(state, moves, seat)
    assert actual.action == expected.action and actual.reasoning == expected.reasoning
    assert agent.learned_binding is binding
    assert serialize_match_snapshot(state) == before and moves == original_moves
    checked_action(state, rules, seat, actual.action)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_complete_opening_never_uses_untrained_mulligan_ranking(monkeypatch, seat):
    rules, state = RulesEngine(), opening(seat)
    module = _subject()
    binding = _binding(module)
    monkeypatch.setattr(module, 'decision_inputs_from_view', forbid_pregame_projection)
    agents = {pid: AIAgent(difficulty='master', archetype='Burn' if pid == seat else 'Tribal',
                          opponent_archetype='Tribal' if pid == seat else 'Burn',
                          learned_binding=binding) for pid in (1, 2)}
    for _ in range(20):
        if not state.pregame_pending:
            break
        actor = pregame_actor(state)
        before = serialize_match_snapshot(state)
        moves = rules.legal_moves(deepcopy(state), actor)
        decision = agents[actor].choose_action(state, moves, actor)
        assert serialize_match_snapshot(state) == before
        state = checked_action(state, rules, actor, decision.action)
    assert not state.pregame_pending and state.kept_hands == {1, 2}
    assert all(state.mulligan_count[pid] <= 2 for pid in (1, 2))
    assert all(len(state.players[pid].hand) >= 5 for pid in (1, 2))
