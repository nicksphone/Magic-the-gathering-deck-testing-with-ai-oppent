"""Selected payments are authoritative, atomic and durable across API recovery."""
import pytest
from sqlmodel import Session

import main
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from persistence.db import engine
from persistence.repository import Repository
from tests.test_api_input_contracts import game, persist, rejected
from tests.test_activation_payment_choices import activation_card
from tests.test_contextual_cost_prohibitions import canonical


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['creature_sacrifice', 'artifact_sacrifice', 'discard'])
def test_selected_payment_rejects_foreign_resource_then_pays_and_resumes_sqlite(game, seat, kind):
    client, match = game
    state = match.state
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    if kind == 'creature_sacrifice':
        source = canonical(state, 'viscera-seer', seat)
        canonical(state, 'viscera-seer', seat)
        selected = source
        foreign = canonical(state, 'viscera-seer', 3-seat)
        key, index = 'sacrifice_card_ids', 0
    elif kind == 'artifact_sacrifice':
        source = activation_card(state, 'trading-post', seat)
        activation_card(state, 'trading-post', seat)
        selected = source
        foreign = activation_card(state, 'trading-post', 3-seat)
        state.players[seat].mana_pool = {color: int(color == 'C') for color in 'WUBRGC'}
        key, index = 'sacrifice_card_ids', 3
    else:
        source = activation_card(state, 'rummaging-goblin', seat)
        selected = canonical(state, 'dismember', seat, Zone.HAND)
        foreign = canonical(state, 'dismember', 3-seat, Zone.HAND)
        key, index = 'discard_card_ids', 0
    persist(match)
    action = {'type': 'activate_ability', 'card_id': source.id, 'ability_index': index,
              'payment_choices': {key: [foreign.id]}}
    rejected(client, match, action, seat)
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    action['payment_choices'] = {key: [selected.id]}
    result = client.post(f'/matches/{state.id}/action', json={'player_id': seat, 'action': action})
    assert result.status_code == 200, result.text
    paid = main.ACTIVE_MATCHES[state.id]
    assert selected.id in paid.state.players[seat].graveyard
    assert foreign.id not in paid.state.players[seat].graveyard
    assert len(paid.state.stack) == 1
    before = serialize_match_snapshot(paid.state)
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    assert serialize_match_snapshot(main.ACTIVE_MATCHES[state.id].state) == before
