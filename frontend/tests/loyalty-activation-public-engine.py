"""Canonical paid loyalty announcements and replay of actual UI callback bodies."""
import sys
from pathlib import Path


def deny(event, _args):
    if event.startswith(('sqlite3.', 'socket.')) or event in {
            'subprocess.Popen', 'os.system', 'os.fork', 'os.forkpty', 'os.posix_spawn'}:
        raise AssertionError('Pure loyalty activation fixture denied ' + event)


sys.addaudithook(deny)
root = Path(__file__).resolve().parents[2]
for relative in ('backend', 'audit/complete-body/gap6', 'audit/gate2-domain-compiler',
                 'audit/gate2-suncleanser'):
    sys.path.insert(0, str(root / relative))
import json
import os
from copy import deepcopy
os.environ.setdefault('GAP6_EVIDENCE', str(root))
os.environ.setdefault('ADMISSION_PHASE', 'loyalty-activation-ui')
import test_paid_context_goldens as paid
from game_state.state import Zone
from game_state.serializers import serialize_match, deserialize_match_snapshot
from rules_engine.continuous import effective_types, has_keyword
from rules_engine.action_validation import ActionRejected


def fixtures():
    fixture = paid.facts.__wrapped__()
    base = next(fixture)
    rows = deepcopy(base)
    rows.update(json.loads((root / 'backend/card_data/builtin_oracle_seed.json').read_bytes())['cards'])
    result = []
    cases = (
        ('ugin-zero', 'Ugin, the Spirit Dragon', 1, {'x_value': 0}),
        ('ugin-two', 'Ugin, the Spirit Dragon', 1, {'x_value': 2}),
        ('ugin-all', 'Ugin, the Spirit Dragon', 1, 'all'),
        ('ugin-player', 'Ugin, the Spirit Dragon', 0, 'player'),
        ('ugin-creature', 'Ugin, the Spirit Dragon', 0, 'creature'),
        ('nissa-land', 'Nissa, Who Shakes the World', 0, 'land'),
        ('nissa-decline', 'Nissa, Who Shakes the World', 0, {}),
        ('teferi-enchantment', 'Teferi, Hero of Dominaria', 1, 'enchantment'),
        ('teferi-creature', 'Teferi, Hero of Dominaria', 1, 'creature'),
        ('teferi-walker', 'Teferi, Hero of Dominaria', 1, 'walker'),
    )
    for seat in (1, 2):
        for kind, name, index, choice in cases:
            state = paid.g.position(rows, seat)
            for player in state.players.values():
                player.mana_pool = {color: 0 for color in 'WUBRGC'}
                player.snow_mana_pool = {color: 0 for color in 'WUBRGC'}
            land = paid.g.add(state, rows, 'Forest', seat)
            state.cards[land].tapped = True
            creature = paid.g.add(state, rows, 'Suncleanser', 3-seat)
            enchantment = paid.g.add(state, rows, 'Leyline Binding', 3-seat)
            walker = paid.g.add(state, rows, 'Nissa, Who Shakes the World', 3-seat)
            source = paid.g.add(state, rows, name, seat, Zone.HAND)
            pool = {'C': 8} if name.startswith('Ugin') else {'G': 2, 'C': 3} if name.startswith('Nissa') else {'W': 1, 'U': 1, 'C': 3}
            state, _ = paid.paid(state, seat, source, pool)
            state = paid.advance(state, lambda current: not current.stack)
            state = paid.priority(paid.cold(state), seat)
            assert state.cards[source].zone == Zone.BATTLEFIELD
            legal = paid.offers(state, seat)
            move = next(move for move in legal if move['type'] == 'activate_loyalty'
                        and move['card_id'] == source and move['ability_index'] == index)
            ids = {'land': land, 'creature': creature, 'enchantment': enchantment, 'walker': walker}
            targets = {'x_value': state.cards[source].loyalty} if choice == 'all' else {
                'target_player': 3-seat} if choice == 'player' else {
                'target_card_id': ids[choice]} if isinstance(choice, str) else choice
            public = serialize_match(state, look_players={seat})
            public.update(controllers={'1': 'human', '2': 'human'}, revision=0, mode='human_vs_human')
            result.append({'id': f'{kind}-seat{seat}', 'kind': kind, 'seat': seat,
                'source': source, 'ids': ids, 'abilityIndex': index, 'state': public,
                'legal': {'player_id': seat, 'revision': 0, 'moves': legal},
                'snapshot': paid.snapshot(state), 'loyalty': state.cards[source].loyalty,
                'expected': {'type': 'activate_loyalty', 'card_id': source,
                             'ability_index': index, 'targets': targets},
                'canonicalOracle': rows[name]['oracle_text'], 'publicMove': move})
    try:
        next(fixture)
    except StopIteration:
        pass
    else:
        raise AssertionError('Canonical fixture yielded more than once')
    return result


