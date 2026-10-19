"""Fixture positioning is scoped to unqueued ordinary plans, not execution."""
import pickle

import pytest

from game_state.state import Step
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.turn_scheduler import ensure_plan
from tests.queued_sequence_support import position, cast, resume
from tests.scheduler_fixture_position import ordinary_position


@pytest.mark.parametrize('seat', [1, 2])
def test_fixture_position_preserves_gameplay_and_remains_restorable(seat):
    state = position(seat)
    ensure_plan(state)
    state.step = Step.DECLARE_BLOCKERS
    state.active_player = 3 - seat
    before = {k: pickle.dumps(v) for k, v in vars(state).items()
              if k not in {'phase_cursor', 'normal_turn_successor'}}
    ordinary_position(state)
    assert before == {k: pickle.dumps(v) for k, v in vars(state).items() if k in before}
    restored = resume(state)
    assert restored.step == Step.DECLARE_BLOCKERS
    assert restored.normal_turn_successor == seat


@pytest.mark.parametrize('seat', [1, 2])
def test_fixture_adapter_cannot_erase_real_extra_turn(seat):
    state, _ = cast(position(seat), 'Time Warp', seat, {'target_player': seat})
    assert resolve_top_of_stack(state)
    before = pickle.dumps(state)
    with pytest.raises(AssertionError, match='queued extra turn'):
        ordinary_position(state)
    assert pickle.dumps(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_fixture_adapter_cannot_erase_real_extra_phase_group(seat):
    from game_state.state import Zone
    from tests.queued_sequence_support import add, act
    state = position(seat)
    source = add(state, 'Aggravated Assault', seat, Zone.BATTLEFIELD)
    state = act(state, seat, {'type': 'activate_ability', 'card_id': source.id, 'ability_index': 0})
    assert resolve_top_of_stack(state)
    before = pickle.dumps(state)
    with pytest.raises(AssertionError, match='extra phases'):
        ordinary_position(state)
    assert pickle.dumps(state) == before
