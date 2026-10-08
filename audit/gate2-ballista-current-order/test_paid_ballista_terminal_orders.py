"""Actual paid X=2 entry orders, not a historical intermediate observation."""
from copy import deepcopy

import pytest

from game_state.serializers import deserialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from tests.test_graveyard_self_activation_product import act, resolve, snapshot
from test_intrinsic_entry_producer_audit import announced, CARDS, record


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restore', [False, True])
@pytest.mark.parametrize('second,expected', [('modifier', 5), ('resident', 6)])
def test_actual_paid_ballista_intrinsic_then_ordered_residents_terminal(
        seat, restore, second, expected, request):
    state, cid, provider, before = announced(seat, 'Walking Ballista', True)
    assert state.stack[-1].payload['mana_spent'] == 4
    assert state.stack[-1].payload['x_value'] == 2
    assert state.cards[cid].oracle_text == CARDS['Walking Ballista']['oracle_text']
    state = resolve(state)
    initial = snapshot(state)
    assert state.pending_replacement_choice['counter_payload']['amount'] == 0
    assert {o['source_card_id'] for o in state.pending_replacement_choice['options']} == {cid, provider}
    choices = []
    consumed = None
    for role in ('intrinsic', second):
        if restore:
            state = deserialize_match_snapshot(snapshot(state))
        pending = state.pending_replacement_choice
        assert pending and pending['player_id'] == seat
        assert state.cards[cid].zone == Zone.STACK
        assert state.cards[cid].counters.get('+1/+1', 0) == 0
        option = next(o for o in pending['options'] if (
            'intrinsic' if o.get('intrinsic_entry') else
            'resident' if o.get('entry_producer') else 'modifier') == role)
        current = snapshot(state)
        for actor, source in ((3-seat, option['source_id']),
                              (seat, consumed or 'not-an-actual-source')):
            with pytest.raises(ActionRejected):
                checked_action(state, RulesEngine(), actor,
                    {'type': 'choose_replacement', 'replacement_source_id': source})
            assert snapshot(state) == current
        choices.append({'role': role, 'pending': deepcopy(pending),
                        'invalid_and_stale_root_equal': True})
        consumed = option['source_id']
        state = act(state, seat, {'type': 'choose_replacement',
                                 'replacement_source_id': consumed})
    assert not state.pending_replacement_choice and not state.pending_mechanic_choice
    assert not state.stack
    assert state.cards[cid].zone == Zone.BATTLEFIELD
    assert state.cards[cid].counters['+1/+1'] == expected
    assert state.players[seat].battlefield.count(cid) == 1
    assert state.cards[cid].owner == state.cards[cid].controller == seat
    assert state.cards[cid].oracle_text == CARDS['Walking Ballista']['oracle_text']
    assert not any(state.players[seat].mana_pool.values())
    record(request, before=before, actual_initial=initial, choices=choices,
           actual_terminal=snapshot(state), expected_counters=expected,
           scope='paid intrinsic-first X2 Ballista exact resident/modifier orders')
