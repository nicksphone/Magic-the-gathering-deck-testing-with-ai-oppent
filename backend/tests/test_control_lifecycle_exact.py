"""Review controls: paid reentry and explicit legacy-admission fault probes."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
from tests.test_static_aura_control_desired import (
    resource_position, raw_card, COMBAT, cast, next_main, restart,
    completed_cleanup, snap, Zone, paid_aura,
)
from rules_engine.control_effects import record_control_effect
from game_state.serializers import deserialize_match_snapshot

FIXTURES = ROOT / 'backend/tests/fixtures'
DOMINATE = json.loads((FIXTURES / 'temporary_control_handler_correction/dominate.json').read_bytes())
RAY = json.loads((FIXTURES / 'temporary_control_audit/ray-of-command.json').read_bytes())
BLINK = json.loads((FIXTURES / 'temporary_control_audit/cloudshift.json').read_bytes())
PLAINS = json.loads((FIXTURES / 'activated_top_selection/plains.json').read_bytes())


def paid_temporary_position(seat):
    state, _ = resource_position(seat)
    for _ in range(2):
        raw_card(state, PLAINS, seat, Zone.BATTLEFIELD)
    target = raw_card(state, COMBAT['Grizzly Bears'], seat, Zone.HAND)
    state = cast(state, seat, target.id)
    state = next_main(state, 3-seat)
    dominate = raw_card(state, DOMINATE, 3-seat, Zone.HAND)
    state = cast(state, 3-seat, dominate.id, {'target_card_id': target.id, 'x_value': 2},
                 cost_choice={'id': 'base'})
    assert state.cards[target.id].controller == 3-seat
    state = next_main(state, seat)
    ray = raw_card(state, RAY, seat, Zone.HAND)
    state = cast(state, seat, ray.id, {'target_card_id': target.id}, cost_choice={'id': 'base'})
    assert state.cards[target.id].controller == seat
    assert state.cards[target.id].owner == seat
    return state, target.id


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_indefinite_ray_owner_blink_cold_restore_cleanup(seat):
    state, target = paid_temporary_position(seat)
    old_sequence = state.cards[target].zone_change_sequence
    old_incarnation = state.cards[target].battlefield_incarnation
    old_delay = deepcopy(state.delayed_triggers)
    assert old_delay[-1]['payload']['incarnation'] == old_incarnation
    assert old_delay[-1]['payload']['zone_change_sequence'] == old_sequence
    state = restart(state)
    blink = raw_card(state, BLINK, seat, Zone.HAND)
    state = cast(state, seat, blink.id, {'target_card_id': target})
    assert state.cards[target].zone_change_sequence == old_sequence + 2
    assert state.cards[target].battlefield_incarnation != old_incarnation
    assert state.cards[target].controller == state.cards[target].owner == seat
    assert state.cards[target].control_effect_base is None
    assert state.cards[target].control_effects == []
    assert state.cards[target].last_known_battlefield == {}, 'New object must not inherit old LBF'
    assert not any(d['payload'].get('incarnation') == state.cards[target].battlefield_incarnation for d in state.delayed_triggers if d['effect_key'] == 'control_loss_tap')
    state = completed_cleanup(restart(state))
    assert state.cards[target].controller == seat, 'Old incarnation temporary cache must not steal fresh owner entry'
    assert target in state.players[seat].battlefield
    assert target not in state.players[3-seat].battlefield
    assert state.cards[target].summoning_sick
    assert not state.cards[target].tapped, 'Old Ray delayed reference must not tap fresh object'
    assert target not in state.temporary_control_changes
    restart(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_legacy_contest_recorder_failure_does_not_half_mutate_root(seat):
    state, target = paid_temporary_position(seat)
    state, _ = paid_aura(state, seat, target)
    # Deliberate old-snapshot compatibility probe, not a lawful gameplay action.
    state.cards[target].control_effect_base = None
    state.cards[target].control_effects = []
    other = raw_card(state, COMBAT['Grizzly Bears'], seat, Zone.BATTLEFIELD)
    before = snap(state)
    with pytest.raises(ValueError):
        record_control_effect(state, other, 3-seat)
    assert snap(state) == before, 'Legacy rejection must precede baseline/clock/ledger mutation'


@pytest.mark.parametrize('seat', [1, 2])
def test_unscoped_legacy_control_snapshot_rejected_without_input_mutation(seat):
    state, target = paid_temporary_position(seat)
    legacy = deepcopy(snap(state))
    legacy['cards'][target].pop('control_effect_base')
    legacy['cards'][target].pop('control_effects')
    # The old version had neither retained target reference nor a duration ledger.
    legacy['temporary_control_changes'][target] = {
        key: legacy['temporary_control_changes'][target][key]
        for key in ('controller', 'expires_turn')
    }
    before = deepcopy(legacy)
    with pytest.raises(ValueError):
        deserialize_match_snapshot(legacy)
    assert legacy == before
