"""Guarded native C12 regression; no saved input or model needed."""
import logging

from ai import pending_effects as projections
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from tests.test_pending_removal import fixture
from tests.regression_agent_wave2.support import add as add_canonical


def test_choice_free_native_batch_baseline_reuses_only_at_exact_scoped_root(monkeypatch):
    state, _, held = fixture()
    friend = add_canonical(state, 'Grizzly Bears', 1, Zone.BATTLEFIELD)
    action = {'type': 'cast_spell', 'card_id': held, 'targets': {}}
    native, calls = projections._destruction_baseline, []

    def counted(*args, **kwargs):
        calls.append(1)
        return native(*args, **kwargs)

    monkeypatch.setattr(projections, '_destruction_baseline', counted)

    def batch():
        return projections.unproductive_destroy_targets(
            state, state.cards[held], 1, {}, action=action,
            candidates={friend.id}, _native_shared_baseline=True)

    with projections.decision_projection_scope(state, 1):
        before = serialize_match_snapshot(state)
        assert friend.id in batch()
        assert friend.id in batch()
        assert serialize_match_snapshot(state) == before
        logging.warning('C12_REAL_NATIVE_BASELINES_TWO_SAME_ROOT_BATCHES=%d', len(calls))
        assert len(calls) == 1
        state.turn += 1
        assert friend.id in batch()
        assert len(calls) == 2
    assert friend.id in batch()
    assert len(calls) == 3


def test_callback_used_baseline_is_not_shared_across_native_batches(monkeypatch):
    state, _, held = fixture()
    friend = add_canonical(state, 'Grizzly Bears', 1, Zone.BATTLEFIELD)
    action = {'type': 'cast_spell', 'card_id': held, 'targets': {}}
    native, history = projections._destruction_baseline, []

    def callback(*args):
        history.append(len(history))
        return {'type': 'pass_priority'}

    def baseline_with_callback(root, seat, policy):
        policy(root, [], seat)
        return native(root, seat, policy)

    monkeypatch.setattr(projections, '_destruction_baseline', baseline_with_callback)
    with projections.decision_projection_scope(state, 1):
        for _ in range(2):
            projections.unproductive_destroy_targets(
                state, state.cards[held], 1, {}, action=action,
                candidates={friend.id}, own_choice_action=callback,
                _native_shared_baseline=True)
    assert history == [0, 1]
