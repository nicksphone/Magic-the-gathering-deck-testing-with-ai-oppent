"""Sibling tap-only route audit; strict intent regressions deliberately unxfail."""
from copy import deepcopy

import pytest

from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.costs import ActivatedCost, parse_activated_cost
from rules_engine.mana_abilities import mana_ability_specs, mana_ability_views
from tests.test_training_selected_mana import mana_position, selected_position, filter_position
from tests.test_training_mana_choice_coverage import card
from tests.test_base_vector_boundaries import add as vector_card
from tests.test_selected_mana_http import game, retain, restart, rejected, forbid_external_network


def land_action(env, cid, route, color):
    action = ({'type': route, 'card_id': cid} if route == 'tap_land_for_mana' else
              {'type': route, 'land_name': env._state.cards[cid].name, 'count': 1})
    if color is not None:
        action['color'] = color
    return action


def paid_position(seat, case):
    if case == 'tower':
        env, _, selected = selected_position(seat)
        cid, color = selected['card_id'], 'B'
    elif case in ('cairns', 'grove'):
        env, cid = filter_position(seat, 'graven-cairns' if case == 'cairns' else 'flooded-grove',
                                   'R' if case == 'cairns' else 'U')
        color = 'B' if case == 'cairns' else 'G'
    else:
        env = mana_position(seat)
        env._state.players[seat].mana_pool = {'C': 2}
        cid = card(env, 'Cabal Coffers', seat)
        for _ in range(2):
            card(env, 'Swamp', seat)
        color = None if case.endswith('omitted') else 'B'
        if case.startswith('coffers_sphere'):
            vector_card(env._state, 'Damping Sphere', seat)
            if color is not None:
                color = 'C'
    views = mana_ability_views(env._state, env._state.cards[cid])
    assert any(parse_activated_cost(view['cost_text']) != ActivatedCost(tap_source=True)
               and (color is None or color in view['outputs']) for view in views)
    return env, cid, color


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('route', ['tap_land_for_mana', 'tap_lands_bulk'])
@pytest.mark.parametrize('case', ['tower', 'coffers', 'coffers_omitted', 'coffers_sphere',
                                 'coffers_sphere_omitted', 'cairns', 'grove'])
def test_sibling_routes_cannot_activate_paid_or_other_resource_abilities(game, seat, route, case):
    env, cid, color = paid_position(seat, case)
    action = land_action(env, cid, route, color)
    before = env.snapshot()
    for boundary in (lambda value: checked_action(env._state, env._rules, seat, value),
                     env.lookup, env.lookup_intent, env.step):
        with pytest.raises(ActionRejected):
            boundary(action)
        assert env.snapshot() == before
    client, match = game
    identifier = retain(match, env)
    rejected(client, match, action, seat)
    restart(identifier)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('route', ['tap_land_for_mana', 'tap_lands_bulk'])
@pytest.mark.parametrize('explicit', [False, True])
def test_simple_basic_land_default_and_explicit_colors_remain_legal(game, seat, route, explicit):
    env = mana_position(seat)
    env._state.players[seat].mana_pool = {}
    cid = card(env, 'Forest', seat)
    action = land_action(env, cid, route, 'G' if explicit else None)
    before = env.snapshot()
    if explicit:
        assert env.lookup_intent(action) == env.lookup(action)
    else:
        # The training consumer intentionally requires an announced color;
        # raw legacy HTTP retains its existing basic-land convenience default.
        for boundary in (env.lookup, env.lookup_intent):
            with pytest.raises(ActionRejected, match='color'):
                boundary(action)
    result = checked_action(env._state, env._rules, seat, action)
    assert result.players[seat].mana_pool['G'] == 1 and result.cards[cid].tapped
    assert env.snapshot() == before
    client, match = game
    identifier = retain(match, env)
    response = client.post(f'/matches/{identifier}/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    assert restart(identifier).state.players[seat].mana_pool['G'] == 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('route', ['tap_land_for_mana', 'tap_lands_bulk'])
@pytest.mark.parametrize('name,branch', [('graven-cairns', 'R'), ('flooded-grove', 'U')])
def test_filter_sphere_same_final_color_uses_only_free_tap_spec(game, monkeypatch, seat, route, name, branch):
    env, cid = filter_position(seat, name, branch)
    vector_card(env._state, 'Damping Sphere', seat)
    action = land_action(env, cid, route, 'C')
    # Both free-C and paid mixed production can end in C; pin actual executor index.
    specs = mana_ability_specs(env._state.cards[cid], env._state)
    free_index = next(spec[0] for spec in specs if parse_activated_cost(spec[1]) == ActivatedCost(tap_source=True))
    views = mana_ability_views(env._state, env._state.cards[cid])
    assert sum('C' in view['outputs'] for view in views) >= 2
    from rules_engine import mana_abilities
    original = mana_abilities.activate_mana_ability
    indices = []
    def traced(state, actor, source, index, color, **kwargs):
        if source == cid:
            indices.append(index)
        return original(state, actor, source, index, color, **kwargs)
    monkeypatch.setattr(mana_abilities, 'activate_mana_ability', traced)
    before = env.snapshot()
    result = checked_action(env._state, env._rules, seat, action)
    assert indices == [free_index]
    assert result.players[seat].mana_pool[branch] == 1 and result.players[seat].mana_pool['C'] == 1
    assert env.snapshot() == before
    indices.clear()
    client, match = game
    identifier = retain(match, env)
    response = client.post(f'/matches/{identifier}/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    assert indices == [free_index]
    restored = restart(identifier).state
    assert restored.players[seat].mana_pool[branch] == 1 and restored.players[seat].mana_pool['C'] == 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('route', ['tap_land_for_mana', 'tap_lands_bulk'])
def test_fixed_mixed_tap_only_land_sphere_is_not_paid_ability_bypass(game, seat, route):
    env = mana_position(seat)
    env._state.players[seat].mana_pool = {}
    cid = vector_card(env._state, 'Simic Growth Chamber', seat).id
    vector_card(env._state, 'Damping Sphere', seat)
    action = land_action(env, cid, route, 'C')
    assert all(parse_activated_cost(spec[1]) == ActivatedCost(tap_source=True)
               for spec in mana_ability_specs(env._state.cards[cid], env._state))
    result = checked_action(env._state, env._rules, seat, action)
    assert result.players[seat].mana_pool['C'] == 1
    client, match = game
    identifier = retain(match, env)
    response = client.post(f'/matches/{identifier}/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    assert restart(identifier).state.players[seat].mana_pool['C'] == 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('route', ['tap_land_for_mana', 'tap_lands_bulk'])
@pytest.mark.parametrize('field,value', [('ability_index', 99), ('output_bundle', {'B': 2}),
                                       ('unknown_choice', {'selected': 'unsupported'})])
def test_legacy_land_intent_selected_fields_must_not_be_silently_dropped(game, seat, route, field, value):
    env = mana_position(seat)
    env._state.players[seat].mana_pool = {}
    cid = card(env, 'Forest', seat)
    action = {**land_action(env, cid, route, 'G'), field: value}
    before = env.snapshot()
    # Strict encoded input and raw HTTP already reject these requested parameters.
    with pytest.raises(ActionRejected):
        env.lookup(action)
    client, match = game
    retain(match, env)
    rejected(client, match, action, seat)
    assert env.snapshot() == before
    # Desired consumer contract; current complete_action normalization drops them.
    with pytest.raises(ActionRejected):
        env.lookup_intent(action)
