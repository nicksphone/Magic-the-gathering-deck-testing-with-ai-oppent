"""Effective printed life restrictions gate real paid actions after recovery."""
import pytest
from sqlmodel import Session

import main
from persistence.db import engine
from persistence.repository import Repository
from rules_engine.keyword_effects import add_keyword_effect
from tests.test_api_input_contracts import game, persist, rejected
from tests.test_life_conversion import permanent
from tests.test_life_lock_suppression import restriction


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_life_activation_becomes_legal_after_lock_suppression_and_sqlite_resume(game, seat):
    client, match = game
    state = match.state
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    lock = permanent(state, 'platinum-emperion', seat)
    source = restriction(state, 'erebos-god-of-the-dead', seat)
    state.players[seat].mana_pool = {color: int(color in 'BC') for color in 'WUBRGC'}
    persist(match)
    action = {'type': 'activate_ability', 'card_id': source.id, 'ability_index': 0}
    url = f'/matches/{state.id}'
    moves = client.get(f'{url}/legal-moves?player_id={seat}').json()['moves']
    assert not any(row['type'] == 'activate_ability' and row.get('card_id') == source.id for row in moves)
    rejected(client, match, action, seat)
    state = match.state  # Rejection can restore an equivalent authoritative snapshot.
    add_keyword_effect(state, lock.id, ['all abilities'], operation='remove', until_end_of_turn=True)
    persist(match)
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    restored = main.ACTIVE_MATCHES[state.id]
    hand_size = len(restored.state.players[seat].hand)
    moves = client.get(f'{url}/legal-moves?player_id={seat}').json()['moves']
    assert any(row['type'] == 'activate_ability' and row.get('card_id') == source.id for row in moves)
    result = client.post(f'{url}/action', json={'player_id': seat, 'action': action})
    assert result.status_code == 200, result.text
    assert restored.state.players[seat].life == 18
    assert restored.state.players[seat].mana_pool['B'] == 0
    assert restored.state.players[seat].mana_pool['C'] == 0
    assert len(restored.state.stack) == 1
    for _ in range(4):
        if not restored.state.stack:
            break
        result = client.post(f'{url}/action', json={'player_id': restored.state.priority_player,
                                                  'action': {'type': 'pass_priority'}})
        assert result.status_code == 200, result.text
    assert not restored.state.stack
    assert len(restored.state.players[seat].hand) == hand_size+1
    assert restored.state.players[seat].life == 18
