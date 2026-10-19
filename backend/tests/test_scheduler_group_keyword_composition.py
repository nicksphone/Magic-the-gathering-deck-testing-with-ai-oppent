"""Canonical temporary group grants persist across visits, not actual turns."""
import pickle

import pytest

from game_state.state import Step, Zone
from rules_engine.action_validation import checked_action
from rules_engine.continuous import has_keyword
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests.desired_extra_sequence_contracts import next_upkeep
from tests.queued_sequence_support import add, resume
from tests.test_permanent_keyword_grants import granted


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Boros Charm', 'Heroic Intervention'])
@pytest.mark.parametrize('family', ['turn', 'combat_main'])
def test_actual_schedule_keeps_grants_until_natural_cleanup(seat, name, family):
    state, _, allies, enemies = granted(seat, name)
    state.players[seat].mana_pool = {'U': 20, 'R': 20, 'C': 20}
    if family == 'turn':
        source = add(state, 'Time Warp', seat)
        action = {'type': 'cast_spell', 'card_id': source.id,
                  'targets': {'target_player': seat}}
    else:
        source = add(state, 'Aggravated Assault', seat, Zone.BATTLEFIELD)
        action = {'type': 'activate_ability', 'card_id': source.id, 'ability_index': 0}
        assert not has_keyword(state, source.id, 'indestructible')
    root = state
    before = pickle.dumps(root)
    state = checked_action(state, RulesEngine(), seat, action)
    assert pickle.dumps(root) == before
    while state.stack:
        assert resolve_top_of_stack(state)
    state = resume(state)
    assert all(has_keyword(state, cid, 'indestructible') for cid in allies)
    assert all(not has_keyword(state, cid, 'indestructible') for cid in enemies)
    if family == 'combat_main':
        group = next(row['group'] for row in state.phase_plan if row['group'])
        for step in (Step.BEGIN_COMBAT, Step.DECLARE_ATTACKERS, Step.DECLARE_BLOCKERS,
                     Step.COMBAT_DAMAGE, Step.END_COMBAT, Step.POSTCOMBAT_MAIN):
            RulesEngine().next_step(state)
            assert state.step == step and state.phase_plan[state.phase_cursor]['group'] == group
            assert all(has_keyword(state, cid, 'indestructible') for cid in allies)
        state = resume(state)
        assert state.spells_cast_this_turn[seat] == 1
    next_upkeep(state)
    assert state.active_player == (seat if family == 'turn' else 3 - seat)
    assert all(not has_keyword(state, cid, 'indestructible') for cid in allies)
    assert all(not has_keyword(state, cid, 'hexproof') for cid in allies)
