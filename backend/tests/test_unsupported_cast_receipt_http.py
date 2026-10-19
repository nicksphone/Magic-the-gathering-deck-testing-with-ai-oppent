"""Canonical unsupported paid bodies retain receipts, never inferred rewards."""
from copy import deepcopy
import json

import pytest

import main
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from tests.test_multicast_subject_audit import add, position
from tests.test_paid_optional_payment_edges import RAW
from tests.test_paid_optional_triggers import fresh_readonly_restore
from tests.test_spell_trigger_surface_audit import (
    act, cards, install, offline_http, record, restore, snapshot,
)

cards.ROWS.update(RAW)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('foreign_owner', [False, True])
def test_unknown_paid_body_private_http_receipt_restart_and_no_free_copy(
        request, offline_http, seat, foreign_owner):
    state, spell = position(seat)
    source = add(state, 'Mirari', seat)
    source.owner = 3-seat if foreign_owner else seat
    secret = add(state, 'Raging Goblin', 3-seat, Zone.HAND)
    state.players[seat].mana_pool = {'R': 1, 'C': 3}
    state.players[3-seat].mana_pool = {}
    match = install(state, seat, request, private=True)
    action = cards.cast(spell, targets={'target_player': 3-seat})
    response = act(offline_http, match, seat, action)
    assert response.status_code == 200, response.text
    match = restore(state.id)
    items = [item for item in match.state.stack if item.source_card_id == source.id]
    assert len(items) == 1
    receipt = deepcopy(items[0])
    assert receipt.controller == seat and receipt.effect_key == 'noop'
    assert receipt.payload['__trigger_full_clause'] == RAW['Mirari']['oracle_text'].lower()
    assert receipt.payload['__unsupported_trigger_instruction']
    assert receipt.payload['__trigger_event'] == 'spell_cast'
    assert '__optional_payment_cost' not in receipt.payload
    assert not match.state.pending_trigger_order
    assert match.state.players[seat].mana_pool.get('C') == 3
    fresh_readonly_restore(match)
    frozen = snapshot(match)
    bad = {'type': 'choose_optional_effect', 'stack_id': receipt.id, 'accept': True}
    response = act(offline_http, match, seat, bad)
    assert response.status_code == 422 and snapshot(match) == frozen
    response = act(offline_http, match, 3-seat, bad)
    assert response.status_code == 403 and snapshot(match) == frozen
    public = main._serialize_match_controller(match)
    assert secret.id not in json.dumps(public) and public['root_seed'] is None
    queued = serialize_match_snapshot(match.state)
    trace = []
    for _ in range(16):
        match = restore(state.id)
        trace.append(serialize_match_snapshot(match.state))
        assert not match.state.pending_trigger_order
        assert not any(item.payload.get('__stack_copy_kind') for item in match.state.stack)
        if not match.state.stack:
            break
        actor = match.state.priority_player
        response = (offline_http.post('/matches/' + state.id + '/autoplay?ticks=1')
                    if match.controllers[actor] == 'ai' else
                    act(offline_http, match, actor, {'type': 'pass_priority'}))
        assert response.status_code == 200, response.text
    else:
        pytest.fail('Unsupported noop and ordinary spell did not finish in16 HTTP transitions')
    assert match.state.players[seat].mana_pool.get('C') == 3
    assert match.state.players[3-seat].life == 18
    assert match.state.cards[source.id].controller == seat
    assert match.state.cards[source.id].owner == source.owner
    assert any('Unsupported optional trigger payment' in row for row in match.state.log)
    fresh_readonly_restore(match)
    record(request, {'canonical': RAW['Mirari'], 'receipt': vars(receipt),
                     'queued': queued, 'trace': trace, 'public': public,
                     'resolved': serialize_match_snapshot(match.state)})
