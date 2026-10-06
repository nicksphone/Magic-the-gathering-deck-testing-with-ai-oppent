"""Explicit synthetic ordinary positions; never repair a queued runtime snapshot."""
from rules_engine.turn_scheduler import NORMAL_PHASES, PHASE_STEPS


def ordinary_position(state):
    assert not state.extra_turns, 'Cannot reposition a queued extra turn'
    assert all(row['group'] == 0 for row in state.phase_plan), 'Cannot reposition extra phases'
    if state.phase_plan:
        assert tuple(row['kind'] for row in state.phase_plan) == NORMAL_PHASES
        state.phase_cursor = next(i for i, row in enumerate(state.phase_plan)
                                  if state.step in PHASE_STEPS[row['kind']])
        state.normal_turn_successor = 3 - state.active_player
