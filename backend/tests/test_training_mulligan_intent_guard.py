"""Mulligan display is current actor context, never chosen count or bottom cards."""
from copy import deepcopy

import pytest

import main
from rules_engine.action_validation import ActionRejected
from training.environment import TrainingEnvironment, encode_action, decode_action
from tests.test_training_keep_hand_intent_audit import opening
from tests.test_training_suspend_intent_audit import isolated_source, assert_private
from tests.test_selected_mana_http import game, retain, restart, rejected, forbid_external_network
from tests.test_training_suspend_keep_intent_guard import observed_helper


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('field', ['unknown_choice', 'keep_hand', 'bottom_card_ids',
                                   'player_id', 'resolving_item', 'phase'])
@pytest.mark.parametrize('is_null', [False, True])
def test_mulligan_unknown_choices_reject_before_helper(monkeypatch, seat, field, is_null):
    env, _ = opening(seat)
    request = {'type': 'mulligan', field: None if is_null else {'selected': 'unsupported'}}
    before, original = env.snapshot(), deepcopy(request)
    calls = observed_helper(monkeypatch)
    with pytest.raises(ActionRejected):
        env.lookup_intent(request, seat)
    assert calls == []
    assert env.snapshot() == before and request == original
    assert_private(env, seat)
    assert_private(env, 3-seat)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('value', [None, False, True, -1, '0', 0.0, [], {}])
def test_mulligan_counter_strict_shape_before_helper_raw_http_atomic(game, monkeypatch, seat, value):
    env, _ = opening(seat)
    request = {'type': 'mulligan', 'current_mulligans': value}
    before, original = env.snapshot(), deepcopy(request)
    calls = observed_helper(monkeypatch)
    with pytest.raises(ActionRejected):
        env.lookup_intent(request, seat)
    assert calls == []
    with pytest.raises(ActionRejected):
        env.lookup(request, seat)
    client, match = game
    retain(match, env)
    assert rejected(client, match, request, seat).status_code == 422
    assert env.snapshot() == before and request == original


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('context', ['wrong-seat', 'stale-declaration', 'pending-bottom', 'stale-count'])
def test_mulligan_context_cannot_be_dropped_before_helper(game, monkeypatch, seat, context):
    env, _ = opening(seat)
    request = next(m for m in env._rules.legal_moves(deepcopy(env._state), seat) if m['type'] == 'mulligan')
    actor = seat
    if context == 'wrong-seat':
        actor = 3-seat
    elif context == 'stale-declaration':
        env.step({'type': 'mulligan'})
    elif context in ('pending-bottom', 'stale-count'):
        env.step({'type': 'mulligan'})
        env.step({'type': 'mulligan'})
        if context == 'stale-count':
            for pid in (seat, 3-seat):
                env.step({'type': 'choose_mechanic', 'card_ids': [env._state.players[pid].hand[2]]})
            assert env._state.mulligan_count[seat] == 1
    before, original = env.snapshot(), deepcopy(request)
    calls = observed_helper(monkeypatch)
    with pytest.raises(ActionRejected):
        env.lookup_intent(request, actor)
    assert calls == []
    client, match = game
    retain(match, env)
    assert rejected(client, match, request, actor).status_code == 422
    assert env.snapshot() == before and request == original
    assert_private(env, seat)
    assert_private(env, 3-seat)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('default_actor', [False, True])
def test_actual_multiple_rounds_current_wholehints_defaultactor_orderedbottom_private_http_restart(game, seat, default_actor):
    env, _ = opening(seat)
    client, match = game
    identifier = retain(match, env)
    path = f'/matches/{identifier}'
    canonical = {'type': 'mulligan'}

    def post(actor, action):
        response = client.post(path + '/action', json={'player_id': actor, 'action': action})
        assert response.status_code == 200, response.text
        return restart(identifier)

    for count in (1, 2):
        for actor in (seat, 3-seat):
            assert env.acting_seat == actor
            view = next(m for m in client.get(path + f'/legal-moves?player_id={actor}').json()['moves'] if m['type'] == 'mulligan')
            assert view == {'type': 'mulligan', 'current_mulligans': count-1}
            before, original = env.snapshot(), deepcopy(view)
            selected = env.lookup_intent(view) if default_actor else env.lookup_intent(view, actor)
            assert selected == env.lookup(canonical, actor)
            assert decode_action(selected['id']) == canonical
            assert env.snapshot() == before and view == original
            rejected(client, main.ACTIVE_MATCHES[identifier], view, actor)
            fork = TrainingEnvironment()
            fork.restore(before)
            env.step(selected['id'])
            fork.step(canonical, actor)
            assert env.snapshot() == fork.snapshot()
            controller = post(actor, canonical)
            assert controller.state.players[actor].hand == env._state.players[actor].hand
            assert_private(env, actor)
            assert_private(env, 3-actor)
        for actor in (seat, 3-seat):
            assert env.acting_seat == actor
            assert env._state.pending_mechanic_choice['kind'] == 'mulligan_bottom'
            assert env._state.mulligan_count[actor] == count
            assert_private(env, actor)
            assert_private(env, 3-actor)
            selected = list(reversed(env._state.players[actor].hand[1:1+count]))
            chosen = {'type': 'choose_mechanic', 'card_ids': selected}
            before = env.snapshot()
            with pytest.raises(ActionRejected):
                env.lookup_intent({'type': 'mulligan', 'current_mulligans': count}, actor)
            assert env.snapshot() == before
            fork = TrainingEnvironment()
            fork.restore(before)
            env.step(encode_action(chosen))
            fork.step(chosen, actor)
            assert env.snapshot() == fork.snapshot()
            controller = post(actor, chosen)
            assert controller.state.players[actor].library[:count] == selected
            assert env._state.players[actor].library[:count] == selected
    view = next(m for m in client.get(path + f'/legal-moves?player_id={seat}').json()['moves'] if m['type'] == 'mulligan')
    assert view == {'type': 'mulligan', 'current_mulligans': 2}
    before = env.snapshot()
    assert env.lookup_intent(view) == env.lookup(canonical, seat)
    assert env.snapshot() == before
    for actor in (seat, 3-seat):
        env.step({'type': 'keep_hand'})
        controller = post(actor, {'type': 'keep_hand'})
    assert not controller.state.pregame_pending
    assert all(len(player.hand) == 5 for player in controller.state.players.values())
    assert_private(env, seat)
    assert_private(env, 3-seat)
