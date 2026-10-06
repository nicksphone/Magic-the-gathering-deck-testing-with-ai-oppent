"""Canonical diagnostic controls plus an ordinary RED for the harmful sealed play."""
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from ai.agent import AIAgent
from ai import pending_effects
from ai.action_contract import complete_action
from ai.information import decision_view
from ai.pending_effects import friendly_destruction_profit
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.natural_heat_diagnostic_support import (
    advance_until, canonical, canonical_control, exact_state, private_cards,
    rank_diagnostic, receipts, removal_delta, replay_receipt,
)


DEFAULT_LEGACY_SCHEDULER = {
    'version': 1, 'extra_turns': [], 'next_phase_visit': 1,
    'next_schedule_ordinal': 1, 'normal_turn_successor': None,
    'phase_cursor': 0, 'phase_plan': [],
}


def _current_legacy_snapshot(snapshot):
    normalized = serialize_match_snapshot(deserialize_match_snapshot(snapshot))
    assert normalized['scheduler'] == DEFAULT_LEGACY_SCHEDULER
    return normalized


def _assert_legacy_snapshot_parity(actual, historical):
    expected = _current_legacy_snapshot(historical)
    assert actual['scheduler'] == DEFAULT_LEGACY_SCHEDULER
    # Only the original collector's historical AI TRACE log is excluded.
    assert canonical({k: v for k, v in actual.items() if k != 'log'}) == canonical(
        {k: v for k, v in expected.items() if k != 'log'})


def test_exact_captured_resolution_preserves_original_trace_and_proves_loss():
    row, state = exact_state()
    before = canonical(serialize_match_snapshot(state))
    assert canonical(RulesEngine().legal_moves(state, row['pid'])) == canonical(row['legal_moves'])
    for receipt in receipts():
        if receipt['event'] != 'applied' or not 303 <= receipt['tick'] <= 305:
            continue
        state = checked_action(state, RulesEngine(), receipt['pid'], receipt['action'])
        actual = serialize_match_snapshot(state)
        _assert_legacy_snapshot_parity(actual, receipt['snapshot'])
    victim = row['action']['targets']['target_card_id']
    assert state.cards[victim].zone == Zone.GRAVEYARD
    assert row['action']['card_id'] in state.players[row['pid']].graveyard
    assert [item.label for item in state.stack] == ['Memory Deluge']
    assert state.players[row['pid']].life == row['snapshot']['players'][str(row['pid'])]['life']
    assert canonical(_current_legacy_snapshot(row['snapshot'])) == before


def test_rank_materialization_and_profit_diagnostics_are_root_pure_and_private():
    result = rank_diagnostic()
    assert result['actual_root_scores'], 'Must record real existing ranker scores, not guessed constants'
    assert all(result['privacy'].values())
    path = Path(os.environ['MTG_HEAT_REPORT'])
    path.write_text(json.dumps(result, sort_keys=True, indent=2))


