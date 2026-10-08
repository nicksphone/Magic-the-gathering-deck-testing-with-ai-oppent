"""Real seven-trigger entry episode; no DB, network, child or injected stack."""
import sys

def deny(event, args):
    if event.startswith(('sqlite3.', 'socket.')) or event in ('subprocess.Popen', 'os.system', 'os.fork', 'os.posix_spawn'):
        raise AssertionError('pure trigger-order fixture denied ' + event)
sys.addaudithook(deny)

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from copy import deepcopy
import json
from tests.test_permanent_spell_context import state, card
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import ActionRejected, validate_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack

rows = []
for seat in (1, 2):
    game = state()
    game.active_player = game.priority_player = seat
    game.players[seat].mana_pool.update({color: 20 for color in 'WUBRGC'})
    game.trigger_order_choice_required = True
    game.trigger_order_choice_players = {seat}
    # Seven nonlegendary copies of unchanged canonical Oracle on a trusted board.
    # This proves choice reachability, not a naturally played seven-copy deck.
    first = card(game, 'Soul Warden', Zone.BATTLEFIELD, owner=seat)
    for index in range(1, 7):
        copy = deepcopy(first)
        copy.id = f'warden-{index}'
        game.cards[copy.id] = copy
        game.players[seat].battlefield.append(copy.id)
    entrant = card(game, 'Prodigal Pyromancer', owner=seat)
    rules = RulesEngine()
    rules.take_action(game, seat, {'type': 'cast_spell', 'card_id': entrant.id}, reject_invalid=True)
    assert entrant.zone == Zone.STACK
    resolve_top_of_stack(game)
    assert entrant.zone == Zone.BATTLEFIELD and game.pending_trigger_order
    moves = rules.legal_moves(game, seat)
    assert len(moves) == 1 and len(moves[0]['trigger_order']) == 7
    assert rules.legal_moves(game, 3-seat) == []
    before = serialize_match_snapshot(game)
    reverse = list(reversed(moves[0]['trigger_order']))
    for actor, order in ((3-seat, reverse), (seat, reverse[:-1]), (seat, [reverse[0]] * 7), (seat, ['unknown'] + reverse[1:])):
        try:
            validate_action(game, rules, actor, {"type": "choose_trigger_order", "trigger_order": order})
            rules.take_action(game, actor, {'type': 'choose_trigger_order', 'trigger_order': order}, reject_invalid=True)
        except ActionRejected:
            pass
        else:
            raise AssertionError('Invalid order accepted')
        assert serialize_match_snapshot(game) == before
    game = deserialize_match_snapshot(before)
    expected_sources = {item['_choice_id']: item['source_card_id'] for item in game.pending_trigger_order['groups'][str(seat)]}
    validate_action(game, rules, seat, {'type': 'choose_trigger_order', 'trigger_order': reverse})
    rules.take_action(game, seat, {'type': 'choose_trigger_order', 'trigger_order': reverse}, reject_invalid=True)
    assert game.pending_trigger_order is None
    assert [item.source_card_id for item in game.stack] == [expected_sources[id] for id in reverse]
    for _ in range(7):
        resolve_top_of_stack(game)
    assert game.players[seat].life == 27 and not game.stack
    rows.append({'seat': seat, 'move': moves[0], 'chosen': reverse})
print(json.dumps(rows))
