"""Canonical payoff with real actor choices; synthetic Q is not model acceptance."""
from copy import deepcopy

import pytest

from ai import pending_effects
from ai.action_contract import complete_action
from ai.agent import AIAgent
from ai.information import decision_view
from rules_engine.action_validation import checked_action
from tests.test_learned_endstep_payment_preference import RULES, offered, position, route, settle


@pytest.mark.parametrize('seat', [1, 2])
def test_known_payoff_requires_actual_actor_choice_and_matches_paid_outcome(monkeypatch, seat):
    state, ids = position(seat, lands=2, artist=True)
    moves = offered(state, seat, ids['Serra Angel'])
    cast = next(move for move in moves if move['type'] == 'cast_spell')
    declaration = complete_action(AIAgent('master', 'Control')._materialize_action(state, cast, seat))
    view, _ = decision_view(state, seat, moves)
    original = pending_effects.unanswered_action_classification
    assert original(view, seat, declaration, settle_declared_combat=True) == (None, None)
    choices = []

    def observe_forecast(projected, actor, action, **kwargs):
        policy = kwargs.get('own_choice_action')
        if policy is not None:
            def observe_choice(branch, legal, chooser):
                assert chooser == actor == seat
                chosen = policy(branch, legal, chooser)
                choices.append(deepcopy(chosen))
                return chosen
            kwargs['own_choice_action'] = observe_choice
        return original(projected, actor, action, **kwargs)

    monkeypatch.setattr(pending_effects, 'unanswered_action_classification', observe_forecast)
    action, calls = route(monkeypatch, state, seat, moves)
    assert calls['classes'][0][1] == (True, None)
    assert any(choice['type'] == 'choose_trigger_target' and choice.get('target_player') == 3-seat
               for choice in choices)
    assert action['cost_choice']['sacrifice_card_ids'] == [ids['Serra Angel']]
    assert settle(checked_action(state, RULES, seat, action)).winner == seat
