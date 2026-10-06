"""Suspend/Keep guard controls on canonical frozen audit dependencies."""
from copy import deepcopy

import pytest

import main
from game_state.serializers import serialize_card_view
from game_state.state import Step, Zone
from rules_engine.action_validation import ActionRejected
from rules_engine.events import emit_event
from training.environment import TrainingEnvironment, decode_action
from tests.test_training_suspend_intent_audit import suspend_position, isolated_source, assert_private
from tests.test_training_keep_hand_intent_audit import opening
from tests.test_selected_mana_http import game, retain, restart, rejected, forbid_external_network
from tests.test_api_input_contracts import persist


def observed_helper(monkeypatch):
    import ai.action_contract
    helper = ai.action_contract.complete_action
    calls = []
    def observed(intent):
        calls.append(deepcopy(intent))
        return helper(intent)
    monkeypatch.setattr(ai.action_contract, 'complete_action', observed)
    return calls


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['suspend', 'keep_hand'])
@pytest.mark.parametrize('field', ['unknown_choice', 'player_id', 'resolving_item'])
@pytest.mark.parametrize('is_null', [False, True])
def test_unknown_fields_reject_before_helper(monkeypatch, seat, family, field, is_null):
    env, action = suspend_position(seat) if family == 'suspend' else opening(seat, True)
    request = {**action, field: None if is_null else {'chosen': 'unsupported'}}
    before, original = env.snapshot(), deepcopy(request)
    calls = observed_helper(monkeypatch)
    with pytest.raises(ActionRejected):
        env.lookup_intent(request, seat)
    assert calls == []
    assert env.snapshot() == before and request == original
    assert_private(env, seat)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('form', ['missing', 'null', 'object', 'empty'])
def test_suspend_card_choice_malformed_before_helper(monkeypatch, seat, form):
    env, action = suspend_position(seat)
    request = {**action, 'mana_cost': '{R}'}
    if form == 'missing':
        del request['card_id']
    else:
        request['card_id'] = {'null': None, 'object': {'id': action['card_id']}, 'empty': ''}[form]
    before, original = env.snapshot(), deepcopy(request)
    calls = observed_helper(monkeypatch)
    with pytest.raises(ActionRejected):
        env.lookup_intent(request, seat)
    assert calls == []
    assert env.snapshot() == before and request == original


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('form', ['null', 'object', 'nested', 'boolean'])
def test_keep_bottom_shape_malformed_before_helper(monkeypatch, seat, form):
    env, action = opening(seat, True)
    action['bottom_card_ids'] = {'null': None, 'object': {'id': 'choice'},
                               'nested': [{'id': 'choice'}], 'boolean': [True]}[form]
    before, original = env.snapshot(), deepcopy(action)
    calls = observed_helper(monkeypatch)
    with pytest.raises(ActionRejected):
        env.lookup_intent(action, seat)
    assert calls == []
    assert env.snapshot() == before and action == original


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('field', ['card_name', 'mana_cost', 'time_counters', 'card_view'])
@pytest.mark.parametrize('form', ['null', 'changed', 'nested'])
def test_suspend_display_exact_shape_before_helper_and_http_atomic(game, monkeypatch, seat, field, form):
    env, action = suspend_position(seat)
    request = next(m for m in env._rules.legal_moves(deepcopy(env._state), seat)
                   if m['type'] == 'suspend' and m['card_id'] == action['card_id'])
    request['card_view'] = serialize_card_view(deepcopy(env._state), action['card_id'])
    if form == 'null':
        request[field] = None
    elif form == 'changed':
        request[field] = {'card_name': 'other card', 'mana_cost': '{0}',
                          'time_counters': 99, 'card_view': {'id': 'other-card'}}[field]
    elif field == 'card_view':
        request[field]['requested_choice'] = None
    else:
        request[field] = {'requested_choice': None}
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
    assert_private(env, seat)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case', ['wrong-seat', 'stale'])
