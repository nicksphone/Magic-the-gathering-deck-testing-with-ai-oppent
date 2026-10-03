"""Public-count forecasts must agree with supported real draw resolution."""
import json
from copy import deepcopy
from pathlib import Path

import pytest

from ai.agent import AIAgent
from effects.registry import resolve_effect
from game_state.serializers import serialize_match_snapshot
from game_state.state import Step
from rules_engine.draw_restrictions import forecast_draw_count
from rules_engine.engine import RulesEngine
from tests.test_ai_recurring_engines import add
from tests.test_permanent_kicker import setup

ROWS = {c['name']: c for c in json.loads((Path(__file__).parent / 'fixtures/draw_forecast.json').read_text())}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('sources', [[], ['Thought Reflection'], ["Teferi's Ageless Insight"],
                                   ['Thought Reflection', "Teferi's Ageless Insight"]])
@pytest.mark.parametrize('draw_step', [False, True])
@pytest.mark.parametrize('previous_draws', [0, 1])
def test_forecast_matches_default_resolution_without_mutating_match(seat, sources, draw_step, previous_draws):
    state, _, _ = setup('Citanul Woodreaders', seat)
    for name in sources:
        add(state, name, seat, cards=ROWS)
    state.step = Step.DRAW if draw_step else Step.PRECOMBAT_MAIN
    state.draws_this_turn[seat] = previous_draws
    state.draws_in_current_draw_step[seat] = previous_draws
    before = serialize_match_snapshot(state)
    predicted = forecast_draw_count(state, seat, 3)
    assert serialize_match_snapshot(state) == before
    projection = deepcopy(state)
    hand_size = len(projection.players[seat].hand)
    resolve_effect(projection, seat, 'draw_cards', {'target_player': seat, 'amount': 3})
    assert len(projection.players[seat].hand) - hand_size == predicted


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('cap', ['Spirit of the Labyrinth', 'Narset, Parter of Veils'])
@pytest.mark.parametrize('previous_draws', [0, 1])
def test_draw_caps_apply_between_replaced_single_draws(seat, cap, previous_draws):
    state, _, _ = setup('Citanul Woodreaders', seat)
    add(state, 'Thought Reflection', seat, cards=ROWS)
    add(state, cap, 3-seat, cards=ROWS)
    state.draws_this_turn[seat] = previous_draws
    assert forecast_draw_count(state, seat, 4) == 1-previous_draws


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master'])
@pytest.mark.parametrize('remaining', [0, 2, 3, 4])
def test_actual_ai_cost_choice_accounts_for_doubled_draw_deckout(seat, difficulty, remaining):
    state, card, _ = setup('Citanul Woodreaders', seat)
    add(state, 'Thought Reflection', seat, cards=ROWS)
    state.players[seat].library = state.players[seat].library[:remaining]
    move = next(m for m in RulesEngine().legal_moves(state, seat) if m.get('card_id') == card.id)
    action = AIAgent(difficulty)._materialize_action(state, move, seat)
    assert action['cost_choice']['id'] == ('kicker' if remaining >= 4 else 'base')


@pytest.mark.parametrize('seat', [1, 2])
def test_exhaustion_cap_and_suppression_use_no_hidden_library_identity(seat):
    state, _, _ = setup('Citanul Woodreaders', seat)
    source = add(state, 'Thought Reflection', seat, cards=ROWS)
    state.players[seat].library = ['unreadable-private-card'] * 2
    assert forecast_draw_count(state, seat, 10000) == 3
    resolve_effect(state, 3-seat, 'temporary_ability_loss', {'target_card_id': source.id})
    assert forecast_draw_count(state, seat, 2) == 2


def test_symmetric_first_draw_exception_counts_only_own_draw_step():
    state, _, _ = setup('Citanul Woodreaders', 2)
    add(state, "Teferi's Ageless Insight", 2, cards=ROWS)
    state.step, state.active_player = Step.DRAW, 1
    assert forecast_draw_count(state, 2, 1) == 2


def test_base_and_kicked_payoffs_compare_replaced_counts():
    state, _, _ = setup('Citanul Woodreaders')
    add(state, 'Thought Reflection', cards=ROWS)
    assert AIAgent('master')._kicker_draw_gain(state, 1, 1, 2) == 6
