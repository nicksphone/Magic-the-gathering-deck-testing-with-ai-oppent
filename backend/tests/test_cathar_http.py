"""Run only in disposable source: API lifespan writes source-local SQLite."""
import json

import pytest
from sqlmodel import Session

import main
from card_data.hydration import hydrate_deck_cards
from game_state.state import Zone
from persistence.db import engine
from persistence.repository import Repository
from tests.test_api_input_contracts import game, persist
from tests.test_cathar_day_night_linked_exile import CATHAR, FACTS, setup


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('designation', ['none', 'day', 'night'])
def test_cached_http_cast_target_choice_and_restart(game, monkeypatch, seat, designation):
    client, _ = game
    monkeypatch.setattr(main, '_hydrate_deck_cards', hydrate_deck_cards)
    with Session(engine) as session:
        repo = Repository(session)
        for facts in FACTS.values():
            payload = {key: value for key, value in facts.items() if key not in {'card_faces', 'colors'}}
            payload['colors'] = ','.join(facts['colors'])
            payload['card_faces_json'] = json.dumps(facts['card_faces'])
            repo.upsert_card(payload)
    deck = [{'quantity': quantity, 'card_name': name}
            for name, quantity in [(CATHAR, 4), ('Recruitment Officer', 4), ('Plains', 52)]]
    response = client.post('/matches/start', json={'deck_a': deck, 'deck_b': deck,
        'controller_a': 'human', 'controller_b': 'human', 'mode': 'human_vs_human', 'seed': 621})
    assert response.status_code == 200, response.text
    mid = response.json()['id']
    match = main.ACTIVE_MATCHES[mid]
    assert all(len(card.card_faces) == 2 for card in match.state.cards.values() if card.name == 'Brutal Cathar')
    # Controlled canonical board isolates entry/targeting from opening shuffles.
    state, source, targets, _ = setup(seat, designation)
    state.id = mid
    match.state = state
    persist(match)

    def restore():
        main.ACTIVE_MATCHES.pop(mid)
        with Session(engine) as session:
            main._restore_active_matches(Repository(session), mid)
        return main.ACTIVE_MATCHES[mid]

    def action(pid, payload):
        response = client.post(f'/matches/{mid}/action', json={'player_id': pid, 'action': payload})
        assert response.status_code == 200, response.text
        return response.json()

    action(seat, {'type': 'cast_spell', 'card_id': source.id})
    for _ in range(4):
        current = main.ACTIVE_MATCHES[mid].state
        if current.cards[source.id].zone == Zone.BATTLEFIELD:
            break
        action(current.priority_player, {'type': 'pass_priority'})
    restored = restore()
    view = client.get(f'/matches/{mid}').json()
    card = next(card for card in view['players'][str(seat)]['battlefield'] if card['id'] == source.id)
    assert card['selected_face_index'] == (1 if designation == 'night' else 0)
    assert len(card['card_faces']) == 2
    if designation == 'night':
        assert card['name'] == 'Moonrage Brute' and not view['stack']
        assert (card['power'], card['toughness']) == (3, 3)
        return
    legal = client.get(f'/matches/{mid}/legal-moves', params={'player_id': seat}).json()['moves']
    choices = [move for move in legal if move['type'] == 'choose_trigger_target']
    assert {move['target_card_id'] for move in choices} == {target.id for target in targets}
    choice = next(move for move in choices if move['target_card_id'] == targets[1].id)
    action(seat, {key: value for key, value in choice.items() if key != 'target_name'})
    for _ in range(4):
        current = main.ACTIVE_MATCHES[mid].state
        if current.cards[targets[1].id].zone == Zone.EXILE:
            break
        action(current.priority_player, {'type': 'pass_priority'})
    restored = restore()
    assert restored.state.cards[targets[1].id].zone == Zone.EXILE
    assert restored.state.linked_exiles
