"""Final resource witnesses use canonical public printings, never game captures."""
from copy import deepcopy
import random

import pytest

from ai.agent import AIAgent
from ai.action_contract import complete_action
from ai.casting_resources import choose_resource_payment
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.query_context import rule_query_scope
from tests.mana_canonical_76 import canonical_card
from tests.test_cast_resource_payments import ROWS, add, position
from training.environment import TrainingEnvironment


def march_position(seat):
    state, spell = position(seat, 'March of the Multitudes')
    state.turn = 6
    # Three lands plus two full printed white/green creatures can fund X=2.
    for name in ('Plains', 'Plains', 'Forest'):
        land = canonical_card(name, id=state.allocate_object_id(), owner=seat,
                              controller=seat, zone=Zone.BATTLEFIELD,
                              tapped=False, summoning_sick=False)
        state.cards[land.id] = land
        state.players[seat].battlefield.append(land.id)
    for _ in range(2):
        add(state, 'Kitchen Finks', seat, cards=ROWS)
    assert spell.oracle_text == ROWS[spell.name]['oracle_text']
    assert spell.mana_cost == '{X}{G}{W}{W}'
    return state, spell


def intent(spell, x):
    return {'type': 'cast_spell', 'card_id': spell.id,
            'cost_choice': {'id': 'base'}, 'targets': {'x_value': x},
            'from_exile': False, 'from_graveyard': False, 'from_library': False}


def env_for(state):
    # Boundary-only adapter; no new game, repository or environment reset.
    env = TrainingEnvironment()
    env._state = state
    return env


def pure_completion(ai, state, action, seat):
    before = serialize_match_snapshot(state)
    original = deepcopy(action)
    rng = random.getstate()
    result = choose_resource_payment(ai, state, action, seat)
    assert serialize_match_snapshot(state) == before
    assert action == original and random.getstate() == rng
    return result


@pytest.mark.parametrize('seat', [1, 2])
def test_final_x_resource_materialization_is_strictly_servable(seat):
    state, spell = march_position(seat)
    ai = AIAgent(archetype='Tokens')
    move = next(m for m in ai.engine.legal_moves(state, seat)
                if m.get('type') == 'cast_spell' and m.get('card_id') == spell.id)
    before = serialize_match_snapshot(state)
    rng = random.getstate()
    original = deepcopy(move)
    action = complete_action(ai._materialize_action(state, move, seat))
    assert action['targets']['x_value'] == 2
    assert not action.get('_invalid_ai_choice')
    assert action.get('resource_payment') is not None
    assert env_for(state).lookup(action, seat)['action']['resource_payment'] == action['resource_payment']
    after = checked_action(state, ai.engine, seat, action)
    receipt = next(item.payload['__casting_resource_payment'] for item in after.stack
                   if item.source_card_id == spell.id)
    assert len(receipt['convoke']) == 2
    assert all(after.cards[cid].tapped for cid in state.players[seat].battlefield)
    assert serialize_match_snapshot(state) == before and move == original
    assert random.getstate() == rng


@pytest.mark.parametrize('seat', [1, 2])
def test_omitted_native_fallback_is_explicit_before_scoring(monkeypatch, seat):
    from ai import casting_resources as module
    state, spell = march_position(seat)
    ai = AIAgent(archetype='Tokens')
    calls, scored = [], []
    take, score = ai.engine.take_action, module._score

    def observe_take(projected, actor, candidate, **kwargs):
        calls.append(deepcopy(candidate))
        return take(projected, actor, candidate, **kwargs)

    def observe_score(agent, before, after, actor):
        assert calls[-1].get('resource_payment') is not None
        scored.append(calls[-1])
        return score(agent, before, after, actor)

    monkeypatch.setattr(ai.engine, 'take_action', observe_take)
    monkeypatch.setattr(module, '_score', observe_score)
    result = pure_completion(ai, state, intent(spell, 2), seat)
    assert scored and result.get('resource_payment') is not None
    assert 'resource_payment' not in calls[0]  # Keep native fallback, do not prune it.
    env_for(state).lookup(result, seat)


@pytest.mark.parametrize('seat', [1, 2])
def test_empty_resource_payment_is_valid_and_not_silently_omitted(seat):
    state, spell = march_position(seat)
    ai = AIAgent(archetype='Tokens')
    action = intent(spell, 0)
    result = pure_completion(ai, state, action, seat)
    assert result.get('resource_payment') is not None
    assert not any(result['resource_payment'].values())
    env_for(state).lookup(result, seat)
    explicit = {**action, 'resource_payment': {}}
    assert pure_completion(ai, state, explicit, seat) == explicit
    env_for(state).lookup(explicit, seat)
    with pytest.raises(ActionRejected, match='Missing required choice: resource_payment'):
        env_for(state).lookup(action, seat)


@pytest.mark.parametrize('seat', [1, 2])
def test_empty_or_foreign_resources_cannot_fund_x_two(seat):
    state, spell = march_position(seat)
    env = env_for(state)
    for payment in ({}, {'convoke': [{'card_id': spell.id, 'pay_as': 'W'}]}):
        before = serialize_match_snapshot(state)
        with pytest.raises(ActionRejected):
            env.lookup({**intent(spell, 2), 'resource_payment': payment}, seat)
        assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_resource_cache_returns_isolated_explicit_witness(seat):
    state, spell = march_position(seat)
    ai = AIAgent(archetype='Tokens')
    action = intent(spell, 2)
    with rule_query_scope(state):
        first = pure_completion(ai, state, action, seat)
        assert first.get('resource_payment') is not None
        expected = deepcopy(first)
        first['resource_payment']['convoke'].clear()
        second = pure_completion(ai, state, action, seat)
        assert second == expected
        second['resource_payment']['convoke'].clear()
        assert pure_completion(ai, state, action, seat) == expected
    env_for(state).lookup(expected, seat)


@pytest.mark.parametrize('seat', [1, 2])
def test_paused_native_cast_keeps_its_explicit_resource_receipt(seat):
    from tests.test_forge_human_replacement_order import setup
    state, _, _, _ = setup(seat)
    state.players[seat].mana_pool = {'G': 1}
    spell = add(state, 'March of the Multitudes', seat, Zone.HAND, cards=ROWS)
    ai = AIAgent(archetype='Tokens')
    action = pure_completion(ai, state, intent(spell, 0), seat)
    assert action.get('resource_payment') is not None
    assert not any(action['resource_payment'].values())
    projected = checked_action(state, ai.engine, seat, action)
    assert projected.pending_replacement_choice is not None
    assert projected.cards[spell.id].zone == Zone.HAND
    owner = projected.mana_continuation['frames'][0]
    assert owner['op'] == 'cast' and owner['payer'] == seat
    assert owner['data']['source']['card_id'] == spell.id
    assert owner['data']['payment_details']['resource_payment'] == action['resource_payment']
    env_for(state).lookup(action, seat)


@pytest.mark.parametrize('seat', [1, 2])
def test_unpayable_completion_is_invalid_not_pass_or_incomplete_cast(seat):
    state, spell = march_position(seat)
    for cid in state.players[seat].battlefield:
        state.cards[cid].tapped = True
    ai = AIAgent(archetype='Tokens')
    with rule_query_scope(state):
        for _ in range(2):
            result = pure_completion(ai, state, intent(spell, 2), seat)
            assert result['type'] == 'cast_spell' and result.get('_invalid_ai_choice') is True