def test_suspend_actual_view_actor_or_incarnation_not_discarded(game, monkeypatch, seat, case):
    env, action = suspend_position(seat)
    hint = next(m for m in env._rules.legal_moves(deepcopy(env._state), seat)
                if m['type'] == 'suspend' and m['card_id'] == action['card_id'])
    if case == 'stale':
        env.step(action)
    before, original = env.snapshot(), deepcopy(hint)
    calls = observed_helper(monkeypatch)
    actor = 3-seat if case == 'wrong-seat' else seat
    with pytest.raises(ActionRejected):
        env.lookup_intent(hint, actor)
    assert calls == []
    client, match = game
    retain(match, env)
    rejected(client, match, action, actor)
    assert env.snapshot() == before and hint == original


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Rift Bolt', 'Ancestral Vision'])
@pytest.mark.parametrize('finish', ['cast', 'decline'])
def test_actual_suspend_upkeep_free_cast_or_decline_http_restart(game, seat, name, finish):
    env, action = suspend_position(seat, name)
    cid = action['card_id']
    before = env.snapshot()
    client, match = game
    identifier = retain(match, env)
    path = f'/matches/{identifier}'
    hint = next(m for m in client.get(path + f'/legal-moves?player_id={seat}').json()['moves']
                if m['type'] == 'suspend' and m['card_id'] == cid)
    checked = env.lookup_intent(hint, seat)
    assert checked == env.lookup(action, seat) and decode_action(checked['id']) == action
    assert env.snapshot() == before
    fork = TrainingEnvironment()
    fork.restore(before)
    env.step(checked['id'])
    fork.step(action)
    assert env.snapshot() == fork.snapshot()
    assert_private(env, seat)
    assert_private(env, 3-seat)

    def post(actor, chosen):
        response = client.post(path + '/action', json={'player_id': actor, 'action': chosen})
        assert response.status_code == 200, response.text
        return main.ACTIVE_MATCHES[identifier]

    state = post(seat, action).state
    assert state.cards[cid].zone == Zone.EXILE and not state.stack
    assert state.cards[cid].counters['time'] == hint['time_counters']
    assert state.spells_cast_this_turn[seat] == 0
    assert state.players[seat].mana_pool == env._state.players[seat].mana_pool
    restart(identifier)
    for count in range(hint['time_counters'], 0, -1):
        controller = main.ACTIVE_MATCHES[identifier]
        controller.state.step = Step.UPKEEP
        emit_event(controller.state, 'begin_step', {'step': 'upkeep', 'active_player': seat})
        assert controller.state.stack[-1].effect_key == 'suspend_upkeep'
        persist(controller)
        controller = restart(identifier)
        for _ in range(2):
            controller = post(controller.state.priority_player, {'type': 'pass_priority'})
        assert controller.state.cards[cid].counters.get('time', 0) == count-1
        if count == 1:
            assert controller.state.stack[-1].effect_key == 'suspend_cast_trigger'
        else:
            assert not controller.state.stack
    for _ in range(2):
        controller = post(controller.state.priority_player, {'type': 'pass_priority'})
    controller = restart(identifier)
    assert controller.state.pending_mechanic_choice['kind'] == 'suspend_cast'
    rejected(client, controller, {'type': 'choose_mechanic', 'card_ids': ['decline']}, 3-seat)
    if finish == 'decline':
        controller = post(seat, {'type': 'choose_mechanic', 'card_ids': ['decline']})
        assert controller.state.cards[cid].zone == Zone.EXILE and not controller.state.stack
    else:
        target = 3-seat if name == 'Rift Bolt' else seat
        chosen = {'type': 'cast_spell', 'card_id': cid, 'from_exile': True,
                  'targets': {'target_player': target}}
        rejected(client, controller, {'type': 'cast_spell', 'card_id': cid, 'from_exile': True}, seat)
        old_mana = deepcopy(controller.state.players[seat].mana_pool)
        old_hand = len(controller.state.players[seat].hand)
        old_life = controller.state.players[target].life
        controller = post(seat, chosen)
        assert controller.state.cards[cid].zone == Zone.STACK
        assert controller.state.players[seat].mana_pool == old_mana
        controller = restart(identifier)
        for _ in range(2):
            controller = post(controller.state.priority_player, {'type': 'pass_priority'})
        assert controller.state.cards[cid].zone == Zone.GRAVEYARD
        if name == 'Rift Bolt':
            assert controller.state.players[target].life == old_life-3
        else:
            assert len(controller.state.players[seat].hand) == old_hand+3
    assert not restart(identifier).state.pending_mechanic_choice
