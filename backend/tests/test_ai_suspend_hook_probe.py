"""Opt-in production probe requires the separately reviewed agent hook proposal."""
import os
import json
import subprocess
import sys

import pytest

from ai.action_contract import complete_action
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from tests.test_ai_suspend_policy import agent, moves
from tests.test_suspend_lifecycle import setup, ready, restore, act, CARDS, add

pytestmark = pytest.mark.skipif(os.environ.get('MTG_SUSPEND_HOOK_PROBE') != '1',
                              reason='Separate parent-owned agent hook is not applied')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Rift Bolt', 'Errant Ephemeron', 'Ancestral Vision'])
def test_actual_agent_hand_and_last_counter(seat, name):
    state, cid = setup(seat, name)
    state.turn = 1
    state.players[seat].mana_pool = {'R': 1} if name == 'Rift Bolt' else {'U': 1, 'C': 1}
    before = serialize_match_snapshot(state)
    action = complete_action(agent().choose_action(state, moves(state, seat), seat).action)
    assert action == {'type': 'suspend', 'card_id': cid}
    assert serialize_match_snapshot(state) == before
    state = ready(state, seat, cid)
    before = serialize_match_snapshot(state)
    action = complete_action(agent().choose_action(state, moves(state, seat), seat).action)
    assert action['type'] == 'cast_spell' and action['card_id'] == cid
    assert action == complete_action(agent().choose_action(restore(state), moves(state, seat), seat).action)
    result = act(state, seat, action)
    assert not result.pending_mechanic_choice
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_agent_required_decline_not_pass_loop(seat):
    state, cid = setup(seat)
    state = ready(state, seat, cid)
    for owner in [1, 2]: add(state, 'Ivory Mask', owner, cards=CARDS)
    action = complete_action(agent().choose_action(state, moves(state, seat), seat).action)
    assert action == {'type': 'choose_mechanic', 'card_ids': ['decline']}
    assert not act(state, seat, action).pending_mechanic_choice


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_agent_normal_deployment_not_displaced(seat):
    state, cid = setup(seat, 'Errant Ephemeron')
    state.turn = 1
    state.players[seat].mana_pool = {'U': 1, 'C': 6}
    action = complete_action(agent().choose_action(state, moves(state, seat), seat).action)
    assert action['type'] == 'cast_spell' and action['card_id'] == cid
    act(state, seat, action)


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_agent_fresh_process_snapshot_replay(seat):
    state, cid = setup(seat)
    state = ready(state, seat, cid)
    snapshot = serialize_match_snapshot(state)
    expected = complete_action(agent().choose_action(state, moves(state, seat), seat).action)
    script = '''
import json, sys
from ai.agent import AIAgent
from ai.action_contract import complete_action
from game_state.serializers import deserialize_match_snapshot
from rules_engine.engine import RulesEngine
s = deserialize_match_snapshot(json.load(sys.stdin))
p = s.pending_mechanic_choice['player_id']
a = AIAgent('strong', 'Midrange', 'Aggro')
print(json.dumps(complete_action(a.choose_action(s, RulesEngine().legal_moves(s, p), p).action)))
'''
    result = subprocess.run([sys.executable, '-c', script], input=json.dumps(snapshot),
                            text=True, capture_output=True, check=True, timeout=30)
    assert json.loads(result.stdout) == expected
    assert serialize_match_snapshot(state) == snapshot
