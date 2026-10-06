"""Strict foretell prefilter; canonical hints never supply authoritative choices."""
from copy import deepcopy

import pytest

from game_state.serializers import serialize_card_view
from rules_engine.action_validation import ActionRejected
from tests.test_training_foretell_intent_audit import scenario
from tests.test_selected_mana_http import game, retain, restart, rejected, forbid_external_network


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('field', ['unknown_choice', 'payment_choices', 'player_id', 'targets'])
@pytest.mark.parametrize('is_null', [False, True])
def test_unsupported_foretell_fields_reject_before_helper(monkeypatch, seat, field, is_null):
    env, _, action, _ = scenario(seat)
    request = {**action, field: None if is_null else {'selected': 'not-in-contract'}}
    before, original = env.snapshot(), deepcopy(request)
    import ai.action_contract
    calls = []
    original_helper = ai.action_contract.complete_action
    def observed(intent):
        calls.append(deepcopy(intent))
        return original_helper(intent)
    monkeypatch.setattr(ai.action_contract, 'complete_action', observed)
    with pytest.raises(ActionRejected):
        env.lookup_intent(request, seat)
    assert calls == []
    assert env.snapshot() == before and request == original


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('form', ['missing', 'null', 'object', 'empty'])
def test_invalid_authoritative_card_schema_rejects_before_helper(monkeypatch, seat, form):
    env, _, action, _ = scenario(seat)
    request = deepcopy(action)
    if form == 'missing':
        del request['card_id']
    else:
        request['card_id'] = {'null': None, 'object': {'chosen_id': action['card_id']}, 'empty': ''}[form]
    before = env.snapshot()
    import ai.action_contract
    calls = []
    original_helper = ai.action_contract.complete_action
    def observed(intent):
        calls.append(deepcopy(intent))
        return original_helper(intent)
    monkeypatch.setattr(ai.action_contract, 'complete_action', observed)
    with pytest.raises(ActionRejected):
        env.lookup_intent(request, seat)
    assert calls == [] and env.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('field', ['card_name', 'mana_cost', 'fixed_costs', 'granted_reductions', 'card_view'])
@pytest.mark.parametrize('form', ['null', 'changed', 'nested_alias'])
def test_only_exact_current_foretell_display_is_allowed(game, seat, field, form):
    env, cid, action, hint = scenario(seat)
    full = {**hint, 'card_view': serialize_card_view(deepcopy(env._state), cid)}
    request = deepcopy(full)
    if form == 'null':
        request[field] = None
    elif form == 'nested_alias':
        if field == 'card_view':
            request[field]['chosen_face'] = None
        else:
            request[field] = {'selected': action['card_id']}
    else:
        request[field] = {'card_name': 'not-this-card', 'mana_cost': '{0}',
                          'fixed_costs': ['{0}'], 'granted_reductions': [99],
                          'card_view': {'id': 'not-this-card'}}[field]
    before, original = env.snapshot(), deepcopy(request)
    for lookup in (env.lookup, env.lookup_intent):
        with pytest.raises(ActionRejected):
            lookup(request, seat)
    client, match = game
    retain(match, env)
    assert rejected(client, match, request, seat).status_code == 422
    assert env.snapshot() == before and request == original


@pytest.mark.parametrize('seat', [1, 2])
def test_whole_http_view_private_copy_and_missing_card_are_not_inferred(game, seat):
    env, cid, action, _ = scenario(seat)
    client, match = game
    identifier = retain(match, env)
    restart(identifier)
    hint = next(move for move in client.get(
        f'/matches/{identifier}/legal-moves?player_id={seat}').json()['moves']
        if move['type'] == 'foretell' and move['card_id'] == cid)
    before, original = env.snapshot(), deepcopy(hint)
    assert env.lookup_intent(hint, seat) == env.lookup(action, seat)
    assert env.snapshot() == before and hint == original
    incomplete = {key: value for key, value in hint.items() if key != 'card_id'}
    with pytest.raises(ActionRejected):
        env.lookup_intent(incomplete, seat)
    with pytest.raises(ActionRejected):
        env.lookup_intent(hint, 3-seat)
    assert env.snapshot() == before
    # Display metadata is never accepted by raw HTTP, even when genuine.
    assert rejected(client, match, hint, seat).status_code == 422
    response = client.post(f'/matches/{identifier}/action',
                           json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    restarted = restart(identifier)
    assert restarted.state.cards[cid].exile_face_down
    env.step(action)
    assert cid not in env.observe(3-seat)['known_cards']
    after = env.snapshot()
    with pytest.raises(ActionRejected):
        env.lookup_intent(hint, seat)
    assert env.snapshot() == after
