"""Real paid legend and exchange continuations, native I/O denied before imports."""
import sys
from pathlib import Path

def deny(event, args):
    if event.startswith(('sqlite3.', 'socket.')) or event in ('subprocess.Popen', 'os.system', 'os.fork', 'os.posix_spawn'):
        raise AssertionError('pure keeper-energy fixture denied ' + event)
sys.addaudithook(deny)
root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / 'backend'))
from copy import deepcopy
import json
from game_state.state import MatchFactory, Zone, Step
from game_state.serializers import serialize_match, serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine

rules = RulesEngine()
legend = {r['name']: r for r in map(json.loads, (root / 'backend/tests/fixtures/legend_keeper_audit/canonical.jsonl').read_text().splitlines())}
exchange = json.loads((root / 'backend/tests/fixtures/counter_native_frames/canonical.json').read_bytes())

def position(seat):
    deck = [{'quantity': 60, 'card_name': 'Island'}]
    state = MatchFactory.from_decks(deck, deck, seed=782)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    state.mechanic_choice_players = state.trigger_order_choice_players = {1, 2}
    state.trigger_order_choice_required = True
    state.players[seat].mana_pool = {color: 20 for color in 'WUBRGC'}
    return state

def add(state, row, owner, zone):
    # Retain full raw Oracle/type/mana/keywords through the actual deck hydrator.
    sample = MatchFactory.from_decks([{**row, 'card_name': row['name'], 'quantity': 1}], [], seed=782)
    card = deepcopy(next(iter(sample.cards.values())))
    card.id = state.allocate_object_id()
    card.owner = card.controller = owner
    card.move_to_zone(zone)
    state.cards[card.id] = card
    getattr(state.players[owner], zone.value).append(card.id)
    return card.id

def cast(state, seat, cid):
    before = sum(state.players[seat].mana_pool.values())
    state = checked_action(state, rules, seat, {'type': 'cast_spell', 'card_id': cid})
    assert sum(state.players[seat].mana_pool.values()) < before
    assert any(item.source_card_id == cid for item in state.stack)
    for _ in range(20):
        if state.pending_mechanic_choice or state.pending_trigger_order or not state.stack:
            break
        state = checked_action(state, rules, state.priority_player, {'type': 'pass_priority'})
    else:
        raise AssertionError('Paid cast did not resolve or pause')
    return state

def reject(state, seat, action):
    before = serialize_match_snapshot(state)
    try:
        checked_action(state, rules, seat, action)
    except ActionRejected:
        pass
    else:
        raise AssertionError('Invalid continuation accepted')
    assert serialize_match_snapshot(state) == before

def row(state, seat):
    assert rules.legal_moves(state, 3-seat) == []
    moves = rules.legal_moves(state, seat)
    assert len(moves) == 1 and moves[0]['type'] == 'choose_mechanic'
    view = serialize_match(state, look_players={seat})
    view.update(controllers={'1': 'human', '2': 'human'}, revision=0, mode='human_vs_human')
    return {'seat': seat, 'state': view, 'legal': {'player_id': seat, 'revision': 0, 'moves': moves}}

rows = []
for seat in (1, 2):
    state = position(seat)
    old = add(state, legend['Isamaru, Hound of Konda'], seat, Zone.HAND)
    new = add(state, legend['Isamaru, Hound of Konda'], seat, Zone.HAND)
    state = cast(state, seat, old)
    assert state.cards[old].zone == Zone.BATTLEFIELD and not state.pending_mechanic_choice
    state = cast(state, seat, new)
    assert state.pending_mechanic_choice['kind'] == 'legend_keeper'
    assert set(state.pending_mechanic_choice['options']) == {old, new}
    rows.append(row(state, seat))
    reject(state, 3-seat, {'type': 'choose_mechanic', 'card_ids': [new]})
    for ids in ([], [new, new], ['unknown']):
        reject(state, seat, {'type': 'choose_mechanic', 'card_ids': ids})
    for keeper, loser in ((old, new), (new, old)):
        restored = deserialize_match_snapshot(serialize_match_snapshot(state))
        resolved = checked_action(restored, rules, seat, {'type': 'choose_mechanic', 'card_ids': [keeper]})
        assert not resolved.pending_mechanic_choice
        assert resolved.cards[keeper].zone == Zone.BATTLEFIELD and resolved.cards[loser].zone == Zone.GRAVEYARD

    for target_name in ('Elvish Mystic', 'Torrential Gearhulk'):
        state = position(seat)
        target = add(state, exchange[target_name], 3-seat, Zone.BATTLEFIELD)
        source = add(state, exchange['Volatile Stormdrake'], seat, Zone.HAND)
        state = cast(state, seat, source)
        assert state.pending_trigger_order['phase'] == 'targets'
        choice = next(m for m in rules.legal_moves(state, seat) if m.get('target_card_id') == target)
        state = checked_action(state, rules, seat, {'type': 'choose_trigger_target', 'stack_id': choice['stack_id'], 'target_card_id': target})
        for _ in range(10):
            if state.pending_mechanic_choice:
                break
            state = checked_action(state, rules, state.priority_player, {'type': 'pass_priority'})
        else:
            raise AssertionError('Exchange did not pause for genuine energy payment')
        assert state.pending_mechanic_choice['kind'] == 'exchange_energy_payment'
        assert state.cards[source].controller == 3-seat and state.cards[target].controller == seat
        assert state.players[seat].counters['energy'] == 4
        options = state.pending_mechanic_choice['options']
        assert options == (['pay', 'decline'] if target_name == 'Elvish Mystic' else ['decline'])
        rows.append(row(state, seat))
        reject(state, 3-seat, {'type': 'choose_mechanic', 'choice_id': options[0]})
        reject(state, seat, {'type': 'choose_mechanic', 'choice_id': 'unknown'})
        if options == ['decline']:
            reject(state, seat, {'type': 'choose_mechanic', 'choice_id': 'pay'})
        for choice in options:
            restored = deserialize_match_snapshot(serialize_match_snapshot(state))
            resolved = checked_action(restored, rules, seat, {'type': 'choose_mechanic', 'choice_id': choice})
            assert not resolved.pending_mechanic_choice
            assert resolved.cards[target].zone == (Zone.BATTLEFIELD if choice == 'pay' else Zone.GRAVEYARD)
            assert resolved.players[seat].counters['energy'] == (3 if choice == 'pay' else 4)
print(json.dumps(rows))
