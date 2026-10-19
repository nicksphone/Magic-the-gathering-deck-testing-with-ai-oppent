"""Actual paid HTTP entry choices, persistence, and private packet boundaries."""
from collections import Counter
import json

import pytest
from sqlmodel import Session

import main
from game_state.serializers import serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone
from persistence.db import engine
from persistence.repository import Repository
from tests.graveyard_batch_native_support_bf62 import place
from tests.test_api_input_contracts import game, persist, rejected
from tests.test_entry_copy_native_936 import raw


def restore(match):
    match_id = match.state.id
    before = serialize_match_snapshot(match.state)
    main.ACTIVE_MATCHES.pop(match_id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), match_id)
    restored = main.ACTIVE_MATCHES[match_id]
    assert serialize_match_snapshot(restored.state) == before
    assert restored.controllers == match.controllers
    return restored


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('foreign', [False, True])
@pytest.mark.parametrize('form', ['choice_id', 'card_ids', 'decline', 'forged_context'])
def test_paid_http_copy_choice_restores_then_selects_or_declines(game, seat, foreign, form):
    client, match = game
    target_owner = 3-seat if foreign else seat
    names = {seat: ['Sculpting Steel'], target_owner: ['Sol Ring']}
    if target_owner == seat:
        names[seat] = ['Sculpting Steel', 'Sol Ring']
    def deck(values):
        counts = Counter(values)
        counts['Island'] += 60 - sum(counts.values())
        return [{**raw(name), 'card_name': name, 'quantity': count} for name, count in counts.items()]

    state = MatchFactory.from_decks(deck(names.get(1, [])), deck(names.get(2, [])),
                                    seed=991, game_id=match.state.id)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = seat
    steel = place(state, 'Sculpting Steel', Zone.HAND, seat)
    target = place(state, 'Sol Ring', Zone.BATTLEFIELD, target_owner)
    state.players[seat].mana_pool = {color: 3 if color == 'C' else 0 for color in 'WUBRGC'}
    match.state = state
    persist(match)
    url = f'/matches/{state.id}'

    response = client.post(url + '/action', json={'player_id': seat,
        'action': {'type': 'cast_spell', 'card_id': steel}})
    assert response.status_code == 200, response.text
    assert sum(match.state.players[seat].mana_pool.values()) == 0
    assert match.state.cards[steel].zone == Zone.STACK
    frame = next(item for item in match.state.stack if item.source_card_id == steel)
    frame_id = frame.id
    for _ in range(2):
        response = client.post(url + '/action', json={'player_id': match.state.priority_player,
            'action': {'type': 'pass_priority'}})
        assert response.status_code == 200, response.text
    pending = match.state.pending_mechanic_choice
    assert pending['kind'] == 'entry_copy' and pending['player_id'] == seat
    assert pending['entry_card_id'] == steel and target in pending['options']
    assert pending['resolving_item']['id'] == frame_id

    moves_response = client.get(url + f'/legal-moves?player_id={seat}')
    assert moves_response.status_code == 200, moves_response.text
    offered, = moves_response.json()['moves']
    assert offered['kind'] == 'entry_copy' and offered['count'] == 1
    assert offered['min_count'] == 0 and target in offered['options']
    public = client.get(url).json()['pending_mechanic_choice']
    for key in ('effect_payload', 'resolving_item', 'characteristic_record', '__entry_copy_plan'):
        assert key not in json.dumps(public)
    rejected(client, match, {'type': 'choose_mechanic', 'card_ids': [target]}, 3-seat)
    rejected(client, match, {'type': 'choose_mechanic', 'card_ids': ['stale-card']}, seat)

    match = restore(match)
    assert match.state.pending_mechanic_choice == pending
    if form == 'forged_context':
        rejected(client, match, {'type': 'choose_mechanic', 'card_ids': [target],
            'resolving_item': pending['resolving_item']}, seat)
    fields = {'choice_id': {'choice_id': target}, 'card_ids': {'card_ids': [target]},
              'decline': {'card_ids': []}, 'forged_context': {'card_ids': [target]}}[form]
    response = client.post(url + '/action', json={'player_id': seat,
        'action': {'type': 'choose_mechanic', **fields}})
    assert response.status_code == 200, response.text
    card = match.state.cards[steel]
    assert card.zone == Zone.BATTLEFIELD and card.owner == card.controller == seat
    expected_name = 'Sculpting Steel' if form == 'decline' else 'Sol Ring'
    assert card.name == expected_name and card.oracle_text == raw(expected_name)['oracle_text']
    assert match.state.cards[target].controller == target_owner
    assert not match.state.pending_mechanic_choice and not match.state.stack
    assert match.state.sideboard_facts['inventory'][steel]['stock_key'] == 'Sculpting Steel'
    match = restore(match)
    assert match.state.cards[steel].name == expected_name
    assert not match.state.pending_mechanic_choice and not match.state.stack