def verify(rows, submissions):
    assert len(rows) == len(submissions) == 20
    checks = []
    for row, submitted in zip(rows, submissions):
        assert submitted == {'id': row['id'], 'seat': row['seat'], 'action': row['expected']}
        state = deserialize_match_snapshot(row['snapshot'])
        seat, source, kind = row['seat'], row['source'], row['kind']
        if kind.startswith('ugin-') and row['abilityIndex'] == 1:
            invalid = deepcopy(row['expected'])
            invalid['targets']['x_value'] = row['loyalty'] + 1
            before = paid.snapshot(state)
            try:
                paid.act(state, seat, invalid)
            except ActionRejected:
                pass
            else:
                raise AssertionError('Insufficient loyalty must reject')
            assert paid.snapshot(state) == before
        state = paid.act(state, seat, submitted['action'])
        state = paid.advance(paid.cold(state), lambda current: not current.stack)
        state = paid.cold(state)
        ids = row['ids']
        if row['abilityIndex'] == 1 and kind.startswith('ugin-'):
            x = submitted['action']['targets']['x_value']
            assert state.cards[ids['creature']].zone == (Zone.EXILE if x >= 2 else Zone.BATTLEFIELD)
            assert state.cards[ids['land']].zone == Zone.BATTLEFIELD
            assert state.cards[source].zone == (Zone.GRAVEYARD if x == row['loyalty'] else Zone.BATTLEFIELD)
            if x < row['loyalty']:
                assert state.cards[source].loyalty == row['loyalty'] - x
        elif kind == 'ugin-player':
            assert state.players[3-seat].life == 17
        elif kind == 'ugin-creature':
            card = state.cards[ids['creature']]
            assert card.zone == Zone.BATTLEFIELD
            assert card.counters.get('__damage_marked', 0) == 3
        elif kind == 'nissa-land':
            card = state.cards[ids['land']]
            assert 'Creature' in effective_types(state, card) and not card.tapped
            assert card.counters.get('+1/+1', 0) == 3
            assert has_keyword(state, ids['land'], 'vigilance') and has_keyword(state, ids['land'], 'haste')
        elif kind == 'nissa-decline':
            card = state.cards[ids['land']]
            assert 'Creature' not in effective_types(state, card) and card.tapped
            assert card.counters.get('+1/+1', 0) == 0
        else:
            target = submitted['action']['targets']['target_card_id']
            assert state.cards[target].zone == Zone.LIBRARY
            assert state.players[3-seat].library[-3] == target
        checks.append({'id': row['id'], 'actualCallback': submitted,
                       'outputSnapshot': paid.snapshot(state), 'passed': True})
    return checks


if __name__ == '__main__':
    if sys.argv[1:] == ['--verify']:
        packet = json.load(sys.stdin)
        print(json.dumps(verify(packet['rows'], packet['submissions'])))
    else:
        assert len(sys.argv) == 1
        print(json.dumps(fixtures()))
