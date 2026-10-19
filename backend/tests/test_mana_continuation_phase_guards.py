"""Desired typed private-frame and payment-query boundaries."""
from copy import deepcopy

import pytest

from game_state.copying import copy_match_state
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from rules_engine.action_validation import ActionRejected
from rules_engine.mana_continuation import activation_outcomes
from tests.test_forge_human_replacement_order import act, fingerprint, setup
from tests.test_linked_mana_damage import request


@pytest.mark.parametrize('seat', [1, 2])
def test_copied_payment_choice_trials_do_not_run_mid_payment_sba(seat, monkeypatch):
    state, sources, _, _ = setup(seat)
    before = fingerprint(state)
    from rules_engine import state_based_actions
    original = state_based_actions.apply_state_based_actions
    calls = []

    def observe(candidate):
        calls.append(candidate)
        return original(candidate)

    monkeypatch.setattr(state_based_actions, 'apply_state_based_actions', observe)
    outcomes = list(activation_outcomes(copy_match_state(state), seat, sources[0], 1, 'W'))
    assert len(outcomes) == 2
    assert calls == [], 'copied feasibility must not insert an SBA inside an unpaid cost'
    assert fingerprint(state) == before
    assert all(s.players[seat].mana_pool['W'] == 1 for s in outcomes)


@pytest.mark.parametrize('mutation', [
    'turn_bool', 'cursor_bool', 'payer_bool', 'stage_type', 'bonus_cursor_bool',
    'malformed_bonus', 'waiting_incarnation', 'unknown_priority',
])
def test_restore_rejects_typed_or_binding_corruption_of_genuine_pause(mutation):
    state, sources, _, _ = setup(1)
    state = act(state, 1, request(state.cards[sources[0]], 'W'))
    snapshot = deepcopy(serialize_match_snapshot(state))
    frame = snapshot['mana_continuation']
    if mutation == 'turn_bool':
        frame['origin']['turn'] = True
    elif mutation == 'cursor_bool':
        frame['origin']['phase_cursor'] = False
    elif mutation == 'payer_bool':
        frame['frames'][0]['payer'] = True
    elif mutation == 'stage_type':
        frame['frames'][0]['stage']['owned'] = 'yes'
    elif mutation == 'bonus_cursor_bool':
        frame['frames'][-1]['bonus_cursor'] = False
    elif mutation == 'malformed_bonus':
        frame['frames'][-1]['captured_bonus'] = [['junk']]
    elif mutation == 'waiting_incarnation':
        frame['waiting']['source']['incarnation'] += 1
    else:
        frame['frames'][0]['data']['return_priority'] = 3
    before = fingerprint(state)
    with pytest.raises((ValueError, ActionRejected)):
        deserialize_match_snapshot(snapshot)
    assert fingerprint(state) == before
