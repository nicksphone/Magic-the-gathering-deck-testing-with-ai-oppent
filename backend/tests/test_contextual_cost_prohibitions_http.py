"""Run only in isolated source copies: API lifespan writes a source-local DB."""
import pytest
from sqlmodel import Session

import main
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from persistence.db import engine
from persistence.repository import Repository
from rules_engine.keyword_effects import add_keyword_effect
from tests.test_api_input_contracts import game, persist, rejected
from tests.test_contextual_cost_prohibitions import canonical
from tests.test_life_lock_suppression import restriction


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['life_activation', 'sacrifice_activation', 'phyrexian_spell'])
def test_contextual_cost_rejection_and_paid_action_survive_sqlite_recovery(game, seat, kind):
    client, match = game
    state = match.state
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    angel = canonical(state, 'angel-of-jubilation', 3-seat)
    if kind == 'life_activation':
        payer = restriction(state, 'erebos-god-of-the-dead', seat)
        pool = 'BC'
    elif kind == 'sacrifice_activation':
        payer = canonical(state, 'viscera-seer', seat)
        pool = ''
    else:
        payer = canonical(state, 'dismember', seat, Zone.HAND)
        pool = 'C'
    state.players[seat].mana_pool = {color: int(color in pool) for color in 'WUBRGC'}
    if kind == 'phyrexian_spell':
        action = {'type': 'cast_spell', 'card_id': payer.id,
                  'targets': {'target_card_id': angel.id}, 'hybrid_choices': ['P', 'P'],
                  'cost_choice': {'id': 'base'}}
    else:
        action = {'type': 'activate_ability', 'card_id': payer.id, 'ability_index': 0}
    url = f'/matches/{state.id}'
    persist(match)
    moves = client.get(f'{url}/legal-moves?player_id={seat}').json()['moves']
    assert not any(move.get('card_id') == payer.id and move['type'] == action['type'] for move in moves)
    rejected(client, match, action, seat)
    state = match.state
    add_keyword_effect(state, angel.id, ['all abilities'], operation='remove', until_end_of_turn=True)
    persist(match)
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    restored = main.ACTIVE_MATCHES[state.id]
    moves = client.get(f'{url}/legal-moves?player_id={seat}').json()['moves']
    assert any(move.get('card_id') == payer.id and move['type'] == action['type'] for move in moves)
    result = client.post(f'{url}/action', json={'player_id': seat, 'action': action})
    assert result.status_code == 200, result.text
    assert len(restored.state.stack) == 1
    assert restored.state.players[seat].life == {
        'life_activation': 18, 'sacrifice_activation': 20, 'phyrexian_spell': 16,
    }[kind]
    assert not any(restored.state.players[seat].mana_pool.values())
    if kind == 'sacrifice_activation':
        assert payer.id in restored.state.players[seat].graveyard
        assert payer.id not in restored.state.players[seat].battlefield
    paid = serialize_match_snapshot(restored.state)
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    assert serialize_match_snapshot(main.ACTIVE_MATCHES[state.id].state) == paid
