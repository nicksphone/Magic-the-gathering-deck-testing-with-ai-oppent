"""Canonical self-cycling clauses bind the cycled object and chosen cost X."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.events import _matches_cycle_trigger
from rules_engine.engine import RulesEngine
from tests.test_linked_damage_targets import raw_card
from tests.test_training_remaining_intent_audit import scenario
from training.environment import TrainingEnvironment
from tests.test_selected_mana_http import game, retain, restart, forbid_external_network


ROWS = {row['name']: row for row in json.loads(
    (Path(__file__).parent / 'fixtures/canonical_cycle_self/cards.json').read_text())}


def settle(env, accept_optional=True):
    for _ in range(16):
        pending = env._state.pending_trigger_order
        if pending:
            assert pending['phase'] == 'optional'
            env.step({'type': 'choose_optional_effect',
                      'stack_id': pending['current_stack_id'], 'accept': accept_optional})
        elif env._state.stack:
            env.step({'type': 'pass_priority'})
        else:
            return env._state
    pytest.fail('Cycling continuation did not resolve')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Shark Typhoon', 'Renewed Faith'])
def test_self_clause_matches_only_the_cycled_instance_and_controller(seat, name):
    env, _, _, _, _, _ = scenario(seat, 'cycling')
    first = raw_card(env._state, ROWS[name], seat, Zone.GRAVEYARD)
    second = raw_card(env._state, ROWS[name], seat, Zone.GRAVEYARD)
    before = env.snapshot()
    oracle = first.oracle_text.lower()
    assert _matches_cycle_trigger(env._state, first, oracle,
                                  {'card_id': first.id, 'controller': seat})
    assert not _matches_cycle_trigger(env._state, first, oracle,
                                      {'card_id': second.id, 'controller': seat})
    assert not _matches_cycle_trigger(env._state, first, oracle,
                                      {'card_id': first.id, 'controller': 3-seat})
    assert env.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('accept', [True, False])
def test_renewed_faith_cycling_resolves_its_own_optional_gain_not_the_spell(seat, accept):
    env, _, _, _, _, selected = scenario(seat, 'cycling')
    source = raw_card(env._state, ROWS['Renewed Faith'], seat, Zone.HAND)
    action = {'type': 'cycle_card', 'card_id': source.id, 'x_value': 0}
    before = env.snapshot()
    announced = checked_action(env._state, RulesEngine(), seat, action)
    assert [item.effect_key for item in announced.stack] == ['cycle_draw', 'gain_life']
    assert announced.stack[-1].payload['amount'] == 2
    assert source.id in announced.players[seat].graveyard
    assert env.snapshot() == before
    replay = TrainingEnvironment()
    replay.restore(before)
    replay.step(action)
    resolved = settle(replay, accept)
    assert resolved.players[seat].life == env._state.players[seat].life + (2 if accept else 0)
    assert resolved.draws_this_turn[seat] == 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('x_value', [0, 1, 3])
def test_canonical_shark_stats_use_chosen_cycling_x_after_snapshot_resume(seat, x_value):
    env, action, _, _, _, selected = scenario(seat, 'cycling', variable_cycling=True)
    action = {**action, 'x_value': x_value}
    before = env.snapshot()
    announced = checked_action(env._state, RulesEngine(), seat, action)
    assert [item.effect_key for item in announced.stack] == ['cycle_draw', 'create_shark_token']
    replay = deepcopy(env)
    replay._state = announced
    checkpoint = replay.snapshot()
    replay.restore(checkpoint)
    assert replay.snapshot() == checkpoint
    settle(replay)
    assert not replay._state.stack
    sharks = [replay._state.cards[cid] for cid in replay._state.players[seat].battlefield
              if replay._state.cards[cid].is_token and replay._state.cards[cid].name == 'Shark']
    assert len(sharks) == (1 if x_value else 0)
    if sharks:
        assert sharks[0].power == sharks[0].toughness == x_value
    assert sum(env._state.players[seat].mana_pool.values()) - sum(
        replay._state.players[seat].mana_pool.values()) == x_value + 2
    assert replay._state.draws_this_turn[seat] == 1
    assert env.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('accept', [True, False])
def test_renewed_faith_optional_cycling_choice_survives_http_restart(game, seat, accept):
    env, _, _, _, _, _ = scenario(seat, 'cycling')
    source = raw_card(env._state, ROWS['Renewed Faith'], seat, Zone.HAND)
    before = env.snapshot()
    client, match = game
    identifier = retain(match, env)
    action = {'type': 'cycle_card', 'card_id': source.id, 'x_value': 0}
    response = client.post(f'/matches/{identifier}/action',
                           json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    for _ in range(16):
        state = restart(identifier).state
        pending = state.pending_trigger_order
        if pending:
            assert pending['phase'] == 'optional'
            actor = seat
            action = {'type': 'choose_optional_effect',
                      'stack_id': pending['current_stack_id'], 'accept': accept}
        elif state.stack:
            actor = state.priority_player
            action = {'type': 'pass_priority'}
        else:
            break
        response = client.post(f'/matches/{identifier}/action',
                               json={'player_id': actor, 'action': action})
        assert response.status_code == 200, response.text
    else:
        pytest.fail('HTTP cycling continuation did not resolve')
    assert state.players[seat].life == env._state.players[seat].life + (2 if accept else 0)
    assert state.draws_this_turn[seat] == 1
    assert source.id in state.players[seat].graveyard
    assert env.snapshot() == before
