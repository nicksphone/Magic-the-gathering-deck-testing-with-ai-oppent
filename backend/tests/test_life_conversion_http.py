"""Canonical affected-player choices through API and SQLite restoration."""
import json
from pathlib import Path

import pytest
from sqlmodel import Session

import main
from game_state.state import Zone
from persistence.db import engine
from persistence.repository import Repository
from tests.test_api_input_contracts import game, persist, rejected
from tests.test_life_conversion import permanent
from tests.test_linked_damage_targets import raw_card


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('first', ['conversion', 'double'])
def test_paid_gain_replacement_choice_restores_affected_seat_and_resumes_spell(game, seat, first):
    client, match = game
    state = match.state
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = 1
    state.land_entries_this_turn = {1: 0, 2: 0}
    converter = permanent(state, 'tainted-remedy', 3-seat)
    doubler = permanent(state, 'alhammarrets-archive', seat)
    raw = json.loads((Path(__file__).parent / 'fixtures/landfall/rest-for-the-weary.json').read_text())
    spell = raw_card(state, raw, 1, Zone.HAND)
    state.players[1].mana_pool = {'W': 1, 'C': 1}
    state.replacement_choice_required = True
    state.replacement_choice_players = {1, 2}
    persist(match)
    path = f'/matches/{state.id}/action'
    result = client.post(path, json={'player_id': 1, 'action': {
        'type': 'cast_spell', 'card_id': spell.id, 'targets': {'target_player': seat}}})
    assert result.status_code == 200, result.text
    for _ in range(4):
        if match.state.pending_replacement_choice:
            break
        result = client.post(path, json={'player_id': match.state.priority_player,
                                        'action': {'type': 'pass_priority'}})
        assert result.status_code == 200, result.text
    pending = match.state.pending_replacement_choice
    assert pending['player_id'] == seat
    assert {row['source_id'] for row in pending['options']} == {converter.id, doubler.id}
    assert match.state.players[seat].life == 20
    rejected(client, match, {'type': 'choose_replacement', 'replacement_source_id': converter.id}, 3-seat)
    mid = state.id
    main.ACTIVE_MATCHES.pop(mid)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), mid)
    restored = main.ACTIVE_MATCHES[mid]
    assert restored.state.pending_replacement_choice['player_id'] == seat
    result = client.post(path, json={'player_id': seat, 'action': {
        'type': 'choose_replacement',
        'replacement_source_id': converter.id if first == 'conversion' else doubler.id}})
    assert result.status_code == 200, result.text
    assert restored.state.players[seat].life == (16 if first == 'conversion' else 12)
    assert restored.state.pending_replacement_choice is None
    assert spell.id in restored.state.players[1].graveyard
    assert restored.state.players[1].mana_pool.get('W', 0) == 0
