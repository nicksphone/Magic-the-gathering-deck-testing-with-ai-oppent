"""Announced graveyard casting methods persist through HTTP and restart."""
import pytest
from sqlmodel import Session

import main
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot
from persistence.db import engine
from persistence.repository import Repository
from tests.test_api_input_contracts import game, persist, rejected
from tests.test_graveyard_cast_methods import RAW, BESTOW, ROWS, LIMITED, add
from rules_engine.costs import casting_method


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('method', ['prototype', 'bestow'])
def test_method_and_permission_survive_http_restart(game, seat, method):
    client, match = game
    state = match.state
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.players[seat].mana_pool = {color: 4 for color in 'WUBRGC'}
    source = 'Lurrus of the Dream-Den' if method == 'prototype' else 'Muldrotha, the Gravetide'
    add(state, source, seat, cards=LIMITED)
    host = add(state, 'Diregraf Ghoul', seat, cards=ROWS)
    name, rows = (RAW['name'], {RAW['name']: RAW}) if method == 'prototype' else ('Leafcrown Dryad', BESTOW)
    card = add(state, name, seat, Zone.GRAVEYARD, cards=rows)
    persist(match)
    legal = client.get(f'/matches/{state.id}/legal-moves?player_id={seat}').json()['moves']
    cost = next(option for move in legal if move.get('card_id') == card.id
                for option in move.get('cost_options', []) if casting_method(option['id']) == method)
    action = {'type': 'cast_spell', 'card_id': card.id, 'from_graveyard': True,
              'cost_choice': {'id': cost['id']}, 'targets': {'target_card_id': host.id} if method == 'bestow' else {}}
    rejected(client, match, {**action, 'cost_choice': {'id': 'missing'}}, player_id=seat)
    response = client.post(f'/matches/{state.id}/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    actual = main.ACTIVE_MATCHES[state.id].state
    assert len(actual.graveyard_permission_uses) == 1
    assert actual.cards[card.id].zone == Zone.STACK
    if method == 'prototype':
        assert actual.cards[card.id].mana_cost == '{1}{B}' and actual.cards[card.id].colors == ['B']
    else:
        assert actual.cards[card.id].types == ['Enchantment']
        assert next(iter(actual.graveyard_permission_uses)).endswith(':Enchantment')
    snapshot = serialize_match_snapshot(actual)
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    assert serialize_match_snapshot(main.ACTIVE_MATCHES[state.id].state) == snapshot
