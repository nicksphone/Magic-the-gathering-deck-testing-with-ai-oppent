"""Reuse an already computed predicate, not arbitrary callback/action results.

Scores/shortlists are explicitly synthetic; checked forecasts remain native.
"""
from copy import deepcopy
import inspect
import pickle

import pytest

from ai import learned_policy, pending_effects
from ai.agent import AIAgent
from ai.information import decision_view
from game_state.state import Step
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_learned_tactical_guard import _cast, _fixture, _route
from tests.test_live_learned_policy import _binding


def route_setup(monkeypatch, seat, win):
    state, cards = _fixture(seat)
    state.players[3-seat].life = 3 if win else 20
    actions = [_cast(state, cards, seat, 'Monastery Swiftspear'),
               _cast(state, cards, seat, 'Lightning Bolt', {'target_player': 3-seat})]
    selected, _ = _route(monkeypatch, state, seat, actions,
                         {'Monastery Swiftspear': .9, 'Lightning Bolt': -.9})
    assert selected == actions[1 if win else 0]
    return state, actions, selected


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('win', [False, True])
def test_native_agent_does_not_repeat_selected_same_horizon_forecast(monkeypatch, seat, win):
    state, actions, expected = route_setup(monkeypatch, seat, win)
    agent = AIAgent(difficulty='master', archetype='Burn', learned_binding=_binding(learned_policy))
    moves = agent.engine.legal_moves(deepcopy(state), seat)
    before = pickle.dumps((state, moves, vars(agent)), protocol=5)
    calls, repeated = [], []
    outcome = pending_effects._unanswered_action_outcome
    wins = pending_effects.unanswered_action_wins

    def observe(root, player, action, **options):
        calls.append(deepcopy(action))
        return outcome(root, player, action, **options)

    def outer(root, player, action, **options):
        repeated.append(deepcopy(action))
        return wins(root, player, action, **options)

    monkeypatch.setattr(pending_effects, '_unanswered_action_outcome', observe)
    monkeypatch.setattr(pending_effects, 'unanswered_action_wins', outer)
    decision = agent.choose_action(state, moves, seat)
    assert decision.action == expected
    assert calls == actions
    assert repeated == [], 'The same selected-action forecast was already complete'
    assert pickle.dumps((state, moves, vars(agent)), protocol=5) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('win', [False, True])
def test_provider_publishes_only_selected_action_exact_true_predicate(monkeypatch, seat, win):
    assert '_terminal_win' in inspect.signature(learned_policy.choose_learned_action).parameters
    state, _, expected = route_setup(monkeypatch, seat, win)
    rules = RulesEngine()
    moves = rules.legal_moves(deepcopy(state), seat)
    view, supplied = decision_view(state, seat, moves)
    receipt = []
    selected = learned_policy.choose_learned_action(
        _binding(learned_policy), AIAgent(difficulty='master', archetype='Burn'),
        view, supplied, seat, admit=lambda action: checked_action(state, rules, seat, action),
        _terminal_win=receipt)
    assert selected == expected and receipt == [win]


@pytest.mark.parametrize('seat', [1, 2])
def test_no_receipt_retains_original_outer_forecast(monkeypatch, seat):
    state, _, expected = route_setup(monkeypatch, seat, False)
    calls = []
    native = pending_effects.unanswered_action_wins

    def provider(*args, **kwargs):
        # Compatibility protocol: a provider that does not produce a receipt.
        return deepcopy(expected)

    def wins(*args, **kwargs):
        calls.append(True)
        return native(*args, **kwargs)

    monkeypatch.setattr(learned_policy, 'choose_learned_action', provider)
    monkeypatch.setattr(pending_effects, 'unanswered_action_wins', wins)
    agent = AIAgent(difficulty='master', archetype='Burn', learned_binding=_binding(learned_policy))
    assert agent.choose_action(state, agent.engine.legal_moves(deepcopy(state), seat), seat).action == expected
    assert calls == [True]


@pytest.mark.parametrize('seat', [1, 2])
def test_defensive_combat_horizon_retains_separate_original_forecast(monkeypatch, seat):
    from tests.test_learned_declared_combat_guard import _declared_combat
    state, _, _, block = _declared_combat(seat)
    _route(monkeypatch, state, seat, [{'type': 'pass_priority'}, block],
           {'pass_priority': .9, 'block': -.9})
    calls = []
    native = pending_effects.unanswered_action_wins

    def wins(root, player, action, **options):
        assert root.step == Step.DECLARE_BLOCKERS and root.active_player != player
        calls.append(options)
        return native(root, player, action, **options)

    monkeypatch.setattr(pending_effects, 'unanswered_action_wins', wins)
    agent = AIAgent(difficulty='master', archetype='Burn', learned_binding=_binding(learned_policy))
    before = pickle.dumps(state, protocol=5)
    assert agent.choose_action(state, agent.engine.legal_moves(deepcopy(state), seat), seat).action == block
    assert calls == [{}], 'The two combat horizons are not interchangeable'
    assert pickle.dumps(state, protocol=5) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_late_invalid_score_publishes_no_partial_receipt(monkeypatch, seat):
    assert '_terminal_win' in inspect.signature(learned_policy.choose_learned_action).parameters
    state, cards = _fixture(seat)
    burn = _cast(state, cards, seat, 'Lightning Bolt', {'target_player': 3-seat})
    creature = _cast(state, cards, seat, 'Monastery Swiftspear')
    selected, _ = _route(monkeypatch, state, seat, [burn, creature],
                         {'Lightning Bolt': .5, 'Monastery Swiftspear': {'q': float('nan'), 'v': 0.}})
    assert selected is None
    rules = RulesEngine()
    view, moves = decision_view(state, seat, rules.legal_moves(deepcopy(state), seat))
    receipt = []
    selected = learned_policy.choose_learned_action(
        _binding(learned_policy), AIAgent(), view, moves, seat,
        admit=lambda action: checked_action(state, rules, seat, action), _terminal_win=receipt)
    assert selected is None and receipt == []
