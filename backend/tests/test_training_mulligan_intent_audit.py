"""Mulligan-only audit; rejection witnesses never accept unsupported requests."""
from copy import deepcopy

import pytest
from pydantic import ValidationError

import main
from api_contracts import MulliganAction
from training.environment import TrainingEnvironment, encode_action
from rules_engine.action_validation import ActionRejected
from tests.test_training_keep_hand_intent_audit import opening
from tests.test_training_suspend_intent_audit import isolated_source, assert_private
from tests.test_selected_mana_http import game, retain, restart, rejected, forbid_external_network


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('field', ['bottom_card_ids', 'player_id', 'from_library',
                                   'resolving_item', 'unknown_choice'])
@pytest.mark.parametrize('is_null', [False, True])
def test_mulligan_unsupported_requested_fields_must_reject(game, seat, field, is_null):
    env, _ = opening(seat)
    request = {'type': 'mulligan', field: None if is_null else {'requested': 'not-a-legal-choice'}}
    before, original = env.snapshot(), deepcopy(request)
    with pytest.raises(ValidationError):
        MulliganAction.model_validate(request)
    with pytest.raises(ActionRejected):
        env.lookup(request, seat)
    client, match = game
    retain(match, env)
    assert rejected(client, match, request, seat).status_code == 422
    assert_private(env, seat)
    assert_private(env, 3-seat)
    try:
        with pytest.raises(ActionRejected):
            env.lookup_intent(request, seat)
    finally:
        assert env.snapshot() == before and request == original


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('value', [None, 99, {'requested_count': 0}, False])
def test_mulligan_count_display_not_a_request_or_coerced_choice(game, seat, value):
    env, _ = opening(seat)
    hint = next(m for m in env._rules.legal_moves(deepcopy(env._state), seat) if m['type'] == 'mulligan')
    assert hint == {'type': 'mulligan', 'current_mulligans': 0}
    request = {**hint, 'current_mulligans': value}
    before, original = env.snapshot(), deepcopy(request)
    with pytest.raises(ValidationError):
        MulliganAction.model_validate(request)
    with pytest.raises(ActionRejected):
        env.lookup(request, seat)
    client, match = game
    retain(match, env)
    assert rejected(client, match, request, seat).status_code == 422
    try:
        with pytest.raises(ActionRejected):
            env.lookup_intent(request, seat)
    finally:
        assert env.snapshot() == before and request == original


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('whole_view', [False, True])
@pytest.mark.parametrize('peer_decision', ['keep_hand', 'mulligan'])
def test_independent_real_round_wholeview_rng_private_bottoms_and_http_restart(game, seat, whole_view, peer_decision):
    env, _ = opening(seat)
    action = {'type': 'mulligan'}
    before = env.snapshot()
    hands = {pid: list(player.hand) for pid, player in env._state.players.items()}
    hint = next(m for m in env._rules.legal_moves(deepcopy(env._state), seat) if m['type'] == 'mulligan')
    assert hint == {'type': 'mulligan', 'current_mulligans': 0}
    assert env.lookup_intent(hint if whole_view else action, seat) == env.lookup(action, seat)
    assert env.snapshot() == before
    fork = TrainingEnvironment()
    fork.restore(before)
    env.step(encode_action(action))
    fork.step(action)
    assert env.snapshot() == fork.snapshot()
    assert env._state.mulligan_declarations == {seat: 'mulligan'}
    assert env._state.mulligan_count == {1: 0, 2: 0}
    assert all(player.hand == hands[pid] for pid, player in env._state.players.items())
    assert env.acting_seat == 3-seat
    assert_private(env, seat)
    assert_private(env, 3-seat)
    env.step({'type': peer_decision})
    fork.step({'type': peer_decision})
    assert env.snapshot() == fork.snapshot()
    assert env._state.mulligan_count[seat] == 1
    assert env._state.mulligan_count[3-seat] == (1 if peer_decision == 'mulligan' else 0)
    assert len(env._state.players[seat].hand) == 7
    if peer_decision == 'keep_hand':
        assert env._state.players[3-seat].hand == hands[3-seat]

    original = TrainingEnvironment()
    original.restore(before)
    client, match = game
    identifier = retain(match, original)
    path = f'/matches/{identifier}'
    restart(identifier)
    view = next(m for m in client.get(path + f'/legal-moves?player_id={seat}').json()['moves'] if m['type'] == 'mulligan')
    assert view == hint
    assert original.lookup_intent(view, seat) == original.lookup(action, seat)
    rejected(client, match, action, 3-seat)

    def post(actor, chosen):
        response = client.post(path + '/action', json={'player_id': actor, 'action': chosen})
        assert response.status_code == 200, response.text
        return main.ACTIVE_MATCHES[identifier]

    controller = post(seat, action)
    controller = restart(identifier)
    assert controller.state.mulligan_declarations == {seat: 'mulligan'}
    rejected(client, controller, action, seat)
    controller = post(3-seat, {'type': peer_decision})
    controller = restart(identifier)
    assert controller.state.players[seat].hand == env._state.players[seat].hand
    while env._state.pending_mechanic_choice:
        actor = env.acting_seat
        assert env._state.pending_mechanic_choice['kind'] == 'mulligan_bottom'
        assert_private(env, actor)
        assert_private(env, 3-actor)
        # Choose a non-first card explicitly; no consumer or engine guess.
        selected = [env._state.players[actor].hand[2]]
        chosen = {'type': 'choose_mechanic', 'card_ids': selected}
        pending = env.snapshot()
        restored = TrainingEnvironment()
        restored.restore(pending)
        rejected(client, controller, {'type': 'keep_hand', 'bottom_card_ids': selected}, actor)
        env.step(chosen)
        restored.step(encode_action(chosen))
        assert env.snapshot() == restored.snapshot()
        controller = post(actor, chosen)
        controller = restart(identifier)
        assert controller.state.players[actor].library[:1] == selected
    while env._state.pregame_pending:
        actor = env.acting_seat
        env.step({'type': 'keep_hand'})
        controller = post(actor, {'type': 'keep_hand'})
    assert not restart(identifier).state.pregame_pending
    assert len(controller.state.players[seat].hand) == 6
    assert len(controller.state.players[3-seat].hand) == (6 if peer_decision == 'mulligan' else 7)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('invalid', ['wrong-seat', 'repeat', 'pending-bottom', 'after-keep', 'at-seven'])
def test_independent_unavailable_mulligan_atomic(game, seat, invalid):
    env, _ = opening(seat)
    actor = seat
    if invalid == 'wrong-seat':
        actor = 3-seat
    elif invalid == 'repeat':
        env.step({'type': 'mulligan'})
    elif invalid == 'pending-bottom':
        env.step({'type': 'mulligan'})
        env.step({'type': 'mulligan'})
    elif invalid == 'after-keep':
        env.step({'type': 'keep_hand'})
        env.step({'type': 'keep_hand'})
    elif invalid == 'at-seven':
        # Explicit supported boundary for the seven-mulligan declaration limit.
        env._state.mulligan_count[seat] = env._state.mulligan_bottomed[seat] = 7
    before = env.snapshot()
    action = {'type': 'mulligan'}
    for method in (env.lookup, env.lookup_intent):
        with pytest.raises(ActionRejected):
            method(action, actor)
        assert env.snapshot() == before
    client, match = game
    retain(match, env)
    rejected(client, match, action, actor)
    assert_private(env, seat)
    assert_private(env, 3-seat)
