"""Selected-target work admission; generic destruction forecasts are unchanged."""
from copy import deepcopy
import pickle

import pytest

from ai.agent import AIAgent
from ai import pending_effects as p
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from tests.test_pending_removal import fixture, add_card


def position():
    state, opponent, held = fixture()
    state.stack.clear()
    state.priority_player = 1
    friends = [add_card(state, 'Sprite Dragon', Zone.BATTLEFIELD, 1).id for _ in range(2)]
    actor = AIAgent('strong')
    move = next(row for row in actor.engine.legal_moves(state, 1) if row.get('card_id') == held)
    return state, actor, move, friends, opponent


@pytest.mark.parametrize('side', ['friendly', 'opponent', 'invalid'])
def test_selected_target_does_not_forecast_unrelated_friends(monkeypatch, side):
    state, actor, move, friends, opponent = position()
    selected = friends[0] if side == 'friendly' else opponent if side == 'opponent' else 'missing-target'
    announced = {**move, 'targets': {'target_card_id': selected}}
    before = pickle.dumps((state, announced), protocol=5)
    profit, visits = p.friendly_destruction_profit, []
    def observed(root, seat, action, **kwargs):
        visits.append(action['targets']['target_card_id'])
        return profit(root, seat, action, **kwargs)
    monkeypatch.setattr(p, 'friendly_destruction_profit', observed)
    result = actor._materialize_action(state, announced, 1, allow_friendly_target=True)
    assert result['targets']['target_card_id'] == selected
    if side == 'invalid':
        with pytest.raises(ActionRejected):
            checked_action(state, actor.engine, 1, result)
    else:
        checked_action(state, actor.engine, 1, result)
    assert visits == ([selected] if side == 'friendly' else [])
    assert pickle.dumps((state, announced), protocol=5) == before


@pytest.mark.parametrize('targets', [{}, {'target_card_id': ''}])
def test_unselected_move_still_considers_all_offered_friendly_targets(monkeypatch, targets):
    state, actor, move, friends, opponent = position()
    move = {**move, 'targets': targets}
    profit, visits = p.friendly_destruction_profit, []
    def observed(root, seat, action, **kwargs):
        visits.append(action['targets']['target_card_id'])
        return profit(root, seat, action, **kwargs)
    monkeypatch.setattr(p, 'friendly_destruction_profit', observed)
    result = actor._materialize_action(state, move, 1)
    assert set(visits) == set(friends)
    assert result['targets']['target_card_id'] == opponent


@pytest.mark.parametrize('shape', [
    'linked_target_pairs', 'required_target_instance_count',
    'required_distinct_target_count', 'supports_divide', 'target_card_ids', 'target_distribution',
])
def test_retargeting_or_multiple_target_protocol_keeps_full_candidate_set(monkeypatch, shape):
    state, actor, move, friends, opponent = position()
    move = deepcopy(move)
    move['targets'] = {'target_card_id': friends[0]}
    if shape == 'target_card_ids':
        move['targets'][shape] = friends
    elif shape == 'target_distribution':
        move['targets'][shape] = {friends[0]: 1}
    else:
        # Shape-only protocol: stop before interpreting this added hint as rules.
        move['target_hints'][shape] = True
    seen = []
    class Captured(Exception):
        pass
    def capture(*args, **kwargs):
        seen.append(kwargs['candidates'])
        raise Captured
    monkeypatch.setattr(p, 'unproductive_destroy_targets', capture)
    with pytest.raises(Captured):
        actor._materialize_action_without_resources(state, move, 1)
    assert len(seen) == 1 and set(friends + [opponent]).issubset(seen[0])
