"""Ordinary combat fixtures must be restorable without weakening queued plans."""
from copy import deepcopy

import pytest

from game_state.state import Step
from rules_engine.turn_scheduler import PHASE_STEPS
from training.environment import TrainingEnvironment
from tests.scheduler_fixture_position import ordinary_position
from tests.test_training_combat_intent_audit import CASES, scenario


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind,family', CASES)
def test_declared_combat_fixture_has_exact_restorable_ordinary_visit(seat, kind, family):
    env, action, hint, _ = scenario(seat, kind, family)
    state = env._state
    assert state.step == (Step.DECLARE_ATTACKERS if kind == 'attack' else Step.DECLARE_BLOCKERS)
    assert state.phase_plan[state.phase_cursor]['kind'] == 'combat'
    assert state.step in PHASE_STEPS[state.phase_plan[state.phase_cursor]['kind']]
    assert state.normal_turn_successor == 3 - state.active_player
    original = env.snapshot()
    replay = TrainingEnvironment()
    replay.restore(original)
    assert replay.snapshot() == original
    assert replay.lookup_intent({**hint, **action}) == env.lookup(action)
    # A corrupt imported cursor must still reject, never repair at restore.
    bad = deepcopy(original['state'])
    bad['scheduler']['phase_cursor'] = next(
        i for i, row in enumerate(bad['scheduler']['phase_plan'])
        if row['kind'] == 'precombat_main')
    from game_state.serializers import deserialize_match_snapshot
    before = deepcopy(bad)
    with pytest.raises(ValueError, match='Invalid phase cursor'):
        deserialize_match_snapshot(bad)
    assert bad == before
    assert replay.snapshot() == original


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('queued', ['turn', 'phase'])
def test_ordinary_fixture_helper_cannot_reposition_queued_schedule(seat, queued):
    env, _, _, _ = scenario(seat, 'attack', 'ordinary')
    state = env._state
    if queued == 'turn':
        state.extra_turns.append({'recipient': 3 - seat, 'anchor_turn': state.turn,
                                 'ordinal': state.next_schedule_ordinal, 'source_card_id': None})
    else:
        state.phase_plan.append({'kind': 'combat', 'visit': state.next_phase_visit,
                                 'group': state.next_schedule_ordinal})
    before = env.snapshot()
    with pytest.raises(AssertionError, match='Cannot reposition'):
        ordinary_position(state)
    assert env.snapshot() == before
