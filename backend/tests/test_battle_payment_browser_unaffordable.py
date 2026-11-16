"""Real Pact/turn/choice controls for the declared unaffordable browser fixture."""
from copy import deepcopy
import importlib
import importlib.util

import pytest

from card_data.seed_cards import SEED_CARD_DATA
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Step, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine


def birth(seat):
    name = 'tests.battle_payment_unaffordable_fixture'
    assert importlib.util.find_spec(name) is not None, 'Unaffordable Pact fixture is missing'
    return importlib.import_module(name).unaffordable_midgame(seat)


def genuine_obligation(seat):
    state, ids = birth(seat)
    rules = RulesEngine()
    start_turn = state.turn
    assert state.pending_mechanic_choice is None and not state.delayed_triggers
    state = checked_action(state, rules, seat,
                           {'type': 'cast_spell', 'card_id': ids['pacts'][0]})
    assert state.stack[-1].source_card_id == ids['pacts'][0]
    searched = False
    opponent_upkeep = False
    for _ in range(160):
        pending = state.pending_mechanic_choice
        if pending:
            assert pending['player_id'] == seat
            if pending['kind'] == 'deferred_upkeep_payment':
                assert searched and opponent_upkeep
                assert state.turn > start_turn and state.active_player == seat
                assert state.step == Step.UPKEEP
                assert state.cards[ids['pacts'][0]].zone == Zone.GRAVEYARD
                return state
            assert pending['kind'] == 'search_library' and not searched
            selected = next(cid for cid in pending['options'] if state.cards[cid].name == 'Grizzly Bears')
            state = checked_action(state, rules, seat,
                                   {'type': 'choose_mechanic', 'card_ids': [selected]})
            assert state.cards[selected].zone == Zone.HAND
            assert len(state.delayed_triggers) == 1
            assert state.delayed_triggers[0]['effect_key'] == 'deferred_upkeep_payment'
            searched = True
        else:
            if state.active_player == 3-seat and state.step == Step.UPKEEP:
                opponent_upkeep = True
            assert state.winner is None
            state = checked_action(state, rules, state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('Genuine Pact progression did not reach its upkeep choice')


@pytest.mark.parametrize('seat', [1, 2])
def test_birth_has_no_injected_choice_and_only_real_zero_cost_pacts_are_affordable(seat):
    before = deepcopy(SEED_CARD_DATA)
    state, ids = birth(seat)
    assert len(state.cards) == 120
    assert all(sum(card.owner == player for card in state.cards.values()) == 60 for player in (1, 2))
    assert state.pending_mechanic_choice is None and not state.delayed_triggers
    assert all(state.cards[cid].name == 'Grizzly Bears' for cid in state.players[seat].battlefield)
    assert not any(state.players[seat].mana_pool.values())
    spells = {move['card_id'] for move in RulesEngine().legal_moves(state, seat)
              if move['type'] == 'cast_spell'}
    assert set(ids['pacts']) <= spells and ids['battle'] not in spells
    assert SEED_CARD_DATA == before


@pytest.mark.parametrize('seat', [1, 2])
def test_real_cast_search_and_native_turns_offer_only_decline(seat):
    state = genuine_obligation(seat)
    pending = state.pending_mechanic_choice
    assert pending['kind'] == 'deferred_upkeep_payment'
    assert pending['options'] == ['decline']
    moves = RulesEngine().legal_moves(state, seat)
    assert len(moves) == 1 and moves[0]['kind'] == pending['kind']
    assert moves[0]['options'] == ['decline'] and moves[0]['player_id'] == seat


@pytest.mark.parametrize('seat', [1, 2])
def test_choice_roundtrip_rejects_unoffered_pay_and_real_decline_loses(seat):
    state = genuine_obligation(seat)
    snapshot = serialize_match_snapshot(state)
    restored = deserialize_match_snapshot(deepcopy(snapshot))
    assert serialize_match_snapshot(restored) == snapshot
    with pytest.raises(ActionRejected):
        checked_action(restored, RulesEngine(), seat,
                       {'type': 'choose_mechanic', 'card_ids': ['pay']})
    assert serialize_match_snapshot(restored) == snapshot
    result = checked_action(restored, RulesEngine(), seat,
                            {'type': 'choose_mechanic', 'card_ids': ['decline']})
    assert result.pending_mechanic_choice is None
    assert result.winner == 3-seat and result.step == Step.UPKEEP
