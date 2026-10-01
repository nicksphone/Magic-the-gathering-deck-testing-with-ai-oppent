"""Opening actions share entry preparation; modifier boards are core fixtures,
not claims that these permanents can normally begin a game together.
"""
import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from tests.test_opening_hand import opening_game, add_opening, keep_both
from tests.test_counter_replacements import source as modifier, choose
from tests.test_counter_prohibitions import source as prohibition
from tests.test_api_input_contracts import game, persist
from ai.agent import AIAgent


@pytest.mark.parametrize('player', [1, 2])
@pytest.mark.parametrize('first,expected', [('double', 1), ('half', 0)])
def test_opening_counter_order_is_off_zone_durable_and_finishes_once(player, first, expected):
    state = opening_game(starter=3-player)
    cid = add_opening(state, 'Gemstone Caverns', player)
    state.cards[cid].move_to_zone(Zone.EXILE)
    state.cards[cid].move_to_zone(Zone.HAND)
    modifier(state, 'Vorinclex, Monstrous Raider', player)
    modifier(state, 'Vorinclex, Monstrous Raider', 3-player)
    state = keep_both(state)
    state = checked_action(state, RulesEngine(), player,
                           {'type': 'choose_mechanic', 'card_ids': [cid]})
    assert state.pregame_pending and state.pending_mechanic_choice is None
    assert state.pending_replacement_choice['player_id'] == player
    assert state.cards[cid].zone == Zone.HAND and cid in state.players[player].hand
    assert not state.cards[cid].counters and not state.stack
    assert not any('begins with Gemstone' in line for line in state.log)
    snapshot = serialize_match_snapshot(state)
    option = state.pending_replacement_choice['options'][0]['source_id']
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 3-player,
                       {'type': 'choose_replacement', 'replacement_source_id': option})
    assert serialize_match_snapshot(state) == snapshot
    state = deserialize_match_snapshot(snapshot)
    state = choose(state, first, player)
    assert not state.pending_replacement_choice and state.pregame_pending
    assert state.cards[cid].zone == Zone.BATTLEFIELD
    assert state.cards[cid].counters.get('luck', 0) == expected
    assert state.players[player].battlefield.count(cid) == 1
    assert state.pending_mechanic_choice['kind'] == 'opening_hand_exile'
    assert len([line for line in state.log if 'begins with Gemstone' in line]) == 1
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    exiled = state.pending_mechanic_choice['options'][0]
    state = checked_action(state, RulesEngine(), player,
                           {'type': 'choose_mechanic', 'card_ids': [exiled]})
    assert not state.pregame_pending and state.pending_mechanic_choice is None
    assert state.cards[exiled].zone == Zone.EXILE
    assert len([line for line in state.log if 'Pregame complete.' in line]) == 1


@pytest.mark.parametrize('player', [1, 2])
def test_opening_entry_prepares_ban_before_committing_and_keeps_exile_instruction(player):
    state = opening_game(starter=3-player)
    cid = add_opening(state, 'Gemstone Caverns', player)
    prohibition(state, 'Solemnity')
    state = keep_both(state)
    state = checked_action(state, RulesEngine(), player,
                           {'type': 'choose_mechanic', 'card_ids': [cid]})
    assert state.cards[cid].zone == Zone.BATTLEFIELD
    assert not state.cards[cid].counters
    assert state.pending_mechanic_choice['kind'] == 'opening_hand_exile'
    assert any('cannot get luck counters' in line for line in state.log)


def test_opening_preparation_does_not_spend_next_cast_entry_record():
    state = opening_game(starter=2)
    cid = add_opening(state, 'Gemstone Caverns')
    record = {'controller': 1, 'counter': '+1/+1', 'amount': 3, 'expires_turn': state.turn}
    state.pending_entry_counters.append(record)
    state = keep_both(state)
    state = checked_action(state, RulesEngine(), 1,
                           {'type': 'choose_mechanic', 'card_ids': [cid]})
    assert state.cards[cid].counters == {'luck': 1}
    assert state.pending_entry_counters == [record]


