"""Color-based spell pricing reaches strict HTTP and durable snapshots."""
import pytest
from sqlmodel import Session

import main
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot
from persistence.db import engine
from persistence.repository import Repository
from tests.test_api_input_contracts import game, persist, rejected
from tests.test_announced_spell_costs import add, ROWS, RAW


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('scenario', ['discount', 'unrelated-tax', 'prototype'])
def test_color_pricing_http_rejection_and_restart(game, seat, scenario):
    client, match = game
    state = match.state
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    source = {'discount': 'Ruby Medallion', 'unrelated-tax': 'Gloom', 'prototype': 'Ugin, the Ineffable'}[scenario]
    add(state, source, 3-seat if scenario == 'unrelated-tax' else seat)
    name = RAW['name'] if scenario == 'prototype' else 'Young Pyromancer'
    card = add(state, name, seat, Zone.HAND, cards={name: RAW} if scenario == 'prototype' else ROWS)
    mana = {'R': 1} if scenario == 'discount' else {'R': 1, 'C': 1} if scenario == 'unrelated-tax' else {'B': 2}
    state.players[seat].mana_pool = {color: mana.get(color, 0) for color in 'WUBRGC'}
    persist(match)
    action = {'type': 'cast_spell', 'card_id': card.id,
              'cost_choice': {'id': 'prototype' if scenario == 'prototype' else 'base'}}
    rejected(client, match, {**action, 'cost_choice': {'id': 'missing'}}, player_id=seat)
    response = client.post(f'/matches/{state.id}/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    actual = main.ACTIVE_MATCHES[state.id].state
    assert actual.cards[card.id].zone == Zone.STACK
    assert next(item.payload['mana_spent'] for item in actual.stack
                if item.source_card_id == card.id and 'mana_spent' in item.payload) == sum(mana.values())
    snapshot = serialize_match_snapshot(actual)
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    assert serialize_match_snapshot(main.ACTIVE_MATCHES[state.id].state) == snapshot
