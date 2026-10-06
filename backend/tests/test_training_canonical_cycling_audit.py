"""Separate canonical card-semantics regression, not an intent-guard assertion."""
import pytest

from training.environment import decode_action
from tests.test_selected_mana_http import game, forbid_external_network
from tests.test_training_remaining_intent_audit import scenario, completed_state, execute_http


@pytest.mark.parametrize('seat', [1, 2])
def test_canonical_shark_typhoon_chosen_x_must_create_actual_token(game, seat):
    env, action, hint, _, _, selected = scenario(seat, 'cycling', variable_cycling=True)
    before = env.snapshot()
    accepted = env.lookup(action)
    assert env.lookup_intent({**hint, **action}) == accepted
    normalized = decode_action(accepted['id'])
    assert normalized['x_value'] == 2
    trusted = completed_state(env, normalized, 'cycling', selected)
    client, match = game
    http = execute_http(client, match, env, normalized, 'cycling', selected)
    assert env.snapshot() == before
    for state in (trusted, http):
        assert action['card_id'] in state.players[seat].graveyard
        assert state.draws_this_turn[seat] == 1
        assert sum(env._state.players[seat].mana_pool.values()) - sum(state.players[seat].mana_pool.values()) == 4
    # The actual canonical fixture says "When you cycle this card"; no invented payoff.
    for state in (trusted, http):
        sharks = [state.cards[cid] for cid in state.players[seat].battlefield
                  if state.cards[cid].is_token and state.cards[cid].name == 'Shark']
        assert len(sharks) == 1 and sharks[0].power == sharks[0].toughness == 2
