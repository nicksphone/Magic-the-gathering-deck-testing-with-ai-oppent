"""Both human seats retain selection and bottom ordering across SQLite recovery."""
import pytest
from sqlmodel import Session

import main
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from persistence.db import engine
from persistence.repository import Repository
from tests.test_api_input_contracts import game, persist, rejected
from tests.test_ai_opaque_selection_horizon import ROWS
from tests.test_ai_recurring_engines import add


def restored(match_id):
    main.ACTIVE_MATCHES.pop(match_id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), match_id)
    return main.ACTIVE_MATCHES[match_id]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,count,ordered', [('Impulse', 1, True), ('Anticipate', 1, True),
                                              ('Memory Deluge', 2, False), ('Dig Through Time', 2, True)])
def test_paid_selection_wrong_actor_and_bottom_choice_recover_through_http(game, seat, name, count, ordered):
    client, match = game
    state = match.state
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.players[seat].mana_pool.update({'U': 10})
    card = add(state, name, seat, Zone.HAND, cards=ROWS)
    match_id = state.id
    persist(match)
    response = client.post(f'/matches/{match_id}/action', json={
        'player_id': seat, 'action': {'type': 'cast_spell', 'card_id': card.id}})
    assert response.status_code == 200, response.text
    for _ in range(8):
        state = main.ACTIVE_MATCHES[match_id].state
        if state.pending_mechanic_choice:
            break
        response = client.post(f'/matches/{match_id}/action', json={
            'player_id': state.priority_player, 'action': {'type': 'pass_priority'}})
        assert response.status_code == 200, response.text
    else:
        raise AssertionError('Selection did not pause through HTTP')
    match = restored(match_id)
    choice = match.state.pending_mechanic_choice
    assert choice['kind'] == 'look_top_select_hand' and choice['count'] == count
    chosen = choice['options'][:count]
    action = {'type': 'choose_mechanic', 'card_ids': chosen}
    rejected(client, match, action, 3-seat)
    response = client.post(f'/matches/{match_id}/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    match = restored(match_id)
    assert set(chosen).issubset(match.state.players[seat].hand)
    if ordered:
        assert match.state.pending_mechanic_choice['kind'] == 'topdeck_bottom_order'
        bottom = list(reversed(match.state.pending_mechanic_choice['options']))
        response = client.post(f'/matches/{match_id}/action', json={
            'player_id': seat, 'action': {'type': 'choose_mechanic', 'card_ids': bottom}})
        assert response.status_code == 200, response.text
        match = restored(match_id)
        assert match.state.players[seat].library[:len(bottom)] == bottom
    assert match.state.pending_mechanic_choice is None
    assert match.state.cards[card.id].zone == Zone.GRAVEYARD
    final = serialize_match_snapshot(match.state)
    assert serialize_match_snapshot(restored(match_id).state) == final
