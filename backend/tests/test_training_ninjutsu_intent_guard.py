"""Ninjutsu chosen parameters are strict; display is only a current public view."""
from copy import deepcopy

import pytest

from game_state.serializers import serialize_card_view
from rules_engine.action_validation import ActionRejected
from training.environment import decode_action
from tests.test_training_ninjutsu_intent_audit import scenario
from tests.test_selected_mana_http import game, retain, restart, rejected, forbid_external_network


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('field', ['unknown_choice', 'payment_choices', 'player_id', 'return_card_ids'])
@pytest.mark.parametrize('is_null', [False, True])
def test_unsupported_ninjutsu_fields_reject_before_helper(monkeypatch, seat, field, is_null):
    env, action, _, _ = scenario(seat)
    request = {**action, field: None if is_null else {'selected': 'unsupported-choice'}}
    before, original = env.snapshot(), deepcopy(request)
    import ai.action_contract
    calls = []
    helper = ai.action_contract.complete_action
    def observed(intent):
        calls.append(deepcopy(intent))
        return helper(intent)
    monkeypatch.setattr(ai.action_contract, 'complete_action', observed)
    with pytest.raises(ActionRejected):
        env.lookup_intent(request, seat)
    assert calls == []
    assert env.snapshot() == before and request == original


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('field', ['card_id', 'return_card_id'])
@pytest.mark.parametrize('form', ['missing', 'null', 'object', 'empty'])
def test_invalid_chosen_ninjutsu_ids_reject_before_helper(monkeypatch, seat, field, form):
    env, action, hint, _ = scenario(seat)
    request = deepcopy(hint)
    if form == 'missing':
        del request[field]
    else:
        request[field] = {'null': None, 'object': {'chosen_id': action[field]}, 'empty': ''}[form]
    before, original = env.snapshot(), deepcopy(request)
    import ai.action_contract
    calls = []
    helper = ai.action_contract.complete_action
    def observed(intent):
        calls.append(deepcopy(intent))
        return helper(intent)
    monkeypatch.setattr(ai.action_contract, 'complete_action', observed)
    with pytest.raises(ActionRejected):
        env.lookup_intent(request, seat)
    assert calls == []
    assert env.snapshot() == before and request == original


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('field', ['card_name', 'mana_cost', 'card_view'])
@pytest.mark.parametrize('form', ['null', 'changed', 'nested_alias'])
def test_ninjutsu_display_is_exact_not_a_chosen_parameter(game, seat, field, form):
    env, action, hint, _ = scenario(seat)
    request = {**hint, 'card_view': serialize_card_view(deepcopy(env._state), action['card_id'])}
    if form == 'null':
        request[field] = None
    elif form == 'changed':
        request[field] = {'card_name': 'not-this-source', 'mana_cost': '{0}',
                          'card_view': {'id': 'not-this-source'}}[field]
    elif field == 'card_view':
        request[field]['return_card_id'] = None
    else:
        request[field] = {'return_card_id': action['return_card_id']}
    before, original = env.snapshot(), deepcopy(request)
    for lookup in (env.lookup, env.lookup_intent):
        with pytest.raises(ActionRejected):
            lookup(request, seat)
    client, match = game
    retain(match, env)
    assert rejected(client, match, request, seat).status_code == 422
    assert env.snapshot() == before and request == original


@pytest.mark.parametrize('seat', [1, 2])
def test_whole_http_ninjutsu_view_selected_second_and_missing_choice_no_inference(game, seat):
    env, action, _, info = scenario(seat)
    before = env.snapshot()
    assert action['return_card_id'] == info['attackers'][1]
    assert info['ninja'] not in env.observe(3-seat)['known_cards']
    client, match = game
    identifier = retain(match, env)
    restart(identifier)
    hint = next(move for move in client.get(
        f'/matches/{identifier}/legal-moves?player_id={seat}').json()['moves']
        if move['type'] == 'ninjutsu' and move['return_card_id'] == action['return_card_id'])
    original = deepcopy(hint)
    accepted = env.lookup_intent(hint, seat)
    assert accepted == env.lookup(action, seat)
    assert decode_action(accepted['id']) == action
    for field in ('card_id', 'return_card_id'):
        missing = {key: value for key, value in hint.items() if key != field}
        with pytest.raises(ActionRejected):
            env.lookup_intent(missing, seat)
    with pytest.raises(ActionRejected):
        env.lookup_intent(hint, 3-seat)
    assert env.snapshot() == before and hint == original
    assert rejected(client, match, hint, seat).status_code == 422
    response = client.post(f'/matches/{identifier}/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    current = restart(identifier)
    assert action['return_card_id'] in current.state.players[seat].hand
    assert info['attackers'][0] in current.state.attackers
    assert env.snapshot() == before
    env.step(action)
    after = env.snapshot()
    with pytest.raises(ActionRejected):
        env.lookup_intent(hint, seat)
    assert env.snapshot() == after
