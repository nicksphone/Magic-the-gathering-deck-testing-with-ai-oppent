"""Single-forecast protocol checks and real checked canonical outcomes.

Synthetic outcome/exception checks measure call semantics, not game strength.
"""
from copy import deepcopy
import pickle

import pytest

from ai import pending_effects


def subject():
    function = getattr(pending_effects, 'unanswered_action_classification', None)
    assert callable(function), 'Missing one-forecast terminal classification'
    return function


@pytest.mark.parametrize('settle', [False, True])
@pytest.mark.parametrize('outcome,expected', [
    (None, (None, None)), ('win', (True, None)),
    ('loss', (False, True)), ('neutral', (False, False)),
    ('rejected', (False, False)),
])
def test_classification_runs_exactly_one_complete_forecast(monkeypatch, settle, outcome, expected):
    classify = subject()
    state, action = object(), {'type': 'pass_priority'}
    seen = []

    def forecast(root, seat, move, **options):
        assert root is state and seat == 2 and move is action
        seen.append(options)
        return outcome

    monkeypatch.setattr(pending_effects, '_unanswered_action_outcome', forecast)
    assert classify(state, 2, action, settle_declared_combat=settle) == expected
    assert seen == [{'settle_declared_combat': settle}]


@pytest.mark.parametrize('error', [ValueError('protocol uncertainty'), RuntimeError('protocol fault')])
def test_classification_preserves_exception_identity_without_retry(monkeypatch, error):
    classify = subject()
    seen = []

    def forecast(*args, **kwargs):
        seen.append(True)
        raise error

    monkeypatch.setattr(pending_effects, '_unanswered_action_outcome', forecast)
    with pytest.raises(type(error)) as caught:
        classify(object(), 1, {'type': 'pass_priority'})
    assert caught.value is error and seen == [True]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind,expected', [
    ('win', (True, None)), ('loss', (False, True)),
    ('neutral', (False, False)), ('rejected', (False, False)),
    ('unknown', (None, None)),
])
def test_checked_canonical_outcomes_match_previous_public_pair(seat, kind, expected):
    classify = subject()
    from ai.information import decision_view
    from rules_engine.action_validation import checked_action
    from rules_engine.engine import RulesEngine
    from tests.test_ai_strategy_fundamentals import position
    from tests.test_learned_tactical_guard import _cast

    rules = RulesEngine()
    state, cards, _, _ = position(seat, ['Lightning Bolt', 'Opt'], ['Mountain', 'Island'])
    state.players[seat].life = 3 if kind == 'loss' else 20
    state.players[3-seat].life = 3 if kind == 'win' else 20
    action = _cast(state, cards, seat, 'Lightning Bolt',
                   {'target_player': seat if kind == 'loss' else 3-seat})
    if kind == 'rejected':
        action['targets'] = {'target_card_id': 'missing-target'}
    elif kind == 'unknown':
        state = checked_action(state, rules, seat, _cast(state, cards, seat, 'Opt'))
    moves = rules.legal_moves(deepcopy(state), seat)
    view, _ = decision_view(state, seat, moves)
    before = pickle.dumps((state, view, moves, action), protocol=5)
    win = pending_effects.unanswered_action_wins(view, seat, action, settle_declared_combat=True)
    loss = (pending_effects.unanswered_action_loses(view, seat, action, settle_declared_combat=True)
            if win is False else None)
    assert (win, loss) == expected
    assert classify(view, seat, action, settle_declared_combat=True) == expected
    assert pickle.dumps((state, view, moves, action), protocol=5) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_learned_router_forecasts_each_candidate_once(monkeypatch, seat):
    # Only the existing shortlist/Q are synthetic; the forecast remains native.
    from tests.test_learned_tactical_guard import _cast, _fixture, _route

    state, cards = _fixture(seat)
    actions = [_cast(state, cards, seat, 'Monastery Swiftspear'),
               _cast(state, cards, seat, 'Lightning Bolt', {'target_player': 3-seat})]
    seen = []
    native = pending_effects._unanswered_action_outcome

    def forecast(root, player, action, **options):
        seen.append(deepcopy(action))
        return native(root, player, action, **options)

    monkeypatch.setattr(pending_effects, '_unanswered_action_outcome', forecast)
    chosen, calls = _route(monkeypatch, state, seat, actions,
                           {'Monastery Swiftspear': .9, 'Lightning Bolt': -.9})
    assert calls['scored'] == ['Monastery Swiftspear', 'Lightning Bolt']
    assert chosen == actions[1]
    assert seen == actions, 'Each checked candidate needs one complete terminal forecast'
