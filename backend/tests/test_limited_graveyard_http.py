"""Real limited-permission costs cross API validation and durable restart."""
import pytest
import json
from sqlmodel import Session

import main
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot
from persistence.db import engine
from persistence.repository import Repository
from tests.test_api_input_contracts import game, persist, rejected
from tests.test_graveyard_play_permissions import ROWS, add, DIRECTORY
from tests.test_limited_graveyard_permissions import LIMITED


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('source,spell', [('Lurrus of the Dream-Den', 'Sol Ring'),
                                        ('Gisa and Geralf', 'Diregraf Ghoul'),
                                        ('Muldrotha, the Gravetide', 'Sol Ring')])
def test_limited_cast_usage_and_rejection_survive_database_restart(game, seat, source, spell):
    client, match = game
    state = match.state
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.players[seat].mana_pool = {color: 4 for color in 'WUBRGC'}
    add(state, source, seat, cards=LIMITED)
    first, second = [add(state, spell, seat, Zone.GRAVEYARD, cards=ROWS) for _ in range(2)]
    persist(match)
    moves = client.get(f'/matches/{state.id}/legal-moves?player_id={seat}').json()['moves']
    move = next(move for move in moves if move.get('card_id') == first.id)
    cost = move['cost_options'][0]
    assert source in cost['label']
    response = client.post(f'/matches/{state.id}/action', json={'player_id': seat,
        'action': {'type': 'cast_spell', 'card_id': first.id, 'from_graveyard': True,
                   'cost_choice': {'id': cost['id']}}})
    assert response.status_code == 200, response.text
    snapshot = serialize_match_snapshot(main.ACTIVE_MATCHES[state.id].state)
    assert len(snapshot['graveyard_permission_uses']) == 1
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    restored = main.ACTIVE_MATCHES[state.id]
    assert serialize_match_snapshot(restored.state) == snapshot
    for _ in range(2):
        actor = main.ACTIVE_MATCHES[state.id].state.priority_player
        passed = client.post(f'/matches/{state.id}/action', json={
            'player_id': actor, 'action': {'type': 'pass_priority'}})
        assert passed.status_code == 200, passed.text
    restored = main.ACTIVE_MATCHES[state.id]
    assert not restored.state.stack
    assert restored.state.cards[first.id].zone == Zone.BATTLEFIELD
    rejected(client, restored, {'type': 'cast_spell', 'card_id': second.id,
        'from_graveyard': True, 'cost_choice': {'id': cost['id']}}, player_id=seat)


@pytest.mark.parametrize('seat', [1, 2])
def test_limited_land_source_is_validated_and_restored_independently_of_total_allowance(game, seat):
    client, match = game
    state = match.state
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    add(state, 'Muldrotha, the Gravetide', seat, cards=LIMITED)
    raw = json.loads((DIRECTORY / 'exploration.json').read_text())
    add(state, raw['name'], seat, cards={raw['name']: {**raw, 'power': None, 'toughness': None}})
    first, second = [add(state, 'Forest', seat, Zone.GRAVEYARD, cards=ROWS) for _ in range(2)]
    persist(match)
    available = client.get(f'/matches/{state.id}/legal-moves?player_id={seat}').json()['moves']
    move = next(move for move in available if move.get('card_id') == first.id and move['type'] == 'play_land')
    action = {'type': 'play_land', 'card_id': first.id, 'from_graveyard': True,
              'graveyard_permission_key': move['graveyard_permission_key']}
    rejected(client, match, {**action, 'graveyard_permission_key': 'missing'}, player_id=seat)
    response = client.post(f'/matches/{state.id}/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    assert response.json()['players'][str(seat)]['land_plays_remaining'] == 1
    expected = serialize_match_snapshot(main.ACTIVE_MATCHES[state.id].state)
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    restored = main.ACTIVE_MATCHES[state.id]
    assert serialize_match_snapshot(restored.state) == expected
    rejected(client, restored, {**action, 'card_id': second.id}, player_id=seat)
