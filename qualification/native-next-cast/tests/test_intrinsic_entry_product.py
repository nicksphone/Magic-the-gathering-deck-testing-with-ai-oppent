"""Pure checked paid-entry qualification; no fabricated executable packets."""
from copy import deepcopy
import itertools
import json
from pathlib import Path

import pytest

from game_state.serializers import deserialize_match_snapshot
from game_state.state import Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.continuous import printed_abilities_suppressed
from rules_engine.entry_counters import (
    intrinsic_x_entry_instruction, prospective_entry_ability_view)
from tests.test_graveyard_self_activation_product import act, resolve, snapshot, raw_card
from tests.test_resident_entry_counter_provider import resident, RENATA, SEASON
from test_intrinsic_entry_producer_audit import announced, CARDS, record


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', CARDS)
def test_all_actual_entry_orders_keep_one_event_and_restore(request, seat, family):
    initial, cid, provider, _ = announced(seat, family, True)
    initial = resolve(initial)
    pending = initial.pending_replacement_choice
    assert pending['counter_payload']['amount'] == 0
    assert initial.cards[cid].zone == Zone.STACK
    assert initial.cards[cid].counters.get('+1/+1', 0) == 0
    assert {option['source_card_id'] for option in pending['options']} == {cid, provider}
    initial_bytes = snapshot(initial)
    outcomes = []
    traces = []
    for order in itertools.permutations(['intrinsic', 'resident', 'modifier']):
        state = deserialize_match_snapshot(initial_bytes)
        selected = []
        choices = []
        valid = True
        for role in order:
            choice = state.pending_replacement_choice
            if choice is None:
                break  # Native sole replacement has already been applied.
            options = choice['options']
            candidate = next((option for option in options if (
                'intrinsic' if option.get('intrinsic_entry') else
                'resident' if option.get('entry_producer') else 'modifier') == role), None)
            if candidate is None:
                valid = False
                break
            payload = choice['counter_payload']
            choices.append(deepcopy(choice))
            event = payload['__entry_counter_event']
            assert event['applied_ids'] == payload['__counter_used']
            assert len(event['applied_ids']) == len(set(event['applied_ids']))
            assert state.cards[cid].zone == Zone.STACK
            assert state.cards[cid].counters.get('+1/+1', 0) == 0
            selected.append(candidate['source_id'])
            state = act(state, seat, {'type': 'choose_replacement',
                                      'replacement_source_id': candidate['source_id']})
            state = deserialize_match_snapshot(snapshot(state))
        if not valid:
            continue
        assert not state.pending_replacement_choice
        assert state.cards[cid].zone == Zone.BATTLEFIELD
        assert state.players[seat].battlefield.count(cid) == 1
        assert state.cards[cid].oracle_text == CARDS[family]['oracle_text']
        assert not any(state.players[seat].mana_pool.values())
        assert len(selected) == len(set(selected))
        outcomes.append(state.cards[cid].counters['+1/+1'])
        traces.append({'requested_order': list(order), 'choices': choices,
                       'selected_ids': selected, 'after': snapshot(state)})
    assert sorted(outcomes) == [4, 5, 6, 6]
    assert snapshot(initial) == initial_bytes
    record(request, before=initial_bytes, traces=traces, counters=outcomes,
           scope='checked original-event orders for two canonical surfaces only')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', CARDS)
@pytest.mark.parametrize('humility', [False, True])
def test_native_prospective_suppression_is_pure_and_no_resurrection(seat, family, humility):
    state, cid, _, _ = announced(seat, family, False)
    if humility:
        from tests import test_graveyard_self_activation_product as native_fixture
        rows = json.loads((Path(native_fixture.__file__).parent /
                           'fixtures/ability_suppression.json').read_text())
        row = next(row for row in rows if row['name'] == 'Humility')
        source = raw_card(state, row, 3-seat, Zone.BATTLEFIELD)
        assign_static_order_on_battlefield_entry(state, source.id)
    before = snapshot(state)
    card = state.cards[cid]
    assert not printed_abilities_suppressed(state, cid)
    view = prospective_entry_ability_view(state, card, seat)
    assert view['printed_suppressed'] == humility
    assert 'Creature' in view['types']
    assert snapshot(state) == before and state.cards[cid] is card
    state = resolve(state)
    if humility:
        assert not state.pending_replacement_choice
        assert state.cards[cid].zone == Zone.BATTLEFIELD
        assert state.cards[cid].counters.get('+1/+1', 0) == 0
    else:
        assert state.pending_replacement_choice['counter_payload']['amount'] == 0


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('failure', ['locked_x', 'frame_x', 'clause', 'recipient_aba',
    'resident_aba', 'event_id', 'history', 'amount', 'used', 'wrong_actor',
    'intrinsic_missing', 'event_missing', 'extra_modifier', 'boolean_x',
    'frame_identity', 'announced_x'])
