"""Lossless custom evaluator traces, using public canonical basic lands."""
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from analytics.action_replay import ReplayMismatch, reconstruct_game
from analytics.decision_quality import build_trace_payload
from analytics.resource_budget import RESOURCE_LIMITS, ResourceBudget, SimulationResourceLimit
from scripts import regression_matrix_replay as runner
from tests.regression_agent_wave2.support import entry


def quality_game(monkeypatch, starting_player=1, *, trace_builder=None, budget=None, ticks=80):
    # Both land names make shuffle order observable; no private game is a fixture.
    deck = [entry('Island', 30), entry('Mountain', 30)]
    chosen = []
    mulligans = {1: 0, 2: 0}

    def choose(_self, state, legal, pid):
        if state.pending_mechanic_choice:
            action = {'type': 'choose_mechanic',
                      'card_ids': list(reversed(state.players[pid].hand[:state.pending_mechanic_choice['count']]))}
        elif state.pregame_pending and mulligans[pid] < 2:
            mulligans[pid] += 1
            action = {'type': 'mulligan'}
        else:
            action = next((move for move in legal if move['type'] in {'keep_hand', 'play_land'}),
                          {'type': 'pass_priority'})
        action = runner.complete_action(action)
        chosen.append(deepcopy(action))
        return SimpleNamespace(action=action, reasoning='public deterministic replay fixture')

    monkeypatch.setattr(runner.AIAgent, 'choose_action', choose)
    def quality(state, pid, legal, action, decision):
        return build_trace_payload(state, pid, legal, action, getattr(decision, 'reasoning', ''))
    builder = trace_builder or runner.contextual_trace(quality, {1: 'Control', 2: 'Burn'})
    result = runner.run_game(deepcopy(deck), deepcopy(deck), 1108, 'casual', ticks,
                             starting_player=starting_player, trace_builder=builder, budget=budget)
    result['seed'] = 1108
    return deck, result, chosen


@pytest.mark.parametrize('starting_player', [1, 2])
def test_quality_evaluator_reconstructs_complete_actions_for_both_seats(monkeypatch, starting_player):
    deck, game, chosen = quality_game(monkeypatch, starting_player)
    before = deepcopy((deck, game))
    traces = [json.loads(line[9:]) for line in game['log'] if line.startswith('AI TRACE ')]
    assert len(traces) == game['ticks'] == 80
    assert any(action['type'] == 'choose_mechanic' and len(action['card_ids']) == 2 for action in chosen)
    report = reconstruct_game(deck, deck, game)
    assert report['matched'] and report['decisions'] == 80
    assert [trace['replay']['action'] for trace in traces] == chosen
    assert all(trace['replay']['schema_version'] == 1 for trace in traces)
    assert (deck, game) == before


@pytest.mark.parametrize('mutation', ['missing', 'version', 'bool_version', 'shape', 'actor',
                                    'hand', 'battlefield', 'legal', 'action', 'outer_actor',
                                    'outer_action', 'outer_turn', 'outer_null_operand'])
def test_replay_envelope_corruption_fails_closed(monkeypatch, mutation):
    deck, game, _ = quality_game(monkeypatch)
    index = next(i for i, line in enumerate(game['log']) if line.startswith('AI TRACE '))
    trace = json.loads(game['log'][index][9:])
    assert 'replay' in trace
    envelope = trace['replay']
    if mutation == 'missing':
        envelope.pop('hand')
    elif mutation == 'version':
        envelope['schema_version'] = 2
    elif mutation == 'bool_version':
        envelope['schema_version'] = True
    elif mutation == 'shape':
        trace['replay'] = None
    elif mutation == 'actor':
        envelope['pid'] = 2
    elif mutation == 'hand':
        envelope['hand'] = []
    elif mutation == 'battlefield':
        envelope['battlefield'] = ['Island']
    elif mutation == 'legal':
        envelope['legal_action_types'] = []
    elif mutation == 'action':
        envelope['action'] = {'type': 'cast_spell'}
    elif mutation == 'outer_actor':
        trace['pid'] = 2
    elif mutation == 'outer_action':
        trace['action']['type'] = 'pass_priority'
    elif mutation == 'outer_turn':
        trace['turn'] += 1
    elif mutation == 'outer_null_operand':
        trace['action']['unrecorded_operand'] = None
    game['log'][index] = 'AI TRACE ' + json.dumps(trace)
    with pytest.raises(ReplayMismatch) as caught:
        reconstruct_game(deck, deck, game)
    assert caught.value.diagnostic['decision'] == 0


def test_old_compact_quality_traces_are_not_backfilled(monkeypatch):
    deck, game, _ = quality_game(monkeypatch)
    for index, line in enumerate(game['log']):
        if line.startswith('AI TRACE '):
            trace = json.loads(line[9:])
            assert trace.pop('replay')
            game['log'][index] = 'AI TRACE ' + json.dumps(trace)
    with pytest.raises(ReplayMismatch) as caught:
        reconstruct_game(deck, deck, game)
    assert caught.value.diagnostic['decision'] == 0
    assert caught.value.diagnostic['field'] == 'hand'


def test_builder_cannot_supply_a_replay_envelope(monkeypatch):
    with pytest.raises(ValueError, match='reserved'):
        quality_game(monkeypatch, trace_builder=lambda *_: {'replay': {}})


def test_envelope_stays_inside_existing_trace_budget(monkeypatch):
    # The custom payload itself fits; its added execution evidence does not.
    budget = ResourceBudget(dict(RESOURCE_LIMITS, trace_entry_utf8_bytes=300))
    with pytest.raises(SimulationResourceLimit, match='trace_entry'):
        quality_game(monkeypatch, trace_builder=lambda *_: {'trace': True}, budget=budget, ticks=1)


@pytest.mark.parametrize('operand', ['hybrid_choices', 'bands'])
def test_full_action_is_bounded_before_builder_copy_or_execution(monkeypatch, operand):
    # Contract-valid adversarial input; no claim that this attack is rules-legal.
    action = {'type': 'attack', 'attackers': []}
    action[operand] = (['W'] * 62500 if operand == 'hybrid_choices' else
                       [['public-card-id-' + 'x' * 80] * 250 for _ in range(125)])
    action = runner.complete_action(action)
    deck = [entry('Island', 60)]
    monkeypatch.setattr(runner.AIAgent, 'choose_action',
                        lambda *_: SimpleNamespace(action=action, reasoning='size boundary fixture'))
    def forbidden(*_args, **_kwargs):
        pytest.fail('Oversized execution operands reached builder/copy/checked transition')
    monkeypatch.setattr(runner, 'checked_action', forbidden)
    with pytest.raises(SimulationResourceLimit):
        runner.run_game(deck, deck, 1108, 'casual', 1,
                        trace_builder=forbidden, budget=ResourceBudget())
