"""Two simple public families: requested aliases must not become other actions."""
from copy import deepcopy

import pytest
from pydantic import ValidationError

from api_contracts import LandAction, PassAction
from game_state.state import Step, Zone
from rules_engine.action_validation import ActionRejected
from training.environment import TrainingEnvironment, encode_action, decode_action
from training.dataset import EpisodeAliases, canonical
from tests.test_training_environment import env as canonical_environment, keep
from tests.test_selected_mana_http import game, retain, restart, rejected, forbid_external_network


MODELS = {'play_land': LandAction, 'pass_priority': PassAction}


def scenario(family, seat):
    env = canonical_environment()
    keep(env)
    state = env._state
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    lands = sorted((card for card in state.cards.values()
                    if card.owner == seat and card.name in {'Mountain', 'Island'}), key=lambda card: card.id)[:2]
    assert len(lands) == 2
    for card in lands:
        player = state.players[seat]
        for zone in ('hand', 'library', 'battlefield', 'graveyard', 'exile'):
            ids = getattr(player, zone)
            if card.id in ids:
                ids.remove(card.id)
        card.move_to_zone(Zone.HAND)
        player.hand.append(card.id)
    action = {'type': family}
    if family == 'play_land':
        action.update(card_id=lands[1].id, from_exile=False, from_graveyard=False)
    hint = next(move for move in env._rules.legal_moves(deepcopy(state), seat)
                if move['type'] == family and
                (family == 'pass_priority' or move['card_id'] == lands[1].id))
    assert set(hint) == ({'type', 'card_id'} if family == 'play_land' else {'type'})
    return env, action, hint, [card.id for card in lands]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['play_land', 'pass_priority'])
@pytest.mark.parametrize('field', ['player_id', 'phase', 'resolving_item', 'targets'])
@pytest.mark.parametrize('is_null', [False, True])
def test_unsupported_land_priority_request_rejects_before_helper(game, monkeypatch, seat, family, field, is_null):
    env, action, _, _ = scenario(family, seat)
    request = {**action, field: None if is_null else {'chosen': 'not-a-public-field'}}
    before, original = env.snapshot(), deepcopy(request)
    with pytest.raises(ValidationError):
        MODELS[family].model_validate(request)
    with pytest.raises(ActionRejected):
        env.lookup(request, seat)
    client, match = game
    retain(match, env)
    assert rejected(client, match, request, seat).status_code == 422
    import ai.action_contract
    calls = []
    helper = ai.action_contract.complete_action
    def observed(intent):
        calls.append(deepcopy(intent))
        return helper(intent)
    monkeypatch.setattr(ai.action_contract, 'complete_action', observed)
    try:
        with pytest.raises(ActionRejected):
            env.lookup_intent(request, seat)
        assert calls == []
    finally:
        assert env.snapshot() == before and request == original


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['play_land', 'pass_priority'])
def test_independent_land_priority_whole_view_execution_replay_http_restart(game, seat, family):
    env, action, hint, lands = scenario(family, seat)
    before, original = env.snapshot(), deepcopy(hint)
    assert env.lookup_intent(hint, seat) == env.lookup(action, seat)
    assert env.snapshot() == before and hint == original
    assert decode_action(encode_action(action)) == action
    client, match = game
    identifier = retain(match, env)
    restart(identifier)
    public_hint = next(move for move in client.get(
        f'/matches/{identifier}/legal-moves?player_id={seat}').json()['moves']
        if move['type'] == family and (family == 'pass_priority' or move['card_id'] == action['card_id']))
    assert env.lookup_intent(public_hint, seat) == env.lookup(action, seat)
    if family == 'play_land':
        assert set(public_hint) == {'type', 'card_id', 'card_view'}
        assert public_hint['card_view']['id'] == lands[1]
        assert rejected(client, match, public_hint, seat).status_code == 422
    else:
        assert public_hint == {'type': 'pass_priority'}
    restored = TrainingEnvironment()
    restored.restore(before)
    assert env.step(encode_action(action)) == restored.step(action)
    assert env.snapshot() == restored.snapshot()
    response = client.post(f'/matches/{identifier}/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    persisted = restart(identifier)
    if family == 'play_land':
        assert lands[1] in env._state.players[seat].battlefield
        assert lands[0] in env._state.players[seat].hand
        assert lands[1] in persisted.state.players[seat].battlefield
        assert lands[0] in persisted.state.players[seat].hand
        assert not env._state.cards[lands[1]].tapped
    else:
        assert env._state.priority_player == persisted.state.priority_player == 3-seat
        assert env._state.step == persisted.state.step == Step.PRECOMBAT_MAIN
        assert env._state.players[seat].hand == restored._state.players[seat].hand


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['play_land', 'pass_priority'])
def test_independent_land_priority_wrong_actor_and_land_timing_atomic(game, seat, family):
    env, action, _, _ = scenario(family, seat)
    before = env.snapshot()
    client, match = game
    retain(match, env)
    for lookup in (env.lookup, env.lookup_intent):
        with pytest.raises(ActionRejected):
            lookup(action, 3-seat)
    rejected(client, match, action, 3-seat)
    assert env.snapshot() == before
    if family == 'play_land':
        env._state.step = Step.COMBAT_DAMAGE
        before = env.snapshot()
        for lookup in (env.lookup, env.lookup_intent):
            with pytest.raises(ActionRejected):
                lookup(action, seat)
        retain(match, env)
        rejected(client, match, action, seat)
        assert env.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['play_land', 'pass_priority'])
def test_independent_land_priority_opponent_hidden_order_bytes_and_action_alias_roundtrip(seat, family):
    env, action, _, _ = scenario(family, seat)
    before = env.snapshot()
    changed = TrainingEnvironment()
    changed.restore(before)
    enemy = changed._state.players[3-seat]
    enemy.hand.reverse()
    enemy.library.reverse()
    aliases, other = EpisodeAliases(), EpisodeAliases()
    private = env.observe(seat)
    assert not set(env._state.players[3-seat].hand) & set(private['known_cards'])
    assert canonical(aliases.observation(private)) == canonical(other.observation(changed.observe(seat)))
    chosen = aliases.action(action, seat)
    assert aliases.actual_action(chosen, seat) == action
    assert env.lookup_intent(action, seat) == changed.lookup_intent(action, seat)
    assert env.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['play_land', 'pass_priority'])
def test_independent_land_source_explicit_and_pass_has_no_actor_parameter(seat, family):
    env, action, _, _ = scenario(family, seat)
    before = env.snapshot()
    if family == 'play_land':
        assert action['card_id']
        for value in (None, ''):
            with pytest.raises(ActionRejected):
                env.lookup_intent({'type': family, 'card_id': value}, seat)
        with pytest.raises(ActionRejected):
            env.lookup_intent({'type': family}, seat)
    else:
        assert set(MODELS[family].model_fields) == {'type'}
        assert env.lookup_intent(action, seat) == env.lookup(action, seat)
    assert env.snapshot() == before
