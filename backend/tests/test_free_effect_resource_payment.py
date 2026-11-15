"""Free native effects retain payment witnesses, not client-granted waivers."""
from copy import deepcopy
import random

import pytest

from ai.agent import AIAgent
from ai.action_contract import complete_action
from ai.casting_resources import _automatic_effect_cost_scope, choose_resource_payment
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.effect_casts import admit_cast, materialize_cast
from rules_engine.query_context import rule_query_scope
from tests.test_cast_resource_payments import ROWS, add, position


def graveyard_position(seat, name='Dig Through Time'):
    state, spell = position(seat, name)
    state.players[seat].hand.remove(spell.id)
    state.players[seat].graveyard.append(spell.id)
    spell.move_to_zone(Zone.GRAVEYARD)
    add(state, 'Ornithopter', seat, cards=ROWS)
    add(state, 'Ornithopter', seat, Zone.GRAVEYARD, cards=ROWS)
    return state, spell


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Dig Through Time', 'Reverse Engineer', 'Chord of Calling'])
def test_native_free_resource_cast_preserves_resources_and_root_rng(seat, name):
    state, spell = graveyard_position(seat, name)
    before = serialize_match_snapshot(state)
    global_rng, native_rng = random.getstate(), state.rng.getstate()
    action = materialize_cast(state, seat, spell.id)
    assert not action.get('_invalid_ai_choice')
    assert action.get('resource_payment') is not None
    assert not any(action['resource_payment'].values())
    assert serialize_match_snapshot(state) == before
    assert random.getstate() == global_rng and state.rng.getstate() == native_rng
    admit_cast(state, seat, action, {'target_card_id': spell.id})
    assert spell.zone == Zone.STACK
    item = next(item for item in state.stack if item.source_card_id == spell.id)
    assert item.payload['mana_spent'] == 0
    assert state.players[seat].mana_pool == before['players'][str(seat)]['mana_pool']
    assert state.players[seat].battlefield == before['players'][str(seat)]['battlefield']
    assert all(not state.cards[cid].tapped for cid in state.players[seat].battlefield)
    assert state.players[seat].exile == before['players'][str(seat)]['exile']
    assert set(state.players[seat].graveyard) == set(before['players'][str(seat)]['graveyard']) - {spell.id}


@pytest.mark.parametrize('seat', [1, 2])
def test_cached_trusted_resource_proposal_does_not_outlive_waiver(seat):
    state, spell = graveyard_position(seat)
    agent = AIAgent('strong')
    action = dict(type='cast_spell', card_id=spell.id, from_graveyard=True,
                  cost_choice={'id': 'base'}, targets={})
    before = serialize_match_snapshot(state)
    with rule_query_scope(state):
        with _automatic_effect_cost_scope(state, seat, spell.id):
            result = choose_resource_payment(agent, state, action, seat)
            assert not result.get('_invalid_ai_choice')
            assert result.get('resource_payment') is not None
            with pytest.raises(ActionRejected):
                checked_action(state, agent.engine, seat, complete_action(result))
        expired = choose_resource_payment(agent, state, action, seat)
        assert expired.get('_invalid_ai_choice')
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('flag', ['effect_cast', 'without_mana', 'suspend_cast'])
def test_client_flags_cannot_authorize_free_resource_trials(seat, flag):
    state, spell = graveyard_position(seat)
    agent = AIAgent('strong')
    action = dict(type='cast_spell', card_id=spell.id, from_graveyard=True,
                  cost_choice={'id': 'base'}, targets={})
    action[flag] = True
    original, before = deepcopy(action), serialize_match_snapshot(state)
    assert choose_resource_payment(agent, state, action, seat).get('_invalid_ai_choice')
    assert action == original and serialize_match_snapshot(state) == before
