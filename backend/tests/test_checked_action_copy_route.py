"""Real canonical120 actions: explicit full-history copy route and atomic isolation."""
from copy import deepcopy
import pickle
from types import FunctionType

import pytest

from game_state import copying
from game_state.serializers import serialize_match_snapshot
from rules_engine import action_validation
from rules_engine.engine import RulesEngine
from tests.test_root_metadata_copy_contract import canonical120


def standard_reference(state, rules, seat, action):
    """Same checked-action code/validators/engine, only root cloning uses stdlib."""
    def standard_copy(value, *, include_history):
        assert include_history is True
        return deepcopy(value)
    original = action_validation.checked_action
    namespace = dict(original.__globals__, deepcopy=deepcopy, copy_match_state=standard_copy)
    reference = FunctionType(original.__code__, namespace, original.__name__,
                             original.__defaults__, original.__closure__)
    return reference(state, rules, seat, action)


def position(seat):
    state = canonical120()
    assert len(state.cards) == 120
    state.active_player = state.priority_player = seat
    state.log.extend(['Retained checked-action history', 'Second retained entry'])
    return state


def attach_aliases(state):
    left, right = list(state.cards.values())[:2]
    shared = [{'markers': [1]}]
    state.copy_test_metadata = {'left': shared, 'right': shared}
    state.copy_test_self = state
    state.copy_test_attributes = state.__dict__
    state.copy_test_history = state.log
    left.copy_test_peer, right.copy_test_peer = right, left
    left.copy_test_attributes = right.__dict__
    left.copy_test_shared = right.copy_test_shared = shared
    return left.id, right.id


def assert_aliases(original, clone, ids):
    left, right = [clone.cards[cid] for cid in ids]
    shared = clone.copy_test_metadata['left']
    assert clone.copy_test_self is clone
    assert clone.copy_test_attributes is not clone.__dict__
    assert clone.copy_test_attributes['cards'] is clone.cards
    assert clone.copy_test_attributes['copy_test_self'] is clone
    assert clone.copy_test_history is clone.log and clone.log is not original.log
    assert left.copy_test_peer is right and right.copy_test_peer is left
    attrs = left.copy_test_attributes
    assert attrs['copy_test_peer'] is left
    assert attrs['copy_test_shared'] is shared
    assert attrs is not original.cards[ids[1]].__dict__
    assert shared is clone.copy_test_metadata['right'] is left.copy_test_shared is right.copy_test_shared
    assert shared is not original.copy_test_metadata['left']
    assert left is not original.cards[ids[0]] and right is not original.cards[ids[1]]


@pytest.mark.parametrize('seat', [1, 2])
def test_external_route_uses_shared_copier_with_explicit_full_history(seat, monkeypatch):
    state = position(seat)
    before = pickle.dumps(state, protocol=5)
    calls = []

    def observed(current, *, include_history):
        assert current is state and include_history is True
        result = copying.copy_match_state(current, include_history=include_history)
        calls.append(result)
        return result

    # Baseline lacks this binding: real action still succeeds, then RED is the route assertion.
    monkeypatch.setattr(action_validation, 'copy_match_state', observed, raising=False)
    clone = action_validation.checked_action(state, RulesEngine(), seat, {'type': 'keep_hand'})
    assert len(calls) == 1 and calls[0] is clone, 'checked_action bypassed the shared full-history copier'
    assert clone.log[:len(state.log)] == state.log and clone.log is not state.log
    assert pickle.dumps(state, protocol=5) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('transition', ['keep', 'resolve_mulligan'])
def test_accepted_values_rng_history_aliases_and_siblings_match_standard(seat, transition):
    state = position(seat)
    actor = seat
    if transition == 'resolve_mulligan':
        state = standard_reference(state, RulesEngine(), seat, {'type': 'mulligan'})
        actor = 3 - seat
    ids = attach_aliases(state)
    before = pickle.dumps(state, protocol=5)
    action = {'type': 'keep_hand'}
    expected = standard_reference(state, RulesEngine(), actor, deepcopy(action))
    actual = action_validation.checked_action(state, RulesEngine(), actor, deepcopy(action))
    sibling = action_validation.checked_action(state, RulesEngine(), actor, deepcopy(action))
    assert serialize_match_snapshot(actual) == serialize_match_snapshot(expected) == serialize_match_snapshot(sibling)
    assert actual.rng.getstate() == expected.rng.getstate() == sibling.rng.getstate()
    assert actual.rng is not state.rng and actual.rng is not sibling.rng
    assert actual.log[:len(state.log)] == state.log
    if transition == 'resolve_mulligan':
        assert actual.mulligan_count[seat] == 1
        assert actual.rng.getstate() != state.rng.getstate(), 'Real mulligan shuffle was not exercised'
    else:
        assert seat in actual.kept_hands and actual.mulligan_declarations[seat] == 'keep_hand'
    for clone in (expected, actual, sibling):
        assert_aliases(state, clone, ids)
    actual.copy_test_metadata['left'][0]['markers'].append(2)
    actual.log.append('Candidate-only diagnostic')
    actual.rng.random()
    actual.players[actor].mana_pool['G'] += 1
    actual.cards[ids[0]].counters['copy-test'] = 1
    assert sibling.copy_test_metadata['left'][0]['markers'] == [1]
    assert sibling.log == expected.log and sibling.rng.getstate() == expected.rng.getstate()
    assert serialize_match_snapshot(sibling) == serialize_match_snapshot(expected)
    assert pickle.dumps(state, protocol=5) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('rejection', ['wrong_actor', 'invalid_bottom_count'])
def test_rejected_request_matches_standard_and_preserves_complete_original(seat, rejection):
    state = position(seat)
    attach_aliases(state)
    before = pickle.dumps(state, protocol=5)
    actor = 3 - seat if rejection == 'wrong_actor' else seat
    action = {'type': 'keep_hand'}
    if rejection == 'invalid_bottom_count':
        action['bottom_card_ids'] = state.players[seat].hand[:1]
    messages = []
    for route in (standard_reference, action_validation.checked_action):
        with pytest.raises(action_validation.ActionRejected) as rejected:
            route(state, RulesEngine(), actor, deepcopy(action))
        messages.append(str(rejected.value))
        assert pickle.dumps(state, protocol=5) == before
    assert messages[0] == messages[1]


@pytest.mark.parametrize('seat', [1, 2])
def test_failure_after_genuine_transition_mutations_keeps_original_atomic(seat):
    class FailAfterTransition(RulesEngine):
        """Labeled failure injection AFTER the real accepted engine transition."""
        def take_action(self, candidate, actor, action, **kwargs):
            super().take_action(candidate, actor, action, **kwargs)
            assert actor in candidate.kept_hands
            candidate.rng.random()
            candidate.log.append('Injected post-transition failure')
            candidate.copy_test_metadata['left'][0]['markers'].append(2)
            candidate.players[actor].life -= 1
            raise action_validation.ActionRejected('injected-after-genuine-transition')

    state = position(seat)
    attach_aliases(state)
    before = pickle.dumps(state, protocol=5)
    for route in (standard_reference, action_validation.checked_action):
        with pytest.raises(action_validation.ActionRejected, match='injected-after-genuine-transition'):
            route(state, FailAfterTransition(), seat, {'type': 'keep_hand'})
        assert pickle.dumps(state, protocol=5) == before