def test_original_natural_decision_must_not_spend_heat_to_kill_own_delver():
    row, state, decision, profit_calls = replay_receipt()
    candidate, delta = removal_delta(state, row['action'], row['action']['targets']['target_card_id'])
    assert delta < 0, 'This regression is limited to the demonstrated losing trade'
    path = Path(os.environ['MTG_HEAT_REPORT']).with_name('actual-replay.json')
    path.write_text(json.dumps({'actual_action': decision.action, 'reasoning': decision.reasoning,
                               'exact_checked_declaration_parity': complete_action(decision.action)
                               == complete_action(row['action']),
                               'sealed_action': row['action'], 'friendly_profit_calls': profit_calls,
                               'resolved_board_delta': delta,
                               'opponent_deluge_remains': [item.label for item in candidate.stack]},
                              sort_keys=True, indent=2))
    assert not (decision.action.get('card_id') == row['action']['card_id']
                and decision.action.get('targets', {}).get('target_card_id')
                == row['action']['targets']['target_card_id']), decision


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('window', ['response', 'proactive'])
@pytest.mark.parametrize('style', ['Tempo', 'Aristocrats'])
@pytest.mark.parametrize('payoff', ['Bastion of Remembrance', 'Blood Artist'])
def test_beneficial_friendly_burn_stays_legal_and_wins(seat, window, style, payoff):
    state, heat, victim = canonical_control(seat, window, payoff=payoff)
    before = canonical(serialize_match_snapshot(state))
    legal = RulesEngine().legal_moves(state, seat)
    view, private_legal = decision_view(state, seat, legal)
    assert all(private_cards(view, seat).values())
    ai = AIAgent(archetype=style, opponent_archetype='Control', difficulty='master')
    declared = {'type': 'cast_spell', 'card_id': heat, 'targets': {'target_card_id': victim}}
    assert friendly_destruction_profit(view, seat, declared,
        own_choice_action=lambda s, moves, pid: ai.choose_action(s, moves, pid).action) is True
    decision = ai.choose_action(state, legal, seat)
    move = next(move for move in private_legal if move.get('card_id') == heat)
    materialized = ai._materialize_action(view, {**move, 'targets': declared['targets']}, seat)
    assert materialized.get('targets', {}).get('target_card_id') == victim
    assert not materialized.get('_invalid_ai_choice'), materialized
    assert canonical(serialize_match_snapshot(state)) == before
    candidate = checked_action(state, RulesEngine(), seat, materialized)
    candidate = advance_until(candidate, lambda s: s.winner is not None, ai)
    assert candidate.winner == seat
    with Path(os.environ['MTG_HEAT_REPORT']).with_name('beneficial-controls.jsonl').open('a') as log:
        log.write(json.dumps({'seat': seat, 'window': window, 'style': style, 'payoff': payoff,
                              'actual_choice': decision.action, 'reasoning': decision.reasoning,
                              'materialized_beneficial_action': materialized,
                              'checked_winner': candidate.winner}, sort_keys=True) + '\n')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('window', ['response', 'proactive'])
def test_opponent_removal_materializes_opponent_and_resolves_exact_damage(seat, window):
    state, heat, victim = canonical_control(seat, window, opponent_target=True)
    before = canonical(serialize_match_snapshot(state))
    legal = RulesEngine().legal_moves(state, seat)
    move = next(move for move in legal if move.get('card_id') == heat)
    view, moves = decision_view(state, seat, [move])
    ai = AIAgent(archetype='Tempo', opponent_archetype='Control', difficulty='master')
    action = ai._materialize_action(view, moves[0], seat)
    assert action.get('targets', {}).get('target_card_id') == victim
    assert not action.get('_invalid_ai_choice')
    candidate, delta = removal_delta(state, action, victim)
    assert candidate.cards[victim].zone == Zone.GRAVEYARD
    assert delta > 0
    assert canonical(serialize_match_snapshot(state)) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('window', ['response', 'proactive'])
def test_response_and_proactive_boundaries_record_actual_decision_and_known_loss(seat, window):
    state, heat, victim = canonical_control(seat, window)
    before = canonical(serialize_match_snapshot(state))
    legal = RulesEngine().legal_moves(state, seat)
    view, moves = decision_view(state, seat, legal)
    assert all(private_cards(view, seat).values())
    ai = AIAgent(archetype='Tempo', opponent_archetype='Control', difficulty='master')
    with patch.object(pending_effects, 'friendly_destruction_profit',
                      wraps=pending_effects.friendly_destruction_profit) as profit:
        decision = ai.choose_action(state, legal, seat)
        profit_calls = profit.call_count
    declared = {'type': 'cast_spell', 'card_id': heat, 'targets': {'target_card_id': victim}}
    candidate, delta = removal_delta(state, declared, victim)
    assert delta < 0
    assert candidate.cards[victim].zone == Zone.GRAVEYARD
    assert canonical(serialize_match_snapshot(state)) == before
    with Path(os.environ['MTG_HEAT_REPORT']).with_name('window-boundaries.jsonl').open('a') as log:
        log.write(json.dumps({'seat': seat, 'window': window, 'actual_action': decision.action,
                              'reasoning': decision.reasoning, 'declared_trade_delta': delta,
                              'actual_friendly_profit_calls': profit_calls,
                              'forced_response': ai._forced_stack_interaction(view, moves, seat),
                              'friendly_profit': friendly_destruction_profit(view, seat, declared)},
                             sort_keys=True) + '\n')
