"""Canonical producer choices; native payment and training admission stay authoritative."""
from copy import deepcopy
import json

import pytest

from ai.agent import AIAgent
from ai.action_contract import complete_action
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from tests.test_linked_damage_targets import raw_card
from tests.test_training_choice_coverage import FIXTURES, position


def canonical(name):
    rows = [json.loads(line) for line in
            (FIXTURES / 'knowledge_profiles/seed155-scryfall.jsonl').read_text().splitlines()]
    rows += json.loads((FIXTURES / 'cast_resources/canonical.json').read_text())['data']
    raw = next(row for row in rows if row['name'] == name)
    assert raw['object'] == 'card' and raw['id'] and raw['oracle_id']
    return raw


def spectral_position(seat, pool, *, name='Spectral Procession', target_name=None):
    env = position(seat)
    state = env._state
    for player in state.players.values():
        for cid in list(player.hand):
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            player.library.append(cid)
        player.hand.clear()
    raw = canonical(name)
    card = raw_card(state, raw, seat, Zone.HAND)
    assert card.mana_cost == raw['mana_cost']
    if name == 'Spectral Procession':
        assert card.mana_cost == '{2/W}{2/W}{2/W}'
    assert card.oracle_text == raw['oracle_text'] and card.type_line == raw['type_line']
    target = raw_card(state, canonical(target_name), 3-seat, Zone.BATTLEFIELD) if target_name else None
    state.players[seat].mana_pool = pool.copy()
    agent = AIAgent(difficulty='strong', archetype='Tokens')
    move = next(move for move in env._rules.legal_moves(state, seat)
                if move['type'] == 'cast_spell' and move['card_id'] == card.id)
    if target is not None:
        move['targets'] = {'target_card_id': target.id}
    return env, agent, move


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('pool,expected', [({'W': 3}, ['W', 'W', 'W']),
                                        ({'W': 1, 'C': 4}, ['W', '2', '2']),
                                        ({'C': 6}, ['2', '2', '2'])])
def test_materialized_hybrid_is_explicit_and_preserves_native_payment(seat, pool, expected):
    env, agent, move = spectral_position(seat, pool)
    before, original = env.snapshot(), deepcopy(move)
    implicit = complete_action(agent._materialize_action_without_resources(env._state, move, seat))
    native = checked_action(env._state, agent.engine, seat, implicit)
    action = agent._materialize_action(env._state, move, seat)
    assert action.get('hybrid_choices') == expected
    completed = complete_action(action)
    assert completed == {**implicit, 'hybrid_choices': expected}
    assert env.lookup_intent(action) == env.lookup(completed)
    projected = checked_action(env._state, agent.engine, seat, completed)
    assert serialize_match_snapshot(projected) == serialize_match_snapshot(native)
    assert env.snapshot() == before and move == original
    env.step(completed)
    assert env._state.cards[move['card_id']].zone == Zone.STACK
    assert env._state.players[seat].mana_pool == native.players[seat].mana_pool


@pytest.mark.parametrize('seat', [1, 2])
def test_explicit_generic_payment_is_not_replaced_by_preferred_white(seat):
    env, agent, move = spectral_position(seat, {'W': 3, 'C': 6})
    move['hybrid_choices'] = ['2', '2', '2']
    before, original = env.snapshot(), deepcopy(move)
    action = agent._materialize_action(env._state, move, seat)
    assert action['hybrid_choices'] == ['2', '2', '2']
    assert env.snapshot() == before and move == original
    env.step(complete_action(action))
    assert sum(env._state.players[seat].mana_pool.values()) == 3


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('pool', [{'W': 2}, {'U': 3}, {}])
def test_unpayable_cast_is_not_completed(seat, pool):
    env, agent, move = spectral_position(seat, {'W': 3})
    env._state.players[seat].mana_pool = pool
    before, original = env.snapshot(), deepcopy(move)
    action = agent._materialize_action(env._state, move, seat)
    assert action.get('_invalid_ai_choice') is True
    with pytest.raises(ActionRejected):
        env.lookup_intent(action)
    assert env.snapshot() == before and move == original


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('branches', [[], ['W'], ['U', 'U', 'U'], ['2', '2', '2']])
def test_explicit_invalid_or_unaffordable_choices_are_not_repaired(seat, branches):
    env, agent, move = spectral_position(seat, {'W': 3})
    move['hybrid_choices'] = branches
    before, original = env.snapshot(), deepcopy(move)
    action = agent._materialize_action(env._state, move, seat)
    assert action['hybrid_choices'] == branches
    for boundary in (env.lookup, env.step):
        with pytest.raises(ActionRejected):
            boundary(complete_action(action))
        assert env.snapshot() == before
    assert move == original


