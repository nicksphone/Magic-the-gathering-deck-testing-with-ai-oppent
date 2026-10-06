"""Bounded entry bodies, genuine duplicate observers and unsupported receipts."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from game_state.state import Zone
from rules_engine.events import emit_event
from tests.test_entry_observers_S2 import ROWS
from tests.test_hand_entry_bookkeeping_audit import capture
from tests.test_linked_damage_targets import raw_card
from tests.test_ninjutsu_source_identity import http_resolve, relocate
from tests.test_selected_mana_http import game, retain, restart, forbid_external_network
from tests.test_training_ninjutsu_intent_audit import scenario


PARTIAL = Path(__file__).parent / 'fixtures/entry_observer_fix/political-triumph.json'
assert sha256(PARTIAL.read_bytes()).hexdigest() == 'ec75e01dffbe05a37355f2850106fa10d1ee672700db9b1791ddd12c383d888b'
POLITICAL = json.loads(PARTIAL.read_bytes())
assert POLITICAL['object'] == 'card' and POLITICAL['oracle_id']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ["Ajani's Welcome", "Cathars' Crusade", 'Soul Warden'])
@pytest.mark.parametrize('departed', [False, True])
def test_actual_duplicate_observers_each_resolve_once_after_human_order_and_restart(
        game, tmp_path, seat, name, departed):
    env, action, _, info = scenario(seat)
    sources = [raw_card(env._state, ROWS[name], seat, Zone.BATTLEFIELD).id for _ in range(2)]
    before_life = env._state.players[seat].life
    client, match = game
    identifier = retain(match, env)
    response = client.post(f'/matches/{identifier}/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    entered = http_resolve(client, identifier)
    pending = entered.pending_trigger_order
    assert pending and pending['current_controller'] == seat
    group = pending['groups'][str(seat)]
    assert len(group) == 2 and {item['source_card_id'] for item in group} == set(sources)
    order = [item['_choice_id'] for item in reversed(group)]
    capture(tmp_path, 'order-pending', entered)
    response = client.post(f'/matches/{identifier}/action', json={
        'player_id': seat, 'action': {'type': 'choose_trigger_order', 'trigger_order': order}})
    assert response.status_code == 200, response.text
    queued = restart(identifier).state
    assert len(queued.stack) == 2
    assert [item.source_card_id for item in queued.stack] == [item['source_card_id'] for item in reversed(group)]
    assert all(item.controller == seat and item.payload['__trigger_event'] == 'enters_battlefield'
               for item in queued.stack)
    if departed:
        env._state = deepcopy(queued)
        for cid in sources:
            relocate(env._state, cid, Zone.EXILE)
        retain(restart(identifier), env)
    capture(tmp_path, 'queued', restart(identifier).state)
    first = http_resolve(client, identifier)
    assert len(first.stack) == 1
    assert first.players[seat].life == before_life + int(name != "Cathars' Crusade")
    final = http_resolve(client, identifier)
    capture(tmp_path, 'resolved', final)
    assert not final.stack
    assert final.players[seat].life == before_life + 2 * int(name != "Cathars' Crusade")
    for cid in [info['ninja'], info['attackers'][0]]:
        assert final.cards[cid].counters == ({'+1/+1': 2} if name == "Cathars' Crusade" else {})
    assert not final.cards[info['attackers'][1]].counters
    env._state = deepcopy(restart(identifier).state)
    secret = env._state.players[3-seat].hand[0]
    assert secret not in env.observe(seat)['known_cards']
    public = client.get(f'/matches/{identifier}/legal-moves?player_id={seat}')
    assert public.status_code == 200 and secret not in public.text


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Altar of the Brood', 'Pandemonium'])
def test_actual_entry_complete_mill_or_unsupported_body_receipt(game, tmp_path, seat, name):
    env, action, _, info = scenario(seat)
    source = raw_card(env._state, ROWS[name], seat, Zone.BATTLEFIELD)
    before_life = {pid: player.life for pid, player in env._state.players.items()}
    before_library = {pid: list(player.library) for pid, player in env._state.players.items()}
    client, match = game
    identifier = retain(match, env)
    response = client.post(f'/matches/{identifier}/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    queued = http_resolve(client, identifier)
    assert len(queued.stack) == 1
    item = queued.stack[-1]
    assert item.source_card_id == source.id and item.controller == seat
    if name == 'Altar of the Brood':
        assert item.effect_key == 'mill_cards'
        assert item.payload['amount'] == 1 and item.payload['target_player'] == 3-seat
        assert '__unsupported_trigger_instruction' not in item.payload
    else:
        assert item.effect_key == 'noop'
        assert item.payload['__unsupported_trigger_instruction'] == source.oracle_text.split(', ', 1)[1].lower()
    assert item.payload['__trigger_full_clause'] == source.oracle_text.lower()
    assert any('Unsupported entry trigger instruction' in line for line in queued.log) == (name != 'Altar of the Brood')
    assert not queued.pending_trigger_order
    env._state = deepcopy(queued)
    relocate(env._state, source.id, Zone.EXILE)
    retain(restart(identifier), env)
    capture(tmp_path, 'pending', restart(identifier).state)
    final = http_resolve(client, identifier)
    capture(tmp_path, 'resolved', final)
    assert not final.stack
    assert {pid: player.life for pid, player in final.players.items()} == before_life
    expected_library = deepcopy(before_library)
    if name == 'Altar of the Brood':
        milled = expected_library[3-seat].pop()
        assert milled in final.players[3-seat].graveyard
    assert {pid: player.library for pid, player in final.players.items()} == expected_library
    assert not final.cards[info['ninja']].counters
    env._state = deepcopy(restart(identifier).state)
    assert env._state.players[3-seat].hand[0] not in env.observe(seat)['known_cards']


@pytest.mark.parametrize('seat', [1, 2])
def test_complete_compound_unknown_body_does_not_grant_partial_scry_or_counters(tmp_path, seat):
    env, _, _, info = scenario(seat)
    source = raw_card(env._state, POLITICAL, seat, Zone.BATTLEFIELD)
    library = list(env._state.players[seat].library)
    emit_event(env._state, 'enters_battlefield', {'card_id': info['attackers'][0]})
    capture(tmp_path, 'pending', env._state)
    assert len(env._state.stack) == 1
    item = env._state.stack[-1]
    assert item.effect_key == 'noop' and item.source_card_id == source.id and item.controller == seat
    assert item.payload['__unsupported_trigger_instruction'] == POLITICAL['oracle_text'].splitlines()[0].split(', ', 1)[1].lower()
    assert not source.counters and not env._state.pending_trigger_order
    assert not env._state.pending_mechanic_choice
    assert env._state.players[seat].library == library
