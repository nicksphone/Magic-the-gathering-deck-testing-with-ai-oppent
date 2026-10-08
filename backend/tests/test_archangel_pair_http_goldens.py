"""NEW paid public paired-kicker API/owned-SQL goldens; no private payment injection."""
import pytest
from sqlmodel import Session
import main
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from persistence.db import engine
from persistence.repository import Repository
from tests.test_api_input_contracts import game, persist, snapshot
from tests.test_archangel_pair_paid_desired import CHOICES, ROWS, setup, g


def current(mid):
    return main.ACTIVE_MATCHES[mid]


def submit(client, mid, seat, action):
    response = client.post(f'/matches/{mid}/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    return response.json()


def sql_restore(mid):
    before = serialize_match_snapshot(current(mid).state)
    main.ACTIVE_MATCHES.pop(mid)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), mid)
    assert serialize_match_snapshot(current(mid).state) == before
    return current(mid).state


def actual_choices(client, mid, seat):
    response = client.get(f'/matches/{mid}/legal-moves?player_id={seat}')
    assert response.status_code == 200, response.text
    return response.json()['moves']


def reach(client, mid, seat, predicate):
    for _ in range(128):
        state = current(mid).state
        if predicate(state):
            return state
        assert not state.pending_mechanic_choice and not state.pending_replacement_choice
        if state.pending_trigger_order:
            actor = state.pending_trigger_order['current_controller']
            moves = actual_choices(client, mid, actor)
            if state.pending_trigger_order.get('phase') == 'targets':
                move = next(m for m in moves if m['type'] == 'choose_trigger_target'
                            and m.get('target_player') == 3-seat)
                assert (move.get('target_card_id') is None) != (move.get('target_player') is None)
                target_key = 'target_card_id' if move.get('target_card_id') is not None else 'target_player'
                move = {'type': move['type'], 'stack_id': move['stack_id'],
                        target_key: move[target_key]}
            else:
                move = next(m for m in moves if m['type'] == 'choose_trigger_order')
                move = {'type': 'choose_trigger_order', 'trigger_order': move['trigger_order']}
            submit(client, mid, actor, move)
        else:
            submit(client, mid, state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('128 actual HTTP choices/priority actions exceeded bound')


def position(controller, seat):
    state, source = setup(seat)
    state.id = controller.state.id
    state.players[seat].mana_pool = {'C': 2, 'W': 2, 'B': 1, 'R': 1}
    controller.state = state
    persist(controller)
    return state.id, source


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('choice,count,paid', CHOICES)
def test_paid_public_four_choices_real_etbs_lifelink_and_owned_sql_reset(game, seat, choice, count, paid):
    client, controller = game
    mid, source = position(controller, seat)
    move = next(m for m in actual_choices(client, mid, seat) if m.get('card_id') == source
                and m['type'] == 'cast_spell')
    assert {c['id'] for c in move['cost_options']} == {row[0] for row in CHOICES}
    assert len(move['cost_options']) == 4
    submit(client, mid, seat, {'type': 'cast_spell', 'card_id': source,
                              'cost_choice': {'id': choice}, 'targets': {}})
    state = current(mid).state
    assert state.players[seat].mana_pool.get('C', 0) == state.players[seat].mana_pool.get('W', 0) == 0
    assert all(state.players[seat].mana_pool.get(symbol, 0) == (0 if symbol in paid else 1)
               for symbol in ('B', 'R'))
    assert state.cards[source].zone == Zone.STACK
    spell = next(i.id for i in state.stack if i.source_card_id == source)
    assert state.cards[source].kicker_count == count and state.cards[source].was_kicked is (count > 0)
    assert state.stack[-1].payload['__kicker_count'] == count and state.stack[-1].payload['__kicked'] is (count > 0)
    state = sql_restore(mid)
    assert state.cards[source].kicker_count == count
    state = reach(client, mid, seat, lambda s: all(i.id != spell for i in s.stack))
    assert state.cards[source].zone == Zone.BATTLEFIELD and state.cards[source].kicker_count == count
    if count:
        assert state.pending_trigger_order
        queued = [t for group in state.pending_trigger_order.get('groups', {}).values()
                  for t in group if t['source_card_id'] == source]
        assert len(queued) + sum(i.source_card_id == source for i in state.stack) == count
    state = reach(client, mid, seat, lambda s: not s.pending_trigger_order)
    triggers = [i for i in state.stack if i.source_card_id == source]
    assert len(triggers) == count
    assert all(i.effect_key == 'deal_damage' and i.payload['amount'] == 2
               and i.payload['target_player'] == 3-seat for i in triggers)
    state = sql_restore(mid)
    assert len([i for i in state.stack if i.source_card_id == source]) == count
    state = reach(client, mid, seat, lambda s: not s.stack)
    assert state.players[seat].life == 20 + 2*count and state.players[3-seat].life == 20 - 2*count
    assert state.cards[source].kicker_count == count and state.cards[source].was_kicked is (count > 0)
    state = sql_restore(mid)
    # Actual paid canonical public return, not direct move/count reset or fake events.
    bounce = g.add(state, ROWS, 'Unsummon', 3-seat, Zone.HAND)
    state.players[3-seat].mana_pool = {'U': 1}
    persist(current(mid))
    state = reach(client, mid, seat, lambda s: s.priority_player == 3-seat)
    submit(client, mid, 3-seat, {'type': 'cast_spell', 'card_id': bounce,
                                'cost_choice': {'id': 'base'}, 'targets': {'target_card_id': source}})
    assert current(mid).state.players[3-seat].mana_pool.get('U', 0) == 0
    state = reach(client, mid, seat, lambda s: not s.stack)
    assert state.cards[source].zone == Zone.HAND
    assert state.cards[source].kicker_count is None and state.cards[source].was_kicked is False
    assert state.cards[source].last_known_battlefield['kicker_count'] == count
    state = sql_restore(mid)
    assert 'kicker_count' not in serialize_match_snapshot(state)['cards'][source]
    assert state.players[seat].life == 20 + 2*count and state.players[3-seat].life == 20 - 2*count


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('forged', [None, 1])
def test_forged_public_count_422_preserves_root_controller_and_owned_sql(game, seat, forged):
    client, controller = game
    mid, source = position(controller, seat)
    before = snapshot(controller)
    response = client.post(f'/matches/{mid}/action', json={'player_id': seat, 'action': {
        'type': 'cast_spell', 'card_id': source,
        'cost_choice': {'id': 'kicker_1_2', 'kicker_count': forged}, 'targets': {}}})
    assert response.status_code == 422, response.text
    assert snapshot(controller) == before
    assert not controller.state.stack and controller.state.cards[source].zone == Zone.HAND
    assert controller.state.cards[source].kicker_count is None and not controller.state.cards[source].was_kicked
    assert controller.state.players[seat].mana_pool == {'C': 2, 'W': 2, 'B': 1, 'R': 1}
