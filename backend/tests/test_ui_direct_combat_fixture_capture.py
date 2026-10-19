"""Exact route-body projection; real serializer/actions, not HTTP/SQL/browser proof."""
import ast
from pathlib import Path

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot, serialize_match
from game_state.state import Step
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from tests import test_attack_bands as bands


def projected_direct_combat():
    path = Path(__file__).resolve().parents[2] / 'frontend/tests/ui_fixture_server.py'
    tree = ast.parse(path.read_text())
    route = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name == 'direct_combat')
    # Only registration is omitted: importing the server would initialize SQL.
    route.decorator_list = []
    def publish(state, deck):
        assert deck == [{'quantity': 60, 'card_name': 'Island'}]
        serialize_match_snapshot(state)  # Actual publication calls this before persisting.
        return state
    namespace = {'publish': publish}
    exec(compile(ast.Module(body=[route], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace['direct_combat']


@pytest.mark.parametrize('seat', [1, 2])
def test_both_seat_fixture_snapshot_roundtrip_and_unknown_capture(seat):
    state = projected_direct_combat()(seat)
    assert state.active_player == state.priority_player == seat
    assert all(state.cards[cid].owner == state.cards[cid].controller == seat
               for cid in ['hero', 'angel', 'elf'])
    assert state.cards['bears'].owner == state.cards['bears'].controller == 3-seat
    assert state.card_observations == {}  # The original synthetic producer has no public history.
    assert state.sideboard_facts == {} if seat == 2 else state.sideboard_facts['complete'] is False
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert serialize_match_snapshot(restored) == serialize_match_snapshot(state)
    assert 'sideboard_facts' not in serialize_match(restored)


@pytest.mark.parametrize('seat', [1, 2])
def test_checked_band_and_remote_seat_block_survive_snapshot(seat):
    state = projected_direct_combat()(seat)
    rules = RulesEngine()
    state = checked_action(state, rules, seat, {'type': 'attack',
        'attackers': ['hero', 'angel'], 'bands': [['hero', 'angel']]})
    assert state.attackers == ['hero', 'angel'] and state.attack_bands == [['hero', 'angel']]
    for _ in range(4):
        if state.step == Step.DECLARE_BLOCKERS:
            break
        state = checked_action(state, rules, state.priority_player, {'type': 'pass_priority'})
    assert state.step == Step.DECLARE_BLOCKERS
    move = next(move for move in rules.legal_moves(state, 3-seat) if move['type'] == 'block')
    assert move['legal_blocks']['bears'] == ['hero']  # Flying rejects direct angel assignment.
    state = checked_action(state, rules, 3-seat, {'type': 'block', 'blocks': {'hero': ['bears']}})
    assert state.blocks == {'hero': ['bears'], 'angel': ['bears']}
    replay = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert replay.blocks == state.blocks and replay.attack_bands == state.attack_bands


@pytest.mark.parametrize('seat', [1, 2])
def test_invalid_band_replay_stays_atomic(seat):
    state = projected_direct_combat()(seat)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'attack',
            'attackers': ['angel', 'elf'], 'bands': [['angel', 'elf']]})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_stale_original_inventory_owner_is_still_rejected(seat):
    state = bands._state()
    cid = state.players[seat].hand[0]
    state.cards[cid].owner = 3-seat  # Deliberate invalid binding, not a real game action.
    with pytest.raises(ValueError, match='Invalid sideboard inventory binding'):
        serialize_match_snapshot(state)
