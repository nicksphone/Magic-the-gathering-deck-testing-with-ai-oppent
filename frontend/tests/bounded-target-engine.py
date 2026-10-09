"""Real canonical public views and execution of component-submitted actions."""
import json
import os
from pathlib import Path
import sys


def deny(event, _args):
    if event.startswith(('sqlite3.', 'socket.')) or event in {
            'subprocess.Popen', 'os.system', 'os.fork', 'os.forkpty', 'os.posix_spawn'}:
        raise AssertionError('Pure bounded-target fixture denied ' + event)


sys.addaudithook(deny)
root = Path(__file__).resolve().parents[2]
for relative in ('backend', 'audit/bounded-spells', 'audit/gate2-domain-compiler'):
    sys.path.insert(0, str(root / relative))
os.environ.setdefault('GAP6_EVIDENCE', str(root.parent / 'evidence'))
from game_state.serializers import (serialize_match, serialize_match_snapshot,
                                    deserialize_match_snapshot)
from game_state.state import Zone
from rules_engine.engine import RulesEngine
import test_paid_preflight as original
import domain_paid_support as paid

if len(sys.argv) > 1 and sys.argv[1] == 'execute':
    results = []
    for packet in json.load(sys.stdin):
        state = deserialize_match_snapshot(packet['snapshot'])
        action = packet['action']
        try:
            state = paid.act(state, packet['seat'], action['type'], **{
                key: value for key, value in action.items() if key != 'type'})
        except Exception as error:
            raise AssertionError({'submitted_action': action}) from error
        assert sum(state.players[packet['seat']].mana_pool.values()) == 0
        assert state.cards[action['card_id']].zone == Zone.STACK
        state = paid.resolve(paid.restore(state))
        selected = action['targets'].get('target_card_ids', [])
        assert state.cards[action['card_id']].zone == Zone.GRAVEYARD
        assert all(state.cards[cid].zone == (
            Zone.GRAVEYARD if cid in selected else Zone.BATTLEFIELD)
            for cid in packet['offered'])
        results.append({'seat': packet['seat'], 'selected': selected, 'resolved': True})
    print(json.dumps(results))
else:
    facts = original.facts.__wrapped__()
    rows = []
    for seat in (1, 2):
        state, source, _, _, _ = original.setup(facts, seat, 'Force of Vigor')
        paid.add(state, facts, "Witch's Oven", seat)
        for player in state.players.values():
            player.mana_pool = {color: player.mana_pool.get(color, 0) for color in 'WUBRGC'}
        public = serialize_match(state, look_players={seat})
        public.update(controllers={'1': 'human', '2': 'human'}, revision=0,
                      mode='human_vs_human')
        moves = RulesEngine().legal_moves(state, seat)
        move = next(move for move in moves if move['type'] == 'cast_spell'
                    and move['card_id'] == source)
        assert move['target_hints']['up_to_target_count'] == 2
        rows.append({'seat': seat, 'source': source, 'state': public,
                     'snapshot': serialize_match_snapshot(state),
                     'legal': {'player_id': seat, 'revision': 0, 'moves': moves}})
    print(json.dumps(rows))
