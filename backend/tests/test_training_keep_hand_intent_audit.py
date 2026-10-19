"""KeepAction is not the current London pending MechanicChoice surface."""
from copy import deepcopy

import pytest
from pydantic import ValidationError

from api_contracts import KeepAction
from rules_engine.action_validation import ActionRejected
from training.environment import TrainingEnvironment, encode_action
from tests.test_selected_mana_http import game, retain, restart, rejected, forbid_external_network
from tests.test_training_suspend_intent_audit import isolated_source, assert_private


def opening(seat, legacy_bottom=False):
    env = TrainingEnvironment()
    env.reset(seed=314)
    env._state.active_player = env._state.priority_player = seat
    if legacy_bottom:
        # Supported legacy unbottomed resume boundary, not a fabricated legal hint.
        env._state.mulligan_count[seat] = 2
    selected = list(reversed(env._state.players[seat].hand[1:3])) if legacy_bottom else []
    return env, {'type': 'keep_hand', 'bottom_card_ids': selected}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('field,value', [
    ('card_ids', ['requested-bottom']), ('card_ids', None),
    ('bottom_count', 2), ('bottom_count', None),
    ('player_id', 1), ('player_id', None),
    ('resolving_item', {'phase': 'mulligan'}), ('resolving_item', None),
])
def test_keep_hand_unsupported_fields_reject_before_normalization(game, seat, field, value):
    env, action = opening(seat, True)
    request = {**action, field: value}
    before, original = env.snapshot(), deepcopy(request)
    with pytest.raises(ValidationError):
        KeepAction.model_validate(request)
    with pytest.raises(ActionRejected):
        env.lookup(request, seat)
    client, match = game
    retain(match, env)
    assert rejected(client, match, request, seat).status_code == 422
    assert_private(env, seat)
    try:
        with pytest.raises(ActionRejected):
            env.lookup_intent(request, seat)
    finally:
        assert env.snapshot() == before and request == original


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('legacy_bottom', [False, True])
@pytest.mark.parametrize('whole_view', [False, True])
def test_deliberate_keep_selection_wholeview_replay_privacy_http_restart(game, seat, legacy_bottom, whole_view):
    env, action = opening(seat, legacy_bottom)
    before, hand = env.snapshot(), list(env._state.players[seat].hand)
    hint = next(m for m in env._rules.legal_moves(deepcopy(env._state), seat) if m['type'] == 'keep_hand')
    assert hint == {'type': 'keep_hand'}
    # Deliberately augment the bare view; never infer bottom IDs from it.
    intent = {**hint, 'bottom_card_ids': action['bottom_card_ids']} if whole_view else action
    assert env.lookup_intent(intent, seat) == env.lookup(action, seat)
    if legacy_bottom:
        with pytest.raises(ActionRejected):
            env.lookup_intent(hint, seat)
    assert env.snapshot() == before
    fork = TrainingEnvironment()
    fork.restore(before)
    env.step(encode_action(action))
    fork.step(action)
    assert env.snapshot() == fork.snapshot()
    selected = action['bottom_card_ids']
    assert env._state.players[seat].hand == [cid for cid in hand if cid not in selected]
    assert env._state.players[seat].library[:len(selected)] == selected
    assert_private(env, seat)
    assert_private(env, 3-seat)
    original = TrainingEnvironment()
    original.restore(before)
    client, match = game
    identifier = retain(match, original)
    restart(identifier)
    public = next(m for m in client.get(f'/matches/{identifier}/legal-moves?player_id={seat}').json()['moves']
                  if m['type'] == 'keep_hand')
    assert public == hint
    assert original.lookup_intent({**public, 'bottom_card_ids': selected}, seat) == original.lookup(action, seat)
    rejected(client, match, action, 3-seat)
    response = client.post(f'/matches/{identifier}/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    state = restart(identifier).state
    assert state.players[seat].hand == [cid for cid in hand if cid not in selected]
    assert state.players[seat].library[:len(selected)] == selected


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('invalid', ['duplicate', 'opponent', 'stale', 'count', 'null'])
def test_keep_deliberate_invalid_bottoms_atomic(game, seat, invalid):
    env, action = opening(seat, True)
    chosen = action['bottom_card_ids']
    action['bottom_card_ids'] = {
        'duplicate': [chosen[0], chosen[0]],
        'opponent': env._state.players[3-seat].hand[:2],
        'stale': ['stale-card', chosen[0]], 'count': chosen[:1], 'null': None,
    }[invalid]
    before = env.snapshot()
    for method in (env.lookup, env.lookup_intent):
        with pytest.raises(ActionRejected):
            method(action, seat)
        assert env.snapshot() == before
    client, match = game
    retain(match, env)
    rejected(client, match, action, seat)


@pytest.mark.parametrize('seat', [1, 2])
def test_current_london_two_rounds_explicit_private_choices_and_restart(game, seat):
    env, _ = opening(seat)
    for round_count in (1, 2):
        env.step({'type': 'mulligan'})
        env.step({'type': 'mulligan'})
        for actor in (seat, 3-seat):
            assert env.acting_seat == actor
            assert env._state.pending_mechanic_choice['kind'] == 'mulligan_bottom'
            selected = list(reversed(env._state.players[actor].hand[1:1+round_count]))
            before = env.snapshot()
            assert_private(env, actor)
            assert_private(env, 3-actor)
            with pytest.raises(ActionRejected):
                env.lookup_intent({'type': 'keep_hand', 'bottom_card_ids': selected}, actor)
            assert env.snapshot() == before
            fork = TrainingEnvironment()
            fork.restore(before)
            action = {'type': 'choose_mechanic', 'card_ids': selected}
            env.step(action)
            fork.step(encode_action(action))
            assert env.snapshot() == fork.snapshot()
            assert env._state.players[actor].library[:round_count] == selected
    client, match = game
    identifier = retain(match, env)
    for actor in (seat, 3-seat):
        restart(identifier)
        hint = next(m for m in client.get(f'/matches/{identifier}/legal-moves?player_id={actor}').json()['moves']
                    if m['type'] == 'keep_hand')
        assert hint == {'type': 'keep_hand'}
        assert env.lookup_intent(hint, actor) == env.lookup({'type': 'keep_hand'}, actor)
        env.step({'type': 'keep_hand'})
        response = client.post(f'/matches/{identifier}/action', json={'player_id': actor, 'action': {'type': 'keep_hand'}})
        assert response.status_code == 200, response.text
    assert not restart(identifier).state.pregame_pending
    assert all(len(p.hand) == 5 for p in env._state.players.values())
