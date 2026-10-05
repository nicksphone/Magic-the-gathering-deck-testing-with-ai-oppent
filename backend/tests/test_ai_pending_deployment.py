"""Strategic search must value a payable pending permanent, not only its lost card."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, Zone
from ai.pending_effects import planning_copy, settled_public_position
from rules_engine.engine import RulesEngine
from rules_engine.action_validation import checked_action
from tests.test_ai_search_prefix import bare_state


def observed():
    path = Path(__file__).parent / 'fixtures/ai_empty_board/observed-turn-nine.json'
    return deserialize_match_snapshot(json.loads(path.read_text()))


def test_observed_empty_board_deploys_instead_of_passing_for_six_turns():
    state = observed()
    before = serialize_match_snapshot(state)
    decision = AIAgent(difficulty='master', archetype='Drain', opponent_archetype='Tribal').choose_action(
        state, RulesEngine().legal_moves(state, 1), 1)
    assert decision.action['type'] == 'cast_spell'
    assert serialize_match_snapshot(state) == before
    accepted = checked_action(planning_copy(state), RulesEngine(), 1, decision.action)
    assert decision.action['card_id'] not in accepted.players[1].hand
    assert accepted.stack and accepted.stack[-1].source_card_id == decision.action['card_id']


@pytest.mark.parametrize('seat', [1, 2])
def test_horizon_keeps_actual_counter_response_value_and_original_stack(seat):
    state = bare_state(seat)
    card = deepcopy(next(card for card in observed().cards.values() if card.name == 'Priest of Forgotten Gods'))
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
    ai.engine.take_action(state, seat, {'type': 'cast_spell', 'card_id': card.id}, reject_invalid=True)
    before = serialize_match_snapshot(state)
    unanswered = ai._strategic_position_score(state, seat)
    response = planning_copy(state)
    ai.engine.take_action(response, seat, {'type': 'pass_priority'}, reject_invalid=True)
    ai.engine.take_action(response, opponent, {'type': 'cast_spell', 'card_id': counter.id,
                                             'targets': {'target_stack_id': response.stack[0].id}}, reject_invalid=True)
    assert ai._strategic_position_score(response, seat) < unanswered
    assert serialize_match_snapshot(state) == before
    assert state.stack and card.zone == Zone.STACK


@pytest.mark.parametrize('seat', [1, 2])
def test_pending_hidden_library_change_is_not_a_known_forecast(seat):
    state = bare_state(seat)
    draw = CardInstance('draw', 'Divination', seat, seat, Zone.HAND, ['Sorcery'],
                        mana_cost='{2}{U}', oracle_text='Draw two cards.')
    state.cards[draw.id] = draw
    state.players[seat].hand.append(draw.id)
    state.players[seat].mana_pool.update({'U': 3})
    ai = AIAgent(difficulty='master', archetype='Control')
    ai.engine.take_action(state, seat, {'type': 'cast_spell', 'card_id': draw.id}, reject_invalid=True)
    before = serialize_match_snapshot(state)
    assert settled_public_position(state, seat) is None
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('style', ['Drain', 'Tribal', 'Control', 'Ramp', 'Tempo'])
@pytest.mark.parametrize('name', ['Priest of Forgotten Gods', 'Blood Artist', 'Zulaport Cutthroat',
                                  'Cauldron Familiar', 'Elvish Clancaller', 'Llanowar Elves'])
def test_shared_strategic_horizon_values_supported_creature_development(seat, style, name):
    state = bare_state(seat)
    state.turn = 10
    card = deepcopy(next(card for card in observed().cards.values() if card.name == name))
    card.id, card.owner, card.controller, card.zone = 'candidate', seat, seat, Zone.HAND
    state.cards[card.id] = card
    state.players[seat].hand.append(card.id)
    state.players[seat].mana_pool.update({'B': 3, 'G': 3, 'C': 3})
    ai = AIAgent(difficulty='master', archetype=style)
    cast = next(move for move in RulesEngine().legal_moves(state, seat) if move['type'] == 'cast_spell')
    cast = ai._materialize_action(state, cast, seat)
    before = serialize_match_snapshot(state)
    score = ai._strategic_line_score(state, cast, seat, 0)
    wait = ai._strategic_line_score(state, {'type': 'pass_priority'}, seat, 0)
    assert score > wait
    assert serialize_match_snapshot(state) == before
