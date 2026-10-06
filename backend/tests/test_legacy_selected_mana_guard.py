"""Legacy public selection guards; no change to internal None planner choices."""
from copy import deepcopy

import pytest

from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action, validate_action
from rules_engine.mana_abilities import activate_mana_ability, mana_ability_views
from tests.test_training_selected_mana import selected_position, filter_position, mana_position
from tests.test_training_mana_choice_coverage import card
from tests.test_base_vector_boundaries import add as vector_card
from tests.test_mana_executor_choices import add as executor_card
from tests.test_selected_mana_http import game, retain, restart, rejected, forbid_external_network


def legacy_position(seat, case):
    if case in ('tower', 'prospector'):
        env, _, chosen = selected_position(seat, 'Phyrexian Tower' if case == 'tower' else 'Skirk Prospector')
        cid, color = chosen['card_id'], chosen['color']
    elif case == 'hybrid':
        env, cid = filter_position(seat, 'graven-cairns', 'R')
        color = 'B'
    else:
        env = mana_position(seat)
        env._state.players[seat].mana_pool = {}
        if case == 'discard':
            cid = executor_card(env._state, 'Bog Witch', seat).id
            executor_card(env._state, 'Forest', seat, Zone.HAND)
            env._state.players[seat].mana_pool = {'B': 1}
            color = 'B'
        else:
            cid = vector_card(env._state, 'Simic Growth Chamber' if case == 'mixed_sphere' else 'Gyre Engineer', seat).id
            color = 'G'
            if case == 'mixed_sphere':
                vector_card(env._state, 'Damping Sphere', seat)
                color = 'C'
    return env, {'type': 'tap_nonland_for_mana', 'card_id': cid, 'color': color}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case', ['tower', 'prospector', 'discard', 'hybrid', 'mixed', 'mixed_sphere'])
def test_real_canonical_legacy_resource_and_vector_rejection_core_http(game, seat, case):
    env, action = legacy_position(seat, case)
    before = env.snapshot()
    for boundary in (lambda value: validate_action(deepcopy(env._state), env._rules, seat, value),
                     lambda value: checked_action(env._state, env._rules, seat, value),
                     env.lookup, env.lookup_intent, env.step):
        with pytest.raises(ActionRejected):
            boundary(action)
        assert env.snapshot() == before
    client, match = game
    identifier = retain(match, env)
    rejected(client, match, action, seat)
    assert serialize_match_snapshot(restart(identifier).state) == serialize_match_snapshot(env._state) | {'id': identifier}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('control', ['ambiguous_index', 'unsupported_x'])
def test_negative_view_controls_no_index_or_x_inference(game, monkeypatch, seat, control):
    # Controlled view metadata, not a fabricated X-producing canonical card.
    env = mana_position(seat)
    cid = card(env, 'Sol Ring', seat)
    views = mana_ability_views(env._state, env._state.cards[cid])
    if control == 'ambiguous_index':
        views.append({**deepcopy(views[0]), 'ability_index': 99})
    else:
        views[0]['cost_text'] = '{X}, {T}'
    monkeypatch.setattr('rules_engine.mana_abilities.mana_ability_views',
                        lambda state, source: deepcopy(views) if source.id == cid else [])
    action = {'type': 'tap_nonland_for_mana', 'card_id': cid, 'color': 'C'}
    before = env.snapshot()
    with pytest.raises(ActionRejected):
        checked_action(env._state, env._rules, seat, action)
    assert env.snapshot() == before
    client, match = game
    retain(match, env)
    rejected(client, match, action, seat)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,color,amount', [('Sol Ring', 'C', 2), ('Forest', 'G', 1), ('Basal Thrull', 'B', 2)])
def test_simple_legacy_core_http_remains_compatible(game, seat, name, color, amount):
    env = mana_position(seat)
    cid = card(env, name, seat)
    env._state.players[seat].mana_pool = {}
    action = {'type': 'tap_nonland_for_mana', 'card_id': cid, 'color': color}
    before = env.snapshot()
    result = checked_action(env._state, env._rules, seat, action)
    assert result.players[seat].mana_pool[color] == amount
    if name == 'Basal Thrull':
        assert cid in result.players[seat].graveyard
    assert env.snapshot() == before
    client, match = game
    identifier = retain(match, env)
    response = client.post(f'/matches/{identifier}/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    restored = restart(identifier).state
    assert restored.players[seat].mana_pool[color] == amount
    if name == 'Basal Thrull':
        assert cid in restored.players[seat].graveyard


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('sphere', [False, True])
def test_explicit_mixed_base_vector_still_supported_core_http(game, seat, sphere):
    env, legacy = legacy_position(seat, 'mixed_sphere' if sphere else 'mixed')
    view = next(view for view in env._rules.legal_moves(deepcopy(env._state), seat)
                if view['type'] == 'activate_mana_ability' and view['card_id'] == legacy['card_id'])
    action = {'type': 'activate_mana_ability', 'card_id': legacy['card_id'],
              'ability_index': view['ability_index'], 'color': 'G', 'output_bundle': {'G': 1, 'U': 1}}
    before = env.snapshot()
    assert env.lookup_intent({**view, **action}) == env.lookup(action)
    expected = {'C': 1} if sphere else {'G': 1, 'U': 1}
    result = checked_action(env._state, env._rules, seat, action)
    assert {color: amount for color, amount in result.players[seat].mana_pool.items() if amount} == expected
    assert env.snapshot() == before
    client, match = game
    identifier = retain(match, env)
    response = client.post(f'/matches/{identifier}/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    restored = restart(identifier).state
    assert {color: amount for color, amount in restored.players[seat].mana_pool.items() if amount} == expected


@pytest.mark.parametrize('seat', [1, 2])
def test_internal_none_resource_and_hybrid_defaults_unchanged(seat):
    env, choices, action = selected_position(seat)
    assert activate_mana_ability(env._state, seat, action['card_id'], action['ability_index'], 'B',
                                 payment_choices=None, hybrid_choices=None)
    assert sum(cid in env._state.players[seat].graveyard for cid in choices) == 1
    env, cid = filter_position(seat, 'graven-cairns', 'R')
    assert activate_mana_ability(env._state, seat, cid, 1, 'B', payment_choices=None,
                                 hybrid_choices=None, output_bundle={'B': 2})
    assert env._state.players[seat].mana_pool['B'] == 2
