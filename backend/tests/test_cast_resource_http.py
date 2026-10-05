"""Real mutation and SQLite recovery; run only in an isolated source checkout."""
import pytest
from sqlmodel import Session

import main
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot
from persistence.db import engine
from persistence.repository import Repository
from tests.test_api_input_contracts import game, persist, rejected
from tests.test_ai_recurring_engines import add
from tests.test_cast_resource_payments import ROWS


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,kind,count', [('Dig Through Time', 'delve', 6),
                                           ('Reverse Engineer', 'improvise', 3)])
def test_paid_resource_cast_rejects_invalid_selection_then_restores(game, seat, name, kind, count):
    client, match = game
    state = match.state
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.players[seat].mana_pool = {c: 2 if c == 'U' else 0 for c in 'WUBRGC'}
    card = add(state, name, seat, Zone.HAND, cards=ROWS)
    zone = Zone.GRAVEYARD if kind == 'delve' else Zone.BATTLEFIELD
    resources = [add(state, 'Ornithopter', seat, zone, cards=ROWS).id for _ in range(count)]
    match_id = state.id
    persist(match)
    base = {'type': 'cast_spell', 'card_id': card.id}
    rejected(client, match, {**base, 'resource_payment': {kind: [resources[0], resources[0]]}}, seat)
    rejected(client, match, {**base, 'resource_payment': {kind: ['missing']}}, seat)
    rejected(client, match, {**base, 'resource_payment': {'unknown': []}}, seat)
    response = client.post(f'/matches/{match_id}/action', json={
        'player_id': seat, 'action': {**base, 'resource_payment': {kind: resources}}})
    assert response.status_code == 200, response.text
    current = main.ACTIVE_MATCHES[match_id]
    expected = serialize_match_snapshot(current.state)
    main.ACTIVE_MATCHES.pop(match_id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), match_id)
    restored = main.ACTIVE_MATCHES[match_id].state
    assert serialize_match_snapshot(restored) == expected
    assert restored.cards[card.id].zone == Zone.STACK
    assert restored.stack[-1].payload['mana_spent'] == 2
