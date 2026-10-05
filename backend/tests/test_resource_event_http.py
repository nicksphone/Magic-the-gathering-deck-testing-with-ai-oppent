"""Both-seat resource triggers survive actual HTTP mutation and SQLite recovery."""
import pytest
from sqlmodel import Session

import main
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot
from persistence.db import engine
from persistence.repository import Repository
from tests.test_api_input_contracts import game, persist
from tests.test_cast_resource_payments import ROWS, add


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['convoke', 'delve'])
def test_resource_trigger_survives_http_restart(game, seat, kind):
    client, match = game
    state = match.state
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    name = 'Siege Wurm' if kind == 'convoke' else 'Dig Through Time'
    watcher_name = 'Emmara, Soul of the Accord' if kind == 'convoke' else 'Tormod, the Desecrator'
    spell = add(state, name, seat, Zone.HAND, cards=ROWS)
    watcher = add(state, watcher_name, seat, cards=ROWS)
    if kind == 'convoke':
        state.players[seat].mana_pool = {color: amount for color, amount in [('C', 4), ('G', 2)]}
        payment = {'convoke': [{'card_id': watcher.id, 'pay_as': 'generic'}]}
    else:
        state.players[seat].mana_pool = {'U': 2}
        payment = {'delve': [add(state, 'Ornithopter', seat, Zone.GRAVEYARD, cards=ROWS).id
                             for _ in range(6)]}
    persist(match)
    response = client.post(f'/matches/{state.id}/action', json={
        'player_id': seat, 'action': {'type': 'cast_spell', 'card_id': spell.id, 'resource_payment': payment}})
    assert response.status_code == 200, response.text
    current = main.ACTIVE_MATCHES[state.id].state
    assert [item.source_card_id for item in current.stack] == [spell.id, watcher.id]
    snapshot = serialize_match_snapshot(current)
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    assert serialize_match_snapshot(main.ACTIVE_MATCHES[state.id].state) == snapshot
