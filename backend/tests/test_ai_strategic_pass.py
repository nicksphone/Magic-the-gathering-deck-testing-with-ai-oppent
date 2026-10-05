"""A scored wait is a real strategic option, not a stalled-action placeholder."""
from copy import deepcopy

import pytest

from ai.agent import AIAgent
from ai.heuristics import evaluate_board
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import checked_action
from tests.test_ai_search_prefix import bare_state
from tests.test_ai_recurring_engines import add, resolve
from tests.regression_agent_wave2.support import add as add_golden


STYLES = ['Aggro', 'Burn', 'Midrange', 'Control', 'Tempo', 'Ramp', 'Drain',
          'Aristocrats', 'Reanimator', 'Tokens', 'Tribal', 'Combo-lite',
          'Counter-heavy', 'Removal-heavy']


def position(seat, target_name='Memnite'):
    state = bare_state(seat)
    state.turn = 10
    target = (add_golden(state, target_name, seat, Zone.BATTLEFIELD)
              if target_name == 'Memnite' else add(state, target_name, seat))
    spell = add(state, 'Naturalize', seat, Zone.HAND)
    state.players[seat].mana_pool.update({'G': 1, 'C': 1})
    action = {'type': 'cast_spell', 'card_id': spell.id,
              'targets': {'target_card_id': target.id}}
    return state, action


def controlled_planner(monkeypatch, ai, actions, scores):
    # Isolate selection policy; these scores are test inputs, not card valuations.
    monkeypatch.setattr(ai, '_rank_moves', lambda *_args: list(actions))
    monkeypatch.setattr(ai, '_materialize_action', lambda _s, move, _p: deepcopy(move))
    monkeypatch.setattr(ai, '_strategic_line_score',
                        lambda _s, move, _p, depth: scores[move['type']])


@pytest.mark.parametrize('style', STYLES)
@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('best_type', ['pass_priority', 'cast_spell'])
def test_planner_preserves_highest_scored_action_for_every_style(monkeypatch, style, seat, best_type):
    state, cast = position(seat)
    wait = {'type': 'pass_priority'}
    ai = AIAgent(difficulty='master', archetype=style)
    scores = {kind: 10 if kind == best_type else -10 for kind in ['pass_priority', 'cast_spell']}
    controlled_planner(monkeypatch, ai, [wait, cast], scores)
    before = serialize_match_snapshot(state)
    assert ai._strategic_plan_action(state, [wait, cast], seat)['type'] == best_type
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_wait_is_evaluated_even_outside_shallow_shortlist(monkeypatch, seat):
    state, cast = position(seat)
    wait = {'type': 'pass_priority'}
    ai = AIAgent(difficulty='master', archetype='Tempo')
    # More ranked announcements than the root beam; all remain worse than waiting.
    ranked = [cast] + [{**deepcopy(cast), 'card_id': add(state, 'Naturalize', seat, Zone.HAND).id}
                       for _ in range(8)] + [wait]
    controlled_planner(monkeypatch, ai, ranked, {'cast_spell': -10, 'pass_priority': 10})
    assert ai._strategic_plan_action(state, ranked, seat) == wait


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('target_name', ['Memnite', 'The Meathook Massacre'])
def test_completed_canonical_friendly_destruction_does_not_override_better_wait(monkeypatch, seat, target_name):
    state, cast = position(seat, target_name)
    wait = {'type': 'pass_priority'}
    ai = AIAgent(difficulty='master', archetype='Midrange')
    before = serialize_match_snapshot(state)
    baseline = evaluate_board(state, seat)
    projected = checked_action(deepcopy(state), ai.engine, seat, cast)
    projected = resolve(projected)
    destruction_value = evaluate_board(projected, seat)
    assert destruction_value < baseline
    controlled_planner(monkeypatch, ai, [wait, cast],
                       {'pass_priority': baseline, 'cast_spell': destruction_value})
    assert ai._strategic_plan_action(state, [wait, cast], seat) == wait
    assert serialize_match_snapshot(state) == before
