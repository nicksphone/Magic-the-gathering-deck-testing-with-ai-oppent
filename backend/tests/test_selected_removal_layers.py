"""Selected-target admission does not bypass final paid-material safety."""
from copy import deepcopy

import pytest

from ai.action_contract import complete_action
from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_ai_friendly_material_conservation import CARDS, position
from tests.test_ai_final_spell_payment_value import settle as settle_choices
from tests.test_ai_recurring_engines import fixture
from tests.test_any_player_cast_damage import settle
from tests.test_linked_damage_targets import raw_card


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('enemy', [False, True])
def test_allowing_friendly_candidate_does_not_authorize_wasteful_final_action(seat, enemy):
    state, move, friendly, opposing = position(seat, 'Recruitment Officer', enemy)
    before, offered = serialize_match_snapshot(state), deepcopy(move)
    action = AIAgent('strong')._materialize_action(state, move, seat, allow_friendly_target=True)
    assert serialize_match_snapshot(state) == before and move == offered
    if not enemy:
        assert action.get('_invalid_ai_choice') is True
        assert state.cards[friendly].zone == Zone.BATTLEFIELD
        return
    assert not action.get('_invalid_ai_choice')
    assert action['targets']['target_card_id'] == opposing
    paid = checked_action(state, RulesEngine(), seat, complete_action(action))
    done = settle(paid)
    assert done.cards[friendly].zone == Zone.BATTLEFIELD
    assert done.cards[opposing].zone == Zone.EXILE
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_final_guard_retains_actual_paid_winning_friendly_destruction(seat):
    state = fixture()
    state.active_player = state.priority_player = seat
    for player in state.players.values():
        player.mana_pool = {color: 0 for color in 'WUBRGC'}
    lands = [raw_card(state, CARDS['Swamp'], seat, Zone.BATTLEFIELD) for _ in range(2)]
    friendly = raw_card(state, CARDS['Recruitment Officer'], seat, Zone.BATTLEFIELD)
    raw_card(state, CARDS['Blood Artist'], seat, Zone.BATTLEFIELD)
    spell = raw_card(state, CARDS['Go for the Throat'], seat, Zone.HAND)
    state.players[3-seat].life = 1
    rules = RulesEngine()
    move = next(move for move in rules.legal_moves(state, seat) if move.get('card_id') == spell.id)
    move = {**move, 'targets': {'target_card_id': friendly.id}}
    before = serialize_match_snapshot(state)
    action = AIAgent('strong')._materialize_action(state, move, seat, allow_friendly_target=True)
    assert not action.get('_invalid_ai_choice')
    assert action['targets']['target_card_id'] == friendly.id
    paid = checked_action(state, rules, seat, complete_action(action))
    assert all(paid.cards[land.id].tapped for land in lands)
    done = settle_choices(paid)
    assert done.cards[friendly.id].zone == Zone.GRAVEYARD
    assert done.winner == seat
    assert serialize_match_snapshot(state) == before
