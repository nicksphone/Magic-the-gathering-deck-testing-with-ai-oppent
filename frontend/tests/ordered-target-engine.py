"""Canonical public target offers and checked execution of UI announcements."""
import sys
from pathlib import Path


def deny(event, _args):
    if event.startswith(('sqlite3.', 'socket.')) or event in {
            'subprocess.Popen', 'os.system', 'os.fork', 'os.forkpty', 'os.posix_spawn'}:
        raise AssertionError('Pure ordered-target fixture denied ' + event)


sys.addaudithook(deny)
root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / 'backend'))
import json
from game_state.serializers import serialize_match, serialize_match_snapshot, deserialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.continuous import effective_combat_stats
from tests.test_multi_target_immediate_return import case, resolve, canonical, raw_card
from tests.test_ordered_creature_modifiers import position


if len(sys.argv) > 1 and sys.argv[1] == 'execute':
    results = []
    for packet in json.load(sys.stdin):
        state = deserialize_match_snapshot(packet['snapshot'])
        ids = packet['action']['targets']['target_card_ids']
        seqs = {cid: state.cards[cid].zone_change_sequence for cid in packet['offered']}
        stats = {cid: effective_combat_stats(state, cid) for cid in set(ids)}
        state = checked_action(state, RulesEngine(), packet['seat'], packet['action'])
        assert state.cards[packet['action']['card_id']].zone == Zone.STACK
        assert sum(state.players[packet['seat']].mana_pool.values()) == 0
        public = serialize_match(state, look_players={packet['seat']})
        assert public['stack'][0]['targets'] == ids
        state = deserialize_match_snapshot(serialize_match_snapshot(state))
        state = resolve(state)
        assert state.cards[packet['action']['card_id']].zone == Zone.GRAVEYARD
        if packet['kind'] == 'ghostly':
            for cid in packet['offered']:
                assert state.cards[cid].zone == Zone.BATTLEFIELD
                assert state.cards[cid].zone_change_sequence == seqs[cid] + 2 * (cid in ids)
                assert state.cards[cid].controller == packet['seat']
                assert state.cards[cid].owner == packet['owners'][cid]
            if packet['creature'] in ids:
                assert state.cards[packet['creature']].counters['+1/+1'] == 2
        else:
            for cid, (power, toughness) in stats.items():
                assert effective_combat_stats(state, cid) == (
                    power - 3 * (cid == ids[0]), toughness - 3 * (cid == ids[1]))
        saved = serialize_match_snapshot(state)
        assert serialize_match_snapshot(deserialize_match_snapshot(saved)) == saved
        results.append({'seat': packet['seat'], 'selected': ids, 'resolved': True})
    print(json.dumps(results))
else:
    rows = []
    for seat in (1, 2):
        for foreign in (False, True):
            state, targets, spell = case(seat, foreign)
            artifact = raw_card(state, canonical('creature_observer_fix/sol-ring.json'), seat, Zone.BATTLEFIELD)
            if foreign:
                artifact.owner = 3 - seat
            rows.append((state, seat, spell, 'ghostly', targets + [artifact.id], targets[0]))
        state, spell, first, second = position(seat)
        rows.append((state, seat, spell, 'agony', [first, second], first))
    public_rows = []
    for state, seat, spell, kind, offered, creature in rows:
        for player in state.players.values():
            player.mana_pool = {color: player.mana_pool.get(color, 0) for color in 'WUBRGC'}
        moves = RulesEngine().legal_moves(state, seat)
        move = next(move for move in moves if move['type'] == 'cast_spell' and move['card_id'] == spell)
        hints = move['target_hints']
        if kind == 'ghostly':
            assert hints['required_distinct_target_count'] == 2
            assert not hints.get('creature_targets')
            assert {row['id'] for row in hints['permanent_targets']} == set(offered)
        else:
            assert hints['required_target_instance_count'] == 2
            assert {row['id'] for row in hints['creature_targets']} == set(offered)
        public = serialize_match(state, look_players={seat})
        public.update(controllers={'1': 'human', '2': 'human'}, revision=0, mode='human_vs_human')
        public_rows.append({'state': public, 'seat': seat, 'source': spell, 'kind': kind,
                            'snapshot': serialize_match_snapshot(state), 'offered': offered,
                            'creature': creature, 'owners': {cid: state.cards[cid].owner for cid in offered},
                            'legal': {'player_id': seat, 'revision': 0, 'moves': moves}})
    print(json.dumps(public_rows))
