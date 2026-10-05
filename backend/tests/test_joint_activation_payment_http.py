"""Jointly selected costs remain atomic and durable through production HTTP."""
import pytest
from sqlmodel import Session

import main
from game_state.serializers import serialize_match_snapshot
from persistence.db import engine
from persistence.repository import Repository
from tests.test_activation_payment_choices import activation_card
from tests.test_api_input_contracts import game, persist, rejected
from tests.test_joint_activation_payment import petal


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('selected_index', [0, 1])
def test_http_joint_payment_rejects_double_spend_then_pays_either_selection_after_restart(game, seat, selected_index):
    client, match = game
    state = match.state
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    source = activation_card(state, 'trading-post', seat)
    first = petal(state, seat)
    action = {'type': 'activate_ability', 'card_id': source.id, 'ability_index': 3,
              'payment_choices': {'sacrifice_card_ids': [first.id]}}
    persist(match)
    rejected(client, match, action, seat)
    # Rejected mutations may restore a new authoritative state object.
    state = match.state
    second = petal(state, seat)
    selected = [first, second][selected_index]
    action['payment_choices']['sacrifice_card_ids'] = [selected.id]
    persist(match)
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    response = client.post(f'/matches/{state.id}/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    paid = main.ACTIVE_MATCHES[state.id]
    assert len(paid.state.stack) == 1
    assert {first.id, second.id}.issubset(paid.state.players[seat].graveyard)
    assert source.id in paid.state.players[seat].battlefield
    assert paid.state.cards[source.id].tapped
    assert sum(paid.state.players[seat].mana_pool.values()) == 0
    snapshot = serialize_match_snapshot(paid.state)
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    assert serialize_match_snapshot(main.ACTIVE_MATCHES[state.id].state) == snapshot
