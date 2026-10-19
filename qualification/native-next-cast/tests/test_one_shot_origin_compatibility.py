"""Legacy state compatibility is not a canonical next-cast rule certificate."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

import pytest

from effects.handlers import set_next_creature_entry_counter
from game_state.state import Zone
from game_state.serializers import deserialize_match_snapshot
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.continuous import effective_combat_stats
from rules_engine.stack_engine import finish_stack_resolution
from tests.test_graveyard_self_activation_product import position, FAMILIES, raw_card, act, resolve, snapshot
from tests.test_resident_entry_counter_provider import BALLISTA, SEASON, resident
from tests.test_counter_replacements import source as modifier
from test_intrinsic_entry_producer_audit import CARDS


def pending_mixed(seat, family='Walking Ballista', record=None):
    state, _ = position(seat, FAMILIES[0])
    packet = deepcopy(record if record is not None else {
        'controller': seat, 'counter': '+1/+1', 'amount': 1,
        'expires_turn': state.turn, 'legacy_metadata': {'nested': ['preserve', 7]}})
    state.pending_entry_counters = [packet]
    resident(state, SEASON, seat)
    modifier(state, 'Winding Constrictor', seat)
    card = raw_card(state, CARDS[family], seat, Zone.HAND)
    state.players[seat].mana_pool = {'C': 4}
    state.replacement_choice_players = {seat}
    state = resolve(act(state, seat, {'type': 'cast_spell', 'card_id': card.id,
                                    'targets': {'x_value': 2}}))
    return state, card.id, packet


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', CARDS)
def test_actual_paid_mixed_eight_preserves_packet_until_commit(request, seat, family):
    state, cid, packet = pending_mixed(seat, family)
    original = snapshot(state)
    trace = []
    assert state.pending_replacement_choice['counter_payload']['amount'] == 0
    assert {bool(o.get('next_entry_producer')) for o in state.pending_replacement_choice['options']} == {True, False}
    for role in ('one_shot', 'intrinsic', 'adder'):
        state = deserialize_match_snapshot(snapshot(state))
        pending = state.pending_replacement_choice
        assert state.pending_entry_counters == [packet]
        assert state.cards[cid].zone == Zone.STACK
        assert state.cards[cid].counters.get('+1/+1', 0) == 0
        option = next(o for o in pending['options'] if (
            o.get('next_entry_producer') if role == 'one_shot' else
            o.get('intrinsic_entry') if role == 'intrinsic' else
            o['operation'] == 'add' and not o.get('entry_producer')))
        before = snapshot(state)
        action = {'type': 'choose_replacement', 'replacement_source_id': option['source_id']}
        updated = act(state, seat, action)
        assert snapshot(state) == before
        state = updated
        trace.append({'role': role, 'option': deepcopy(option), 'action': action,
                      'before': before, 'after': snapshot(state)})
    assert not state.pending_replacement_choice
    assert state.cards[cid].zone == Zone.BATTLEFIELD
    assert state.cards[cid].counters['+1/+1'] == 8
    assert effective_combat_stats(state, cid) == (8, 8)
    assert state.pending_entry_counters == []
    assert state.players[seat].battlefield.count(cid) == 1
    assert not any(state.players[seat].mana_pool.values())
    assert original['pending_entry_counters'] == [packet]
    target = Path(os.environ['MTG_MIXED_TRACE']) / (
        hashlib.sha256(request.node.nodeid.encode()).hexdigest() + '.json')
    with target.open('x') as stream:
        json.dump({'node': request.node.nodeid, 'family': family, 'seat': seat,
                   'recipient': cid, 'packet_provenance': 'explicit legacy, canonical producer unknown',
                   'original': original, 'choices': trace, 'final': snapshot(state),
                   'final_effective_stats': [8, 8]}, stream, indent=2, sort_keys=True)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('failure', ['packet_amount', 'packet_metadata', 'packet_missing',
    'packet_index', 'receipt_missing', 'recipient_aba', 'frame_id', 'history', 'wrong_actor',
    'consume_index', 'consume_missing'])
def test_stale_pending_packet_is_rejected_before_clear(seat, failure):
    state, cid, _ = pending_mixed(seat)
    payload = state.pending_replacement_choice['counter_payload']
    if failure == 'packet_amount': state.pending_entry_counters[0]['amount'] += 1
    elif failure == 'packet_metadata': state.pending_entry_counters[0]['legacy_metadata']['nested'].append(8)
    elif failure == 'packet_missing': state.pending_entry_counters.clear()
    elif failure == 'packet_index': payload['__next_entry_counter']['index'] += 1
    elif failure == 'receipt_missing': payload.pop('__next_entry_counter')
    elif failure == 'recipient_aba': state.cards[cid].zone_change_sequence += 1
    elif failure == 'frame_id': payload['entry_item']['id'] += ' altered'
    elif failure == 'history': payload['__entry_counter_event']['history'].append({})
    elif failure == 'consume_index': payload['consume_entry_counter'] += 1
    elif failure == 'consume_missing': payload.pop('consume_entry_counter')
    before = snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 3-seat if failure == 'wrong_actor' else seat,
            {'type': 'choose_replacement',
             'replacement_source_id': state.pending_replacement_choice['options'][0]['source_id']})
    assert snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_no_frame_handler_remains_explicit_legacy_and_lossless_defaults(seat):
    state, _ = position(seat, FAMILIES[0])
    set_next_creature_entry_counter(state, seat, {'amount': 1})
    record = deepcopy(state.pending_entry_counters[0])
    assert '__entry_origin' not in record and record['source_card_id'] is None
    for key in ('counter', 'expires_turn', 'source_card_id'):
        record.pop(key)
    record['metadata'] = {'unknown_source': None, 'keep': [1, 2]}
    state, _, retained = pending_mixed(seat, record=record)
    assert state.pending_entry_counters == [record] == [retained]
    assert snapshot(deserialize_match_snapshot(snapshot(state))) == snapshot(state)
    option = next(o for o in state.pending_replacement_choice['options'] if o.get('next_entry_producer'))
    assert 'source_card_id' not in option and option['clause'] is None
    assert 'legacy provenance unknown' in option['name']


@pytest.mark.parametrize('seat', [1, 2])
def test_original_fifo_queue_keeps_unselected_records(seat):
    state, cid, packet = pending_mixed(seat)
    later = {**packet, 'amount': 3}
    state.pending_entry_counters.append(later)
    for _ in range(4):
        if not state.pending_replacement_choice:
            break
        choice = state.pending_replacement_choice
        option = next((o for o in choice['options'] if o.get('next_entry_producer')), choice['options'][0])
        state = act(state, seat, {'type': 'choose_replacement', 'replacement_source_id': option['source_id']})
    assert state.cards[cid].zone == Zone.BATTLEFIELD
    assert state.pending_entry_counters == [later]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('failure', ['counts', 'history', 'completion_missing', 'receipt_missing'])
def test_actual_completion_preflight_rejects_corruption_without_commit(monkeypatch, seat, failure):
    from rules_engine import entry_counters
    original_checker = entry_counters.next_entry_commit_matches
    captured = {}
    def observe(state, item, payload):
        if payload.get('__consume_entry_counter_receipt'):
            captured.update(state=snapshot(state), item=deepcopy(item), payload=deepcopy(payload))
        return original_checker(state, item, payload)
    monkeypatch.setattr(entry_counters, 'next_entry_commit_matches', observe)
    state, cid, packet = pending_mixed(seat)
    for role in ('one_shot', 'intrinsic', 'adder'):
        option = next(o for o in state.pending_replacement_choice['options'] if (
            o.get('next_entry_producer') if role == 'one_shot' else
            o.get('intrinsic_entry') if role == 'intrinsic' else
            o['operation'] == 'add' and not o.get('entry_producer')))
        state = act(state, seat, {'type': 'choose_replacement', 'replacement_source_id': option['source_id']})
    assert state.cards[cid].counters['+1/+1'] == 8
    monkeypatch.setattr(entry_counters, 'next_entry_commit_matches', original_checker)
    resumed = deserialize_match_snapshot(captured['state'])
    payload = captured['payload']
    assert payload['__entry_counter_completion']['__entry_counter_event']['amount'] == 8
    if failure == 'counts': payload['__entry_counters_ready']['+1/+1'] = 9
    elif failure == 'history': payload['__entry_counter_completion']['__entry_counter_event']['history'][-1]['after'] = 9
    elif failure == 'completion_missing': payload.pop('__entry_counter_completion')
    else:
        payload.pop('__consume_entry_counter_receipt')
        payload.pop('__consume_entry_counter')
    before = snapshot(resumed)
    with pytest.raises(ActionRejected):
        finish_stack_resolution(resumed, captured['item'], payload)
    assert snapshot(resumed) == before and resumed.pending_entry_counters == [packet]
