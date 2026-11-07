"""Projection protocol bounds; private matched-game replay is kept separately."""
import pytest

from ai.pending_effects import _settle_announced_stack, planning_copy
from game_state.serializers import serialize_match_snapshot
from tests.test_effect_cast_choices import permission


@pytest.mark.parametrize('seat', [1, 2])
def test_same_pending_choice_is_not_recursively_forecast(seat):
    state, _ = permission(seat)
    before = serialize_match_snapshot(state)
    calls = []

    def choose(projected, legal, player):
        calls.append(player)
        assert len(calls) == 1, 'Repeated forecast invoked the policy again'
        # A no-action baseline reaches this same real permission again.
        assert not _settle_announced_stack(planning_copy(projected),
            player_id=player, own_choice_action=choose)
        return {'type': 'choose_mechanic', 'card_ids': ['decline']}

    for _ in range(2):
        calls.clear()
        assert _settle_announced_stack(planning_copy(state),
            player_id=seat, own_choice_action=choose)
        assert calls == [seat]
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_changing_nested_forecasts_are_bounded_but_not_claimed_resolved(seat):
    state, _ = permission(seat)
    calls, frontiers = [], []

    def choose(projected, legal, player):
        calls.append(projected.turn)
        assert len(calls) <= 8, 'Distinct nested forecasts exceeded the depth bound'
        next_state = planning_copy(projected)
        next_state.turn += 1
        next_state.pending_mechanic_choice['label'] = f'Distinct protocol choice {len(calls)}'
        frontiers.append(_settle_announced_stack(next_state,
            player_id=player, own_choice_action=choose))
        return {'type': 'choose_mechanic', 'card_ids': ['decline']}

    assert _settle_announced_stack(planning_copy(state),
        player_id=seat, own_choice_action=choose)
    assert len(calls) == 8
    assert frontiers == [False] + [True] * 7


@pytest.mark.parametrize('seat', [1, 2])
def test_same_choice_in_a_changed_counterfactual_is_still_a_cycle(seat):
    state, _ = permission(seat)
    calls = []

    def choose(projected, legal, player):
        calls.append(player)
        assert len(calls) == 1, 'The same permission was ranked recursively'
        changed = planning_copy(projected)
        changed.players[player].life -= 1
        changed.log.append('Counterfactual history is not a new pending choice')
        assert not _settle_announced_stack(changed,
            player_id=player, own_choice_action=choose)
        return {'type': 'choose_mechanic', 'card_ids': ['decline']}

    assert _settle_announced_stack(planning_copy(state), player_id=seat, own_choice_action=choose)
    assert calls == [seat]


@pytest.mark.parametrize('seat', [1, 2])
def test_failed_policy_does_not_leave_a_stale_active_choice(seat):
    state, _ = permission(seat)

    def fail(*args):
        raise RuntimeError('policy failure remains visible')

    with pytest.raises(RuntimeError, match='policy failure remains visible'):
        _settle_announced_stack(planning_copy(state), player_id=seat, own_choice_action=fail)
    assert _settle_announced_stack(planning_copy(state), player_id=seat,
        own_choice_action=lambda *_: {'type': 'choose_mechanic', 'card_ids': ['decline']})
