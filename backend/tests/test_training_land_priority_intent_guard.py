"""Public two-family guard: strict chosen fields and exact eligible presentation."""
from copy import deepcopy
from typing import get_args

import pytest

from api_contracts import LandAction, PassAction
from game_state.serializers import serialize_card_view
from rules_engine.action_validation import ActionRejected
from training.dataset import EpisodeAliases, canonical
from tests.test_training_land_priority_intent_audit import scenario
from tests.test_selected_mana_http import game, retain, restart, rejected, forbid_external_network


def observe_helper(monkeypatch):
    import ai.action_contract
    calls = []
    helper = ai.action_contract.complete_action
    def observed(intent):
        calls.append(deepcopy(intent))
        return helper(intent)
    monkeypatch.setattr(ai.action_contract, 'complete_action', observed)
    return calls


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['play_land', 'pass_priority'])
@pytest.mark.parametrize('field', ['unknown_choice', 'next_step', 'land_card_id'])
@pytest.mark.parametrize('is_null', [False, True])
def test_unknown_land_priority_fields_reject_before_helper(monkeypatch, seat, family, field, is_null):
    env, action, _, _ = scenario(family, seat)
    request = {**action, field: None if is_null else {'chosen': 'unsupported'}}
    before, original = env.snapshot(), deepcopy(request)
    calls = observe_helper(monkeypatch)
    with pytest.raises(ActionRejected):
        env.lookup_intent(request, seat)
    assert not calls
    assert env.snapshot() == before and request == original


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['play_land', 'pass_priority'])
@pytest.mark.parametrize('field', ['card_view', 'card_name', 'graveyard_permission_name'])
@pytest.mark.parametrize('form', ['null', 'changed', 'nested_choice'])
def test_display_metadata_is_exact_current_offer_not_choice_container(game, monkeypatch, seat, family, field, form):
    env, action, hint, _ = scenario(family, seat)
    request = deepcopy(hint)
    value = serialize_card_view(deepcopy(env._state), action['card_id']) if family == 'play_land' else {}
    if form == 'null':
        request[field] = None
    elif form == 'changed':
        request[field] = {**value, 'id': 'not-the-chosen-card'} if field == 'card_view' else 'unoffered metadata'
    else:
        request[field] = {**value, 'selected_face_index': None, 'player_id': 3-seat}
    before, original = env.snapshot(), deepcopy(request)
    client, match = game
    retain(match, env)
    assert rejected(client, match, request, seat).status_code == 422
    calls = observe_helper(monkeypatch)
    with pytest.raises(ActionRejected):
        env.lookup_intent(request, seat)
    assert not calls
    assert env.snapshot() == before and request == original


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('field,value', [
    ('card_id', None), ('card_id', ''), ('card_id', {'selected': 'card'}),
    ('from_exile', None), ('from_graveyard', None), ('from_exile', 1),
    ('selected_face_index', -1), ('selected_face_index', {'index': 0}),
    ('entry_choice', 'untapped'), ('graveyard_permission_key', ''),
])
def test_malformed_typed_land_fields_with_valid_display_reject_before_helper(monkeypatch, seat, field, value):
    env, action, hint, _ = scenario('play_land', seat)
    request = {**action, 'card_view': serialize_card_view(deepcopy(env._state), action['card_id']), field: value}
    before, original = env.snapshot(), deepcopy(request)
    calls = observe_helper(monkeypatch)
    with pytest.raises(ActionRejected):
        env.lookup_intent(request, seat)
    assert not calls
    assert env.snapshot() == before and request == original


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['play_land', 'pass_priority'])
def test_actual_http_whole_view_deliberate_choice_wrong_seat_stale_restore(game, monkeypatch, seat, family):
    env, action, _, lands = scenario(family, seat)
    before = env.snapshot()
    client, match = game
    identifier = retain(match, env)
    restart(identifier)
    hint = next(move for move in client.get(
        f'/matches/{identifier}/legal-moves?player_id={seat}').json()['moves']
        if move['type'] == family and (family == 'pass_priority' or move['card_id'] == lands[1]))
    original = deepcopy(hint)
    calls = observe_helper(monkeypatch)
    assert env.lookup_intent(hint, seat) == env.lookup(action, seat)
    assert len(calls) == 1 and calls[0] == hint
    if family == 'play_land':
        assert calls[0]['card_id'] == lands[1]
        assert 'from_exile' not in calls[0] and 'from_graveyard' not in calls[0]
        assert LandAction.model_validate(action).from_exile is False
        assert LandAction.model_validate(action).from_graveyard is False
    else:
        assert get_args(PassAction.model_fields['type'].annotation) == ('pass_priority',)
        assert set(PassAction.model_fields) == {'type'}
    with pytest.raises(ActionRejected):
        env.lookup_intent(hint, 3-seat)
    assert env.snapshot() == before and hint == original
    response = client.post(f'/matches/{identifier}/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    restored_match = restart(identifier)
    env.step(action)
    after = env.snapshot()
    with pytest.raises(ActionRejected):
        env.lookup_intent(hint, seat)
    assert env.snapshot() == after and hint == original
    if family == 'play_land':
        assert lands[1] in restored_match.state.players[seat].battlefield
        assert lands[0] in restored_match.state.players[seat].hand
    else:
        assert restored_match.state.priority_player == 3-seat


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['play_land', 'pass_priority'])
def test_private_hidden_order_does_not_change_qualified_hint_or_alias_input(seat, family):
    env, action, hint, _ = scenario(family, seat)
    from training.environment import TrainingEnvironment
    changed = TrainingEnvironment()
    changed.restore(env.snapshot())
    enemy = changed._state.players[3-seat]
    enemy.hand.reverse()
    enemy.library.reverse()
    if family == 'play_land':
        hint['card_view'] = serialize_card_view(deepcopy(env._state), action['card_id'])
    original, before = deepcopy(hint), env.snapshot()
    left, right = EpisodeAliases(), EpisodeAliases()
    assert canonical(left.observation(env.observe(seat))) == canonical(right.observation(changed.observe(seat)))
    assert env.lookup_intent(hint, seat) == changed.lookup_intent(hint, seat)
    assert env.snapshot() == before and hint == original
    assert left.actual_action(left.action(action, seat), seat) == action
