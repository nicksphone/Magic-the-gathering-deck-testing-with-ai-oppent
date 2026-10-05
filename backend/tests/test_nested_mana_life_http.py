"""Outer/nested life payments use production HTTP rejection and recovery paths."""
import json
from pathlib import Path

import pytest
from sqlmodel import Session

import main
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from persistence.db import engine
from persistence.repository import Repository
from tests.test_api_input_contracts import game, persist, rejected
from tests.test_life_lock_suppression import restriction
from tests.test_linked_damage_targets import raw_card


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('life', [3, 5])
def test_http_nested_life_budget_is_atomic_and_durable_before_and_after_payment(game, seat, life):
    client, match = game
    state = match.state
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.players[seat].life = life
    source = restriction(state, 'erebos-god-of-the-dead', seat)
    raw = json.loads((Path(__file__).parent / 'fixtures/nested_mana_life/mana-confluence.json').read_text())
    for _ in range(2):
        raw_card(state, raw, seat, Zone.BATTLEFIELD)
    persist(match)
    action = {'type': 'activate_ability', 'card_id': source.id, 'ability_index': 0}
    if life == 3:
        rejected(client, match, action, seat)
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    restored = main.ACTIVE_MATCHES[state.id]
    if life == 3:
        rejected(client, restored, action, seat)
        return
    response = client.post(f'/matches/{state.id}/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    paid = main.ACTIVE_MATCHES[state.id]
    assert paid.state.players[seat].life == 1
    assert len(paid.state.stack) == 1
    assert sum(paid.state.players[seat].mana_pool.values()) == 0
    snapshot = serialize_match_snapshot(paid.state)
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    assert serialize_match_snapshot(main.ACTIVE_MATCHES[state.id].state) == snapshot
