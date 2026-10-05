"""A pending stack must not add a second absolute score to the position."""
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from ai.agent import AIAgent
from ai.pending_effects import planning_copy
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_ai_pending_deployment import observed
from tests.test_ai_search_prefix import bare_state


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('offset', [-100.0, 0.0, 100.0])
def test_pass_only_response_delta_is_independent_of_absolute_score(seat, offset):
    state = bare_state(seat)
    card = deepcopy(next(c for c in observed().cards.values() if c.name == 'Priest of Forgotten Gods'))
    card.id, card.owner, card.controller, card.zone = 'candidate', seat, seat, Zone.HAND
    state.cards[card.id] = card
    state.players[seat].hand.append(card.id)
    state.players[seat].mana_pool.update({'B': 2})
    ai = AIAgent(difficulty='master', archetype='Drain')
    state = checked_action(state, ai.engine, seat, {'type': 'cast_spell', 'card_id': card.id})
    before = serialize_match_snapshot(state)
    score = ai._strategic_position_score
    with patch.object(ai, '_strategic_top_actions', return_value=[{'type': 'pass_priority'}]), \
            patch.object(ai, '_strategic_position_score', side_effect=lambda s, p: score(s, p) + offset):
        assert ai._stack_two_ply_value(state, seat) == pytest.approx(0.0)
    assert serialize_match_snapshot(state) == before


def test_actual_later_empty_board_develops_payable_body_instead_of_repeated_passes():
    path = Path(__file__).parent / 'fixtures/ai_empty_board/observed-turn-eleven.json'
    state = deserialize_match_snapshot(json.loads(path.read_text()))
    before = serialize_match_snapshot(state)
    ai = AIAgent(difficulty='master', archetype='Drain', opponent_archetype='Tribal')
    decision = ai.choose_action(state, RulesEngine().legal_moves(state, 1), 1)
    assert decision.action['type'] == 'cast_spell'
    assert state.cards[decision.action['card_id']].name == 'Priest of Forgotten Gods'
    assert serialize_match_snapshot(state) == before
    accepted = checked_action(planning_copy(state), RulesEngine(), 1, decision.action)
    assert decision.action['card_id'] not in accepted.players[1].hand
    assert accepted.stack[-1].source_card_id == decision.action['card_id']


@pytest.mark.parametrize('seat', [1, 2])
def test_real_counter_response_is_negative_and_score_offset_invariant(seat):
    state = bare_state(seat)
    card = deepcopy(next(c for c in observed().cards.values() if c.name == 'Priest of Forgotten Gods'))
    card.id, card.owner, card.controller, card.zone = 'candidate', seat, seat, Zone.HAND
    state.cards[card.id] = card
    state.players[seat].hand.append(card.id)
    state.players[seat].mana_pool.update({'B': 2})
    opponent = 3-seat
    counter = CardInstance('counter', 'Counterspell', opponent, opponent, Zone.HAND, ['Instant'],
                           mana_cost='{U}{U}', oracle_text='Counter target spell.')
    state.cards[counter.id] = counter
    state.players[opponent].hand.append(counter.id)
    state.players[opponent].mana_pool.update({'U': 2})
    ai = AIAgent(difficulty='master', archetype='Drain')
    state = checked_action(state, ai.engine, seat, {'type': 'cast_spell', 'card_id': card.id})
    state = checked_action(state, ai.engine, seat, {'type': 'pass_priority'})
    before = serialize_match_snapshot(state)
    baseline = ai._stack_two_ply_value(state, seat)
    assert baseline < 0
    score = ai._strategic_position_score
    with patch.object(ai, '_strategic_position_score', side_effect=lambda s, p: score(s, p) + 100):
        assert ai._stack_two_ply_value(state, seat) == pytest.approx(baseline)
    assert serialize_match_snapshot(state) == before
