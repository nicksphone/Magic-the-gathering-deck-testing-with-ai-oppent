"""Canonical entry routes; strict NEW audit with no product modifications."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from card_data.fallback_cards import fallback_card_payload
from game_state.serializers import serialize_match_snapshot
from game_state.state import MatchFactory, Zone, object_incarnation
from tests.test_linked_damage_targets import raw_card
from tests.test_ninjutsu_source_identity import http_resolve
from tests.test_selected_mana_http import game, retain, restart, forbid_external_network
from tests.test_training_environment import resolve
from tests.test_training_ninjutsu_intent_audit import scenario


FIXTURE = Path(__file__).parent / 'fixtures/hand_entry_bookkeeping/canonical.jsonl'
PROVENANCE = json.loads(FIXTURE.with_name('provenance.json').read_text())
assert sha256(FIXTURE.read_bytes()).hexdigest() == PROVENANCE['fixture_sha256']
ROWS = {row['name']: row for row in map(json.loads, FIXTURE.read_text().splitlines())}
assert all(row['object'] == 'card' and row['oracle_id'] for row in ROWS.values())


def capture(path, label, state):
    (path / (label + '.json')).write_text(json.dumps(serialize_match_snapshot(state), sort_keys=True))


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_ninjutsu_entry_advances_source_zone_sequence(tmp_path, seat):
    env, action, _, info = scenario(seat)
    before = env._state.cards[info['ninja']].zone_change_sequence
    capture(tmp_path, 'before', env._state)
    env.step(action)
    capture(tmp_path, 'pending', env._state)
    assert env._state.stack[0].payload['__source_zone_sequence'] == before
    resolve(env)
    capture(tmp_path, 'after', env._state)
    source = env._state.cards[info['ninja']]
    assert source.zone == Zone.BATTLEFIELD
    assert source.zone_change_sequence == before + 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('observer', [None, 'Soul Warden', "Cathars' Crusade"])
def test_ninjutsu_entry_metadata_and_real_entry_trigger_restart(game, tmp_path, seat, observer):
    env, action, _, info = scenario(seat)
    state = env._state
    if observer:
        raw_card(state, ROWS[observer], seat, Zone.BATTLEFIELD)
    source = state.cards[info['ninja']]
    before_timestamp = source.effect_timestamp
    before_life = state.players[seat].life
    assert not source.counters
    capture(tmp_path, 'before', state)
    client, match = game
    identifier = retain(match, env)
    response = client.post(f'/matches/{identifier}/action', json={
        'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    queued = restart(identifier).state
    capture(tmp_path, 'pending', queued)
    state = http_resolve(client, identifier)
    capture(tmp_path, 'entered', state)
    source = state.cards[info['ninja']]
    assert source.owner == source.controller == seat
    assert source.zone == Zone.BATTLEFIELD and source.tapped and source.summoning_sick
    assert source.entered_turn == state.turn
    assert source.effect_timestamp > before_timestamp
    assert source.static_order == source.effect_timestamp == object_incarnation(source)
    assert info['ninja'] in state.attackers
    assert state.attack_targets[info['ninja']] == f'player:{3-seat}'
    assert info['attackers'][1] in state.players[seat].hand
    assert info['attackers'][1] not in state.attackers
    assert not source.counters
    assert all(state.cards[cid].tapped for cid in info['lands'])
    assert sum(state.players[seat].mana_pool.values()) == 0
    assert len(state.stack) == int(observer is not None)
    if observer:
        state = http_resolve(client, identifier)
    capture(tmp_path, 'resolved', state)
    assert state.players[seat].life == before_life + int(observer == 'Soul Warden')
    expected = {'+1/+1': 1} if observer == "Cathars' Crusade" else {}
    assert state.cards[info['ninja']].counters == expected
    assert state.cards[info['attackers'][0]].counters == expected
    assert not state.cards[info['attackers'][1]].counters
    assert not state.stack
    assert restart(identifier).state.cards[info['ninja']].counters == expected
    env._state = deepcopy(state)
    foreign = state.players[3-seat].hand[0]
    assert foreign not in env.observe(seat)['known_cards']


def opening_position(seat, name):
    basic = {**fallback_card_payload('Island'), 'card_name': 'Island', 'quantity': 60}
    own = [{**basic, 'quantity': 59}, {**ROWS[name], 'card_name': name, 'quantity': 1}]
    decks = {seat: own, 3-seat: [basic]}
    state = MatchFactory.from_decks(decks[1], decks[2], seed=54)
    state.active_player = state.priority_player = 3-seat
    source = next(card for card in state.cards.values() if card.name == name and card.owner == seat)
    player = state.players[seat]
    if source.id not in player.hand:
        outgoing = player.hand.pop()
        state.cards[outgoing].move_to_zone(Zone.LIBRARY)
        player.library.append(outgoing)
        player.library.remove(source.id)
        source.move_to_zone(Zone.HAND)
        player.hand.append(source.id)
    assert len(player.hand) == 7
    assert source.oracle_text == ROWS[name]['oracle_text']
    return state, source.id


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Leyline of the Void', 'Gemstone Caverns'])
def test_opening_hand_entry_sequence_counters_timestamp_and_http_restart(game, tmp_path, seat, name):
    state, cid = opening_position(seat, name)
    before_sequence = state.cards[cid].zone_change_sequence
    before_timestamp = state.cards[cid].effect_timestamp
    assert not state.cards[cid].counters and not state.attackers
    capture(tmp_path, 'before', state)
    client, match = game
    identifier = retain(match, SimpleNamespace(_state=state))
    for pid in (3-seat, seat):
        response = client.post(f'/matches/{identifier}/action', json={
            'player_id': pid, 'action': {'type': 'keep_hand'}})
        assert response.status_code == 200, response.text
        restart(identifier)
    assert cid in restart(identifier).state.pending_mechanic_choice['options']
    response = client.post(f'/matches/{identifier}/action', json={
        'player_id': seat, 'action': {'type': 'choose_mechanic', 'card_ids': [cid]}})
    assert response.status_code == 200, response.text
    entered = restart(identifier).state
    capture(tmp_path, 'entered', entered)
    source = entered.cards[cid]
    assert source.zone == Zone.BATTLEFIELD
    assert source.zone_change_sequence == before_sequence + 1
    assert source.owner == source.controller == seat
    assert source.entered_turn == entered.turn and not source.tapped
    assert not source.summoning_sick and cid not in entered.attackers
    assert source.effect_timestamp > before_timestamp
    assert source.static_order == source.effect_timestamp == object_incarnation(source)
    assert source.counters == ({'luck': 1} if name == 'Gemstone Caverns' else {})
    if name == 'Gemstone Caverns':
        pending = entered.pending_mechanic_choice
        assert pending['kind'] == 'opening_hand_exile'
        selected = pending['options'][-1]
        response = client.post(f'/matches/{identifier}/action', json={
            'player_id': seat, 'action': {'type': 'choose_mechanic', 'card_ids': [selected]}})
        assert response.status_code == 200, response.text
        assert restart(identifier).state.cards[selected].zone == Zone.EXILE
    final = restart(identifier).state
    capture(tmp_path, 'after', final)
    assert not final.stack and final.cards[cid].zone_change_sequence == before_sequence + 1
    assert len([line for line in final.log if f'begins with {name} on the battlefield' in line]) == 1
