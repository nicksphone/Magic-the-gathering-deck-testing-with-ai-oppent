"""Replay the actual browser payload in an isolated in-memory engine; no DB/API."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))
from tests.test_attack_bands import _state
from game_state.state import CardInstance, Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine

payload = json.loads(sys.argv[1])
seat = payload['player_id']
state = _state()
state.active_player = state.priority_player = seat
for player in state.players.values():
    player.battlefield.clear()
for cid, tapped, sick in [('hero', False, False), ('bear', False, False), ('tapped', True, False), ('sick', False, True)]:
    state.cards[cid] = CardInstance(id=cid, name=cid, owner=seat, controller=seat, zone=Zone.BATTLEFIELD,
                                   types=['Creature'], power=2, toughness=2, tapped=tapped, summoning_sick=sick)
    state.players[seat].battlefield.append(cid)
rules = RulesEngine()
attack = next(move for move in rules.legal_moves(state, seat) if move['type'] == 'attack')
assert attack['options'] == ['hero', 'bear'], attack
state = checked_action(state, rules, seat, payload['action'])
assert state.attackers_declared
assert state.attackers == ['hero', 'bear']
assert state.cards['hero'].tapped and state.cards['bear'].tapped
assert state.cards['tapped'].tapped and not state.cards['sick'].tapped
assert all(state.attack_targets[cid] == f'player:{3-seat}' for cid in state.attackers)
print(f'PASS engine replay seat {seat}: browser payload accepted; declared={state.attackers_declared}; attackers={state.attackers}; eligible tapped; sick excluded; targets={state.attack_targets}')
