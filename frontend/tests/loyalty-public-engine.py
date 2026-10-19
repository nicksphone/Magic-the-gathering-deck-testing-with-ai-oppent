"""Actual paid loyalty views; forbid database, socket and child creation."""
import sys
from pathlib import Path


def deny(event, _args):
    if event.startswith(('sqlite3.', 'socket.')) or event in {
            'subprocess.Popen', 'os.system', 'os.fork', 'os.forkpty', 'os.posix_spawn'}:
        raise AssertionError('Pure loyalty fixture denied ' + event)


sys.addaudithook(deny)
root = Path(__file__).resolve().parents[2]
for relative in ('backend', 'audit/complete-body/delta', 'audit/complete-body/gap6',
                 'audit/complete-body/tests', 'audit/gate2-domain-compiler',
                 'audit/gate2-suncleanser'):
    sys.path.insert(0, str(root / relative))
import os
import json
from copy import deepcopy
os.environ.setdefault('GAP6_EVIDENCE', str(root))
os.environ.setdefault('ADMISSION_PHASE', 'loyalty-public-ui')
import test_paid_context_goldens as paid
from game_state.state import Zone
from game_state.serializers import serialize_match

seed = json.loads((root / 'backend/card_data/builtin_oracle_seed.json').read_bytes())['cards']
auras = {row['name']: row for row in json.loads(
    (root / 'backend/tests/fixtures/aura_costs.json').read_bytes())}
from tests.test_counter_replacements import ROWS as counters
from tests.test_counter_prohibitions import ROWS as prohibitions
fixture = paid.facts.__wrapped__()
base = next(fixture)
rows = deepcopy(base)
rows.update(deepcopy(seed))
rows.update(deepcopy(auras))
rows.update(deepcopy(counters))
rows.update(deepcopy(prohibitions))


def view(state, seat, kind):
    state = paid.cold(state)
    public = serialize_match(state, look_players={seat})
    public.update(controllers={'1': 'human', '2': 'human'}, revision=0, mode='human_vs_human')
    return {'seat': seat, 'kind': kind, 'state': public,
            'legal': {'player_id': seat, 'revision': 0, 'moves': paid.offers(state, seat)}}


result = []


def position(seat):
    state = paid.g.position(rows, seat)
    for player in state.players.values():
        player.mana_pool = {color: 0 for color in 'WUBRGC'}
    return state


for seat in (1, 2):
    state = position(seat)
    paid.g.add(state, rows, 'Doubling Season', seat)
    target = paid.g.add(state, rows, 'Colossal Dreadmaw', 3-seat)
    selected = [paid.g.add(state, rows, name, seat, Zone.HAND) for name in
                ('Octopus Umbra', 'Breeding Pool', "Jetmir's Garden", 'Teferi, Hero of Dominaria')]
    source = paid.g.add(state, rows, 'Ugin, the Spirit Dragon', seat, Zone.HAND)
    state, _ = paid.paid(state, seat, source, {'C': 8})
    state = paid.advance(state, lambda current: not current.stack)
    assert state.cards[source].loyalty == 14
    state = paid.priority(state, seat)
    state = paid.act(state, seat, {'type': 'activate_loyalty', 'card_id': source,
                                  'ability_index': 2, 'targets': {}})
    state = paid.advance(state, lambda current: current.pending_mechanic_choice is not None)
    assert state.pending_mechanic_choice['kind'] == 'loyalty_cards'
    result.append(view(state, seat, 'loyalty_cards'))
    state = paid.act(state, seat, {'type': 'choose_mechanic', 'card_ids': selected})
    assert state.pending_mechanic_choice['kind'] == 'loyalty_attachment'
    assert target in state.pending_mechanic_choice['options']
    result.append(view(state, seat, 'loyalty_attachment'))

    state = position(seat)
    paid.g.add(state, rows, 'Doubling Season', seat)
    source = paid.g.add(state, rows, 'Elspeth, Sun\'s Champion', seat, Zone.HAND)
    state, _ = paid.paid(state, seat, source, {'W': 2, 'C': 4})
    state = paid.advance(state, lambda current: not current.stack)
    state = paid.priority(state, seat)
    state = paid.act(state, seat, {'type': 'activate_loyalty', 'card_id': source,
                                  'ability_index': 2, 'targets': {}})
    state = paid.advance(state, lambda current: not current.stack)
    assert state.emblems and state.cards[state.emblems[-1]].zone == Zone.COMMAND
    result.append(view(state, seat, 'emblem'))

try:
    next(fixture)
except StopIteration:
    pass
else:
    raise AssertionError('Canonical fixture yielded more than once')
print(json.dumps(result))
