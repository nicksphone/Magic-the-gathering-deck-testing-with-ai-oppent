"""Fault-injected diagnostic transport, not fabricated card Oracle or games."""
import pytest

from ai.agent import AIAgent
from ai import damage_sequences
from rules_engine.engine import RulesEngine
from tests.test_ai_burn_sequences import CASES, _position

WARNING = 'Oracle effect not inferred: explicit synthetic diagnostic transport probe'


def plan(state, seat):
    agent = AIAgent(difficulty='master', archetype='Burn', opponent_archetype='Tribal')
    return damage_sequences.winning_damage_action(agent, state, RulesEngine().legal_moves(state, seat), seat)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('history', [0, 100])
@pytest.mark.parametrize('stage', ['cast', 'settlement'])
def test_new_unsupported_diagnostic_invalidates_winning_search(seat, history, stage, monkeypatch):
    state = _position(seat, CASES[0])
    state.log.extend(['Explicit diagnostic-history padding'] * history)
    assert plan(state, seat) is not None
    if stage == 'cast':
        original = damage_sequences.simulation_checked_action

        def execute(*args, **kwargs):
            result = original(*args, **kwargs)
            result.log.append(WARNING)
            return result

        monkeypatch.setattr(damage_sequences, 'simulation_checked_action', execute)
    else:
        original = damage_sequences.settled_public_position

        def settle(*args, **kwargs):
            result = original(*args, **kwargs)
            if result is not None:
                result.log.append(WARNING)
            return result

        monkeypatch.setattr(damage_sequences, 'settled_public_position', settle)
    assert plan(state, seat) is None


@pytest.mark.parametrize('seat', [1, 2])
def test_old_diagnostic_history_is_not_current_branch_evidence(seat):
    state = _position(seat, CASES[0])
    state.log.append(WARNING)
    assert plan(state, seat) is not None
