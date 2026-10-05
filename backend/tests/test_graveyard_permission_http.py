"""Both-seat graveyard actions cross strict HTTP contracts and SQLite restart."""
import pytest
from sqlmodel import Session

import main
from game_state.serializers import serialize_match_snapshot
from game_state.state import Step, Zone
from persistence.db import engine
from persistence.repository import Repository
from tests.test_api_input_contracts import game, persist, rejected
from tests.test_graveyard_play_permissions import ROWS, add


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['cast_spell', 'play_land'])
def test_graveyard_source_flag_view_and_restart(game, seat, kind):
    client, match = game
    state = match.state
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = seat
    state.players[seat].mana_pool = {'B': 1}
    name, grant = ('Gravecrawler', 'Diregraf Ghoul') if kind == 'cast_spell' else ('Forest', 'Crucible of Worlds')
    card = add(state, name, seat, Zone.GRAVEYARD, cards=ROWS)
    add(state, grant, seat, cards=ROWS)
    persist(match)
    available = client.get(f'/matches/{state.id}/legal-moves?player_id={seat}')
    assert available.status_code == 200
    move = next(move for move in available.json()['moves'] if move.get('card_id') == card.id and move['type'] == kind)
    assert move['from_graveyard'] and move['card_view']['name'] == name
    response = client.post(f'/matches/{state.id}/action', json={
        'player_id': seat, 'action': {'type': kind, 'card_id': card.id, 'from_graveyard': True}})
    assert response.status_code == 200, response.text
    current = main.ACTIVE_MATCHES[state.id].state
    assert current.cards[card.id].zone == (Zone.STACK if kind == 'cast_spell' else Zone.BATTLEFIELD)
    snapshot = serialize_match_snapshot(current)
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    assert serialize_match_snapshot(main.ACTIVE_MATCHES[state.id].state) == snapshot


@pytest.mark.parametrize('seat', [1, 2])
def test_forged_graveyard_permission_rejected_atomically(game, seat):
    client, match = game
    state = match.state
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    land = add(state, 'Forest', seat, Zone.GRAVEYARD, cards=ROWS)
    persist(match)
    rejected(client, match, {'type': 'play_land', 'card_id': land.id, 'from_graveyard': True}, player_id=seat)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('scenario', ['creature_land', 'graveyard_spell', 'graveyard_only_hand'])
def test_canonical_prohibitions_reject_http_without_mutation(game, seat, scenario):
    client, match = game
    state = match.state
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.players[seat].mana_pool = {'B': 3}
    if scenario == 'graveyard_only_hand':
        card = add(state, 'Haakon, Stromgald Scourge', seat, Zone.HAND, cards=ROWS)
        action = {'type': 'cast_spell', 'card_id': card.id}
    else:
        add(state, "Grafdigger's Cage", 3-seat, cards=ROWS)
        if scenario == 'creature_land':
            add(state, 'Crucible of Worlds', seat, cards=ROWS)
            card = add(state, 'Dryad Arbor', seat, Zone.GRAVEYARD, cards=ROWS)
            kind = 'play_land'
        else:
            add(state, 'Diregraf Ghoul', seat, cards=ROWS)
            card = add(state, 'Gravecrawler', seat, Zone.GRAVEYARD, cards=ROWS)
            kind = 'cast_spell'
        action = {'type': kind, 'card_id': card.id, 'from_graveyard': True}
    persist(match)
    rejected(client, match, action, player_id=seat)
