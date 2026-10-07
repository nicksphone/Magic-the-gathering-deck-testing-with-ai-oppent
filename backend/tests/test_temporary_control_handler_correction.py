"""Paid control instructions; no SQL, sockets, fabricated effects or stack items."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from game_state.state import Zone
from tests.test_temporary_control_lifecycle_audit import (
    position, cast, act, passes, advance, raw_card, restart, assert_private, ROWS,
)
from tests.test_generic_protection_damage import CANONICAL
from tests.test_temporary_control_delayed_product import no_sqlite_or_network

DOMINATE = json.loads((Path(__file__).parent / 'fixtures/temporary_control_handler_correction/dominate.json').read_text())
TWINCAST = json.loads((Path(__file__).parent / 'fixtures/coupled_targets/twincast.json').read_text())
COUNTERSPELL = json.loads((Path(__file__).parent / 'fixtures/trigger_instruction_product/counterspell.json').read_text())


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('first_ray', [False, True])
def test_paid_indefinite_control_has_no_expired_temporary_cache(seat, first_ray, tmp_path):
    state, ray, target = position(seat, 'ray-of-command')
    dominate = raw_card(state, DOMINATE, seat, Zone.HAND).id
    state.players[seat].mana_pool = {'C': 6, 'U': 3}
    if first_ray:
        state = passes(cast(state, seat, ray, target))
        saved = deepcopy(state.delayed_triggers)
    else:
        saved = []
    state = act(state, seat, {'type': 'cast_spell', 'card_id': dominate,
                             'cost_choice': {'id': 'base'},
                             'targets': {'target_card_id': target, 'x_value': 2}})
    assert state.stack[-1].payload['mana_spent'] == 5
    state = passes(state)
    assert state.cards[target].controller == seat
    assert not state.temporary_control_changes
    assert state.delayed_triggers == saved and not state.stack
    state = advance(restart(state, tmp_path, 'indefinite'))
    assert state.cards[target].controller == seat
    assert state.delayed_triggers == saved and not state.stack
    assert_private(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_retained_ray_record_waits_for_real_future_control_loss(seat, tmp_path):
    state, ray, target = position(seat, 'ray-of-command')
    dominate = raw_card(state, DOMINATE, seat, Zone.HAND).id
    other_ray = raw_card(state, ROWS['ray-of-command'], 3-seat, Zone.HAND).id
    state.players[seat].mana_pool = {'C': 6, 'U': 3}
    state.players[3-seat].mana_pool = {'C': 3, 'U': 1}
    state = passes(cast(state, seat, ray, target))
    saved = deepcopy(state.delayed_triggers)
    state = act(state, seat, {'type': 'cast_spell', 'card_id': dominate,
                             'cost_choice': {'id': 'base'},
                             'targets': {'target_card_id': target, 'x_value': 2}})
    state = passes(state)
    assert state.delayed_triggers == saved and not state.stack
    state = act(state, state.priority_player, {'type': 'pass_priority'})
    state = passes(cast(state, 3-seat, other_ray, target))
    assert state.cards[target].controller == 3-seat
    trigger = state.stack[-1]
    assert trigger.effect_key == 'control_loss_tap' and trigger.controller == seat
    assert trigger.source_card_id == ray
    state = passes(restart(state, tmp_path, 'actual-future-loss'))
    assert state.cards[target].tapped
    assert all(record['source_card_id'] != ray for record in state.delayed_triggers)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('opposite', [False, True])
@pytest.mark.parametrize('counter_original', [False, True])
def test_actual_copy_controller_not_inherited_original_caster(seat, opposite, counter_original, tmp_path):
    copier = 3-seat if opposite else seat
    state, ray, target = position(seat, 'ray-of-command')
    alternative = raw_card(state, CANONICAL['White Knight'], seat if opposite else 3-seat, Zone.BATTLEFIELD).id
    twincast = raw_card(state, TWINCAST, copier, Zone.HAND).id
    counter = raw_card(state, COUNTERSPELL, 3-seat, Zone.HAND).id
    state.players[seat].mana_pool = {'C': 3, 'U': 3 if copier == seat else 1}
    state.players[3-seat].mana_pool = {'U': 4 if opposite else 2}
    state = cast(state, seat, ray, target)
    original_id = state.stack[-1].id
    if opposite:
        state = act(state, seat, {'type': 'pass_priority'})
    state = act(state, copier, {'type': 'cast_spell', 'card_id': twincast,
                               'cost_choice': {'id': 'base'},
                               'targets': {'target_stack_id': original_id}})
    assert state.stack[-1].payload['mana_spent'] == 2
    state = passes(state)
    selected = 'target_card_id:' + alternative if opposite else 'keep'
    assert selected in state.pending_mechanic_choice['options']
    state = act(state, copier, {'type': 'choose_mechanic', 'card_ids': [selected]})
    copied_id = state.stack[-1].id
    assert copied_id != original_id and state.stack[-1].controller == copier
    chosen = alternative if opposite else target
    if counter_original:
        if state.priority_player != 3-seat:
            state = act(state, state.priority_player, {'type': 'pass_priority'})
        state = act(state, 3-seat, {'type': 'cast_spell', 'card_id': counter,
                                  'cost_choice': {'id': 'base'},
                                  'targets': {'target_stack_id': original_id}})
        state = passes(state)
        assert state.cards[ray].zone == Zone.GRAVEYARD
        assert state.stack[-1].id == copied_id
    state = passes(restart(state, tmp_path, 'actual-copied-resolution'))
    assert state.cards[chosen].controller == copier
    assert state.delayed_triggers[-1]['controller'] == copier
    assert_private(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_act_route_retains_temporary_expiry(seat):
    state, spell, target = position(seat, 'act-of-treason')
    state = passes(cast(state, seat, spell, target))
    assert state.cards[target].controller == seat
    assert state.temporary_control_changes[target]['controller'] == 3-seat
    state = advance(state)
    assert state.cards[target].controller == 3-seat
    assert not state.temporary_control_changes