@pytest.mark.parametrize('seat', [1, 2])
def test_free_effect_cast_does_not_choose_printed_hybrid_branches(seat):
    from rules_engine.effect_casts import materialize_cast, admit_cast
    env, _, move = spectral_position(seat, {'W': 3})
    state, cid = env._state, move['card_id']
    state.players[seat].hand.remove(cid)
    state.players[seat].graveyard.append(cid)
    state.cards[cid].move_to_zone(Zone.GRAVEYARD)
    state.players[seat].mana_pool = {}
    before = env.snapshot()
    action = materialize_cast(state, seat, cid)
    assert not action.get('_invalid_ai_choice')
    assert 'hybrid_choices' not in action
    assert env.snapshot() == before
    admit_cast(state, seat, action, {'target_card_id': cid})
    assert state.cards[cid].zone == Zone.STACK


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('pool,expected', [({'G': 2, 'C': 1}, ['G', 'G']),
                                        ({'W': 2, 'C': 1}, ['W', 'W']),
                                        ({'G': 1, 'W': 1, 'C': 1}, ['G', 'W'])])
def test_colored_hybrid_completion_matches_native_payment(seat, pool, expected):
    env, agent, move = spectral_position(seat, pool, name='Kitchen Finks')
    before, original = env.snapshot(), deepcopy(move)
    implicit = complete_action(agent._materialize_action_without_resources(env._state, move, seat))
    native = checked_action(env._state, agent.engine, seat, implicit)
    action = agent._materialize_action(env._state, move, seat)
    assert action.get('hybrid_choices') == expected
    assert complete_action(action) == {**implicit, 'hybrid_choices': expected}
    projected = checked_action(env._state, agent.engine, seat, complete_action(action))
    assert serialize_match_snapshot(projected) == serialize_match_snapshot(native)
    env.lookup_intent(action)
    assert env.snapshot() == before and move == original
    env.step(complete_action(action))
    assert sum(env._state.players[seat].mana_pool.values()) == 0


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('pool', [{'U': 3}, {'G': 1, 'C': 1}])
def test_colored_hybrid_wrong_color_or_insufficient_mana_is_not_completed(seat, pool):
    env, agent, move = spectral_position(seat, {'G': 2, 'C': 1}, name='Kitchen Finks')
    env._state.players[seat].mana_pool = pool
    before, original = env.snapshot(), deepcopy(move)
    action = agent._materialize_action(env._state, move, seat)
    assert action.get('_invalid_ai_choice') is True
    with pytest.raises(ActionRejected):
        env.lookup_intent(action)
    assert env.snapshot() == before and move == original


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('pool,expected,life', [({'C': 1}, ['P', 'P'], 16),
                                              ({'B': 1, 'C': 1}, ['B', 'P'], 18),
                                              ({'B': 2, 'C': 1}, ['B', 'B'], 20)])
def test_phyrexian_completion_matches_native_mana_and_life_payment(seat, pool, expected, life):
    env, agent, move = spectral_position(seat, pool, name='Dismember', target_name='Kitchen Finks')
    before, original = env.snapshot(), deepcopy(move)
    implicit = complete_action(agent._materialize_action_without_resources(env._state, move, seat))
    native = checked_action(env._state, agent.engine, seat, implicit)
    action = agent._materialize_action(env._state, move, seat)
    assert action.get('hybrid_choices') == expected
    assert complete_action(action) == {**implicit, 'hybrid_choices': expected}
    projected = checked_action(env._state, agent.engine, seat, complete_action(action))
    assert serialize_match_snapshot(projected) == serialize_match_snapshot(native)
    env.lookup_intent(action)
    assert env.snapshot() == before and move == original
    env.step(complete_action(action))
    assert env._state.players[seat].life == life
    assert sum(env._state.players[seat].mana_pool.values()) == 0


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('explicit', [False, True])
def test_phyrexian_life_cannot_be_paid_and_explicit_choice_is_not_repaired(seat, explicit):
    env, agent, move = spectral_position(seat, {'C': 1}, name='Dismember', target_name='Kitchen Finks')
    env._state.players[seat].life = 3
    if explicit:
        move['hybrid_choices'] = ['P', 'P']
    before, original = env.snapshot(), deepcopy(move)
    action = agent._materialize_action(env._state, move, seat)
    if explicit:
        assert action['hybrid_choices'] == ['P', 'P']
    else:
        assert action.get('_invalid_ai_choice') is True
    for boundary in (env.lookup_intent, lambda intent: env.step(complete_action(intent))):
        with pytest.raises(ActionRejected):
            boundary(action)
        assert env.snapshot() == before
    assert move == original


def test_hybrid_search_bound_rejects_before_native_expansion(monkeypatch):
    from ai.casting_resources import complete_cast_hybrid_choices
    from rules_engine import mana
    env, agent, move = spectral_position(1, {'W': 3})
    action = agent._materialize_action_without_resources(env._state, move, 1)
    # A producer hint beyond this AI budget, not an unsupported game mechanic.
    action = deepcopy(action)
    action['cost_options'][0]['mana_cost'] = '{W/U}' * 7
    before, original = env.snapshot(), deepcopy(action)
    def forbidden(*args, **kwargs):
        raise AssertionError('Unbounded native expansion')
    monkeypatch.setattr(mana, '_payment_requirements', forbidden)
    completed = complete_cast_hybrid_choices(agent, env._state, action, 1)
    assert completed == {**action, '_invalid_ai_choice': True}
    assert env.snapshot() == before and action == original
