"""Existing private reorder continuation retains independently resolved schedules."""
from copy import deepcopy
import pickle

import pytest

from ai.information import decision_view, is_unknown
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests.queued_sequence_support import add
from tests.test_library_reorder import setup, restore


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Index', 'Ponder'])
@pytest.mark.parametrize('family', ['turn', 'combat_main'])
def test_private_reorder_resume_preserves_resolved_queue(seat, name, family):
    state, source = setup(name, seat)
    state.players[seat].mana_pool = {'U': 20, 'R': 20, 'C': 20}
    if family == 'turn':
        scheduler = add(state, 'Time Warp', seat)
        action = {'type': 'cast_spell', 'card_id': scheduler.id,
                  'targets': {'target_player': 3 - seat}}
    else:
        scheduler = add(state, 'Aggravated Assault', seat, Zone.BATTLEFIELD)
        action = {'type': 'activate_ability', 'card_id': scheduler.id, 'ability_index': 0}
    original = pickle.dumps(state)
    root = state
    state = checked_action(state, RulesEngine(), seat, action)
    assert pickle.dumps(root) == original
    assert resolve_top_of_stack(state)
    schedule = deepcopy(serialize_match_snapshot(state)['scheduler'])
    assert state.extra_turns if family == 'turn' else any(row['group'] for row in state.phase_plan)
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'cast_spell', 'card_id': source.id, 'targets': {}})
    assert not resolve_top_of_stack(state)
    assert serialize_match_snapshot(state)['scheduler'] == schedule
    inspected = list(state.pending_mechanic_choice['options'])
    before = pickle.dumps(state)
    own, _ = decision_view(state, seat, RulesEngine().legal_moves(state, seat))
    other, _ = decision_view(state, 3 - seat, [])
    assert all(not is_unknown(own.cards[cid]) and is_unknown(other.cards[cid]) for cid in inspected)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 3 - seat,
                       {'type': 'choose_mechanic', 'card_ids': inspected})
    assert pickle.dumps(state) == before
    state = restore(state)
    order = list(reversed(inspected))
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'choose_mechanic', 'card_ids': order})
    if name == 'Ponder':
        assert state.pending_mechanic_choice['kind'] == 'library_shuffle'
        state = restore(state)
        state = checked_action(state, RulesEngine(), seat,
                               {'type': 'choose_mechanic', 'card_ids': ['keep']})
        assert state.players[seat].hand == [order[0]]
    else:
        assert not state.players[seat].hand
    assert state.pending_mechanic_choice is None
    assert state.cards[source.id].zone == Zone.GRAVEYARD
    assert serialize_match_snapshot(restore(state))['scheduler'] == schedule
