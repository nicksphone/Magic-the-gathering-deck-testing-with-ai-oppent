"""Real owned HTTP comparison; not a backup-cluster or global rules certificate."""
import json

from game_state.state import CardInstance, StackItem, Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.targeting import stack_object_kind
from tests.test_api_input_contracts import game, add_card, persist


def prepare(controller):
    add_card(controller, 'font', 'Font of Agonies', Zone.BATTLEFIELD, ['Enchantment'],
             text='Whenever you pay life, put that many blood counters on this enchantment.')
    add_card(controller, 'boon', 'Withering Boon', Zone.HAND, ['Instant'], '{1}{B}',
             'As an additional cost to cast this spell, pay 3 life.\nCounter target creature spell.')
    controller.state.players[1].mana_pool.update({'B': 1, 'C': 1})


def test_original_manual_empty_payload_is_not_a_typed_counter_target(game):
    client, controller = game
    prepare(controller)
    bear = CardInstance('bear', 'Grizzly Bears', 2, 2, Zone.STACK, ['Creature'],
                        mana_cost='{1}{G}', power=2, toughness=2)
    controller.state.cards[bear.id] = bear
    item = StackItem('bear-spell', bear.id, 2, bear.name, 'noop', {})
    controller.state.stack.append(item)
    persist(controller)
    assert stack_object_kind(controller.state, item) == 'legacy_unknown'
    response = client.get(f'/matches/{controller.state.id}/legal-moves?player_id=1')
    assert response.status_code == 200
    assert not any(move.get('card_id') == 'boon' and move['type'] == 'cast_spell'
                   for move in response.json()['moves'])
    print('BOON_MANUAL_EVIDENCE', json.dumps({'kind': stack_object_kind(controller.state, item),
                                             'offered': False, 'payload': item.payload}))


def test_actual_paid_opponent_cast_then_boon_keeps_original_life_and_trigger(game):
    client, controller = game
    prepare(controller)
    state = controller.state
    bear = add_card(controller, 'bear', 'Grizzly Bears', Zone.HAND, ['Creature'],
                    cost='{1}{G}', power=2, toughness=2, owner=2)
    state.active_player = state.priority_player = 2
    state.players[2].mana_pool.update({'G': 1, 'C': 1})
    persist(controller)
    base = f'/matches/{state.id}'
    response = client.post(base + '/action', json={'player_id': 2,
                                                  'action': {'type': 'cast_spell', 'card_id': bear.id}})
    assert response.status_code == 200, response.text
    state = controller.state
    assert len(state.stack) == 1
    item = state.stack[0]
    assert item.source_card_id == bear.id and item.controller == 2
    assert item.payload['mana_spent'] == 2
    assert item.payload['__announced_stack_kind'] == 'spell'
    assert stack_object_kind(state, item) == 'spell'
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert restored.stack[0].payload == item.payload
    assert stack_object_kind(restored, restored.stack[0]) == 'spell'
    response = client.post(base + '/action', json={'player_id': 2,
                                                  'action': {'type': 'pass_priority'}})
    assert response.status_code == 200, response.text
    state = controller.state
    assert state.priority_player == 1
    moves = client.get(base + '/legal-moves?player_id=1')
    assert moves.status_code == 200
    move = next(move for move in moves.json()['moves']
                if move.get('card_id') == 'boon' and move['type'] == 'cast_spell')
    assert [target['id'] for target in move['target_hints']['stack_targets']] == [item.id]
    response = client.post(base + '/action', json={'player_id': 1,
                                                  'action': {'type': 'cast_spell', 'card_id': 'boon',
                                                             'targets': {'target_stack_id': item.id}}})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['players']['1']['life'] == 17
    assert [item['label'] for item in body['stack']] == ['Grizzly Bears', 'Withering Boon', 'Font of Agonies trigger']
    print('BOON_PAID_EVIDENCE', json.dumps({'kind': stack_object_kind(state, item),
                                           'paid_mana': item.payload['mana_spent'],
                                           'life': body['players']['1']['life'],
                                           'labels': [entry['label'] for entry in body['stack']]}))