def test_pending_self_and_event_proofs_reject_atomically(seat, failure):
    state, cid, provider, _ = announced(seat, 'Walking Ballista', True)
    state = resolve(state)
    state = deserialize_match_snapshot(snapshot(state))
    payload = state.pending_replacement_choice['counter_payload']
    proof = payload['__intrinsic_entry_counter']
    if failure == 'locked_x': proof['locked_x'] += 1
    elif failure == 'frame_x': payload['entry_item']['payload']['x_value'] += 1
    elif failure == 'clause': state.cards[cid].oracle_text = state.cards[cid].oracle_text.replace(
        'This creature enters with X +1/+1 counters on it.',
        'This creature enters with X +1/+1 counters on it. Draw a card.')
    elif failure == 'recipient_aba': state.cards[cid].zone_change_sequence += 1
    elif failure == 'resident_aba': state.cards[provider].zone_change_sequence += 1
    elif failure == 'event_id': payload['__entry_counter_event']['event_id'] += ' forged'
    elif failure == 'history': payload['__entry_counter_event']['history'].append({})
    elif failure == 'amount': payload['amount'] = 2
    elif failure == 'used': payload['__counter_used'] = ['forged']
    elif failure == 'intrinsic_missing': payload.pop('__intrinsic_entry_counter')
    elif failure == 'event_missing': payload.pop('__entry_counter_event')
    elif failure == 'extra_modifier': payload['__counter_entry_modifiers'].append({
        'source_id': 'forged', 'source_card_id': cid, 'name': 'forged', 'operation': 'add', 'operand': 99})
    elif failure == 'boolean_x': proof['locked_x'] = True
    elif failure == 'frame_identity': payload['entry_item']['id'] += ' forged'
    elif failure == 'announced_x': payload['entry_item']['payload']['__announced_targets']['x_value'] += 1
    before = snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 3-seat if failure == 'wrong_actor' else seat,
            {'type': 'choose_replacement',
             'replacement_source_id': state.pending_replacement_choice['options'][0]['source_id']})
    assert snapshot(state) == before


@pytest.mark.parametrize('tail', [' Draw a card.', ' if you gained life.', ' instead.', '\nextra'])
def test_intrinsic_full_clause_rejects_unknown_tails(tail):
    assert intrinsic_x_entry_instruction('This creature enters with X +1/+1 counters on it.')
    assert not intrinsic_x_entry_instruction('This creature enters with X +1/+1 counters on it.' + tail)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', CARDS)
def test_standalone_intrinsic_is_forced_with_no_bf_self_receipt(seat, family):
    state, cid, provider, _ = announced(seat, family, False)
    source = state.cards[provider]
    state.players[seat].battlefield.remove(provider)
    source.move_to_zone(Zone.EXILE)
    state.players[source.owner].exile.append(provider)
    state = resolve(state)
    assert not state.pending_replacement_choice
    assert state.cards[cid].zone == Zone.BATTLEFIELD
    assert state.cards[cid].counters['+1/+1'] == 2


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', CARDS)
def test_zero_x_is_not_a_positive_producer(seat, family):
    from tests.test_graveyard_self_activation_product import position, FAMILIES
    state, _ = position(seat, FAMILIES[0])
    resident(state, RENATA, seat)
    card = raw_card(state, CARDS[family], seat, Zone.HAND)
    state.players[seat].mana_pool = {}
    state = resolve(act(state, seat, {'type': 'cast_spell', 'card_id': card.id,
                                     'targets': {'x_value': 0}}))
    assert not state.pending_replacement_choice
    assert state.cards[card.id].zone == Zone.BATTLEFIELD
    assert state.cards[card.id].counters['+1/+1'] == 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('failure', ['history_after', 'history_order', 'history_used', 'locked_x'])
def test_resumed_history_is_validated_before_pending_clear(seat, failure):
    state, cid, _, _ = announced(seat, 'Walking Ballista', True)
    state = resolve(state)
    intrinsic = next(option for option in state.pending_replacement_choice['options']
                     if option.get('intrinsic_entry'))
    state = act(state, seat, {'type': 'choose_replacement',
                             'replacement_source_id': intrinsic['source_id']})
    state = deserialize_match_snapshot(snapshot(state))
    payload = state.pending_replacement_choice['counter_payload']
    event = payload['__entry_counter_event']
    assert payload['amount'] == event['amount'] == 2
    assert len(event['history']) == 1 and event['history'][0]['role'] == 'intrinsic'
    assert state.cards[cid].zone == Zone.STACK
    if failure == 'history_after': event['history'][0]['after'] = 3
    elif failure == 'history_order': event['history'][0]['before'] = 1
    elif failure == 'history_used': event['applied_ids'] = []
    else: payload['__intrinsic_entry_counter']['locked_x'] = 3
    before = snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'choose_replacement',
            'replacement_source_id': state.pending_replacement_choice['options'][0]['source_id']})
    assert snapshot(state) == before