def test_stale_opening_incarnation_is_not_committed_after_choice():
    state = opening_game(starter=2)
    cid = add_opening(state, 'Gemstone Caverns')
    modifier(state, 'Vorinclex, Monstrous Raider', 1)
    modifier(state, 'Vorinclex, Monstrous Raider', 2)
    state = keep_both(state)
    state = checked_action(state, RulesEngine(), 1,
                           {'type': 'choose_mechanic', 'card_ids': [cid]})
    # Deliberately invalidate a paused packet to check its defensive boundary.
    state.cards[cid].move_to_zone(Zone.EXILE)
    state.cards[cid].move_to_zone(Zone.HAND)
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = choose(state, 'double', 1)
    assert state.cards[cid].zone == Zone.HAND and not state.cards[cid].counters
    assert cid not in state.players[1].battlefield
    assert state.pregame_pending and state.pending_mechanic_choice['kind'] == 'opening_hand'
    assert any('entry aborted' in line for line in state.log)


def test_zone_sequence_roundtrip_same_zone_and_old_snapshot_default():
    state = opening_game()
    cid = add_opening(state, 'Gemstone Caverns')
    card = state.cards[cid]
    card.move_to_zone(Zone.HAND)
    assert card.zone_change_sequence == 0
    card.move_to_zone(Zone.EXILE)
    card.move_to_zone(Zone.HAND)
    snapshot = serialize_match_snapshot(state)
    assert deserialize_match_snapshot(snapshot).cards[cid].zone_change_sequence == 2
    snapshot['cards'][cid].pop('zone_change_sequence')
    assert deserialize_match_snapshot(snapshot).cards[cid].zone_change_sequence == 0


@pytest.mark.parametrize('style', ['Aggro', 'Control', 'Tempo', 'Ramp', 'Tokens', 'Tribal', 'Drain'])
def test_ai_completes_opening_counter_choice_and_followup_without_mulligan(style):
    state = opening_game(starter=2)
    cid = add_opening(state, 'Gemstone Caverns')
    modifier(state, 'Vorinclex, Monstrous Raider', 1)
    modifier(state, 'Vorinclex, Monstrous Raider', 2)
    state = keep_both(state)
    rules = RulesEngine()
    state = checked_action(state, rules, 1, {'type': 'choose_mechanic', 'card_ids': [cid]})
    agent = AIAgent(difficulty='master', archetype=style)
    decision = agent.choose_action(state, rules.legal_moves(state, 1), 1)
    assert decision.action['type'] == 'choose_replacement'
    state = checked_action(state, rules, 1, decision.action)
    assert state.cards[cid].counters['luck'] == 1
    decision = agent.choose_action(state, rules.legal_moves(state, 1), 1)
    assert decision.action['type'] == 'choose_mechanic'
    state = checked_action(state, rules, 1, decision.action)
    assert not state.pregame_pending


@pytest.mark.parametrize('player', [1, 2])
def test_http_opening_replacement_restore_preserves_actor_and_hand_until_commit(game, player):
    import main
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository
    client, controller = game
    match_id = controller.state.id
    state = opening_game(starter=3-player)
    state.id = match_id
    cid = add_opening(state, 'Gemstone Caverns', player)
    modifier(state, 'Vorinclex, Monstrous Raider', player)
    modifier(state, 'Vorinclex, Monstrous Raider', 3-player)
    controller.state = keep_both(state)
    persist(controller)
    path = f'/matches/{match_id}'
    response = client.post(path+'/action', json={'player_id': player,
        'action': {'type': 'choose_mechanic', 'card_ids': [cid]}})
    assert response.status_code == 200, response.text
    assert response.json()['pregame_pending']
    assert cid in [card['id'] for card in response.json()['players'][str(player)]['hand']]
    main.ACTIVE_MATCHES.pop(match_id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), match_id)
    assert client.get(path+'/legal-moves').json()['player_id'] == player
    pending = main.ACTIVE_MATCHES[match_id].state.pending_replacement_choice
    option = next(item['source_id'] for item in pending['options'] if item['operation'] == 'double')
    action = {'type': 'choose_replacement', 'replacement_source_id': option}
    assert client.post(path+'/action', json={'player_id': 3-player, 'action': action}).status_code == 422
    response = client.post(path+'/action', json={'player_id': player, 'action': action})
    assert response.status_code == 200, response.text
    view = response.json()
    assert view['pregame_pending'] and view['pending_mechanic_choice']['kind'] == 'opening_hand_exile'
    card = next(card for card in view['players'][str(player)]['battlefield'] if card['id'] == cid)
    assert card['counters']['luck'] == 1
