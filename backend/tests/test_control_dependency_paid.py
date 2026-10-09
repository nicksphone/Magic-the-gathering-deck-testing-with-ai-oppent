"""Paid canonical Aura-source control dependency, both seats, real detach."""
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
from tests.test_static_aura_control_desired import (
    resource_position, next_main, paid_aura, paid_bounce, controlled,
    receipts, restart, Zone,
)


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_control_of_aura_source_orders_before_its_dependent_effect(seat, receipts):
    state, target = resource_position(seat)
    state = next_main(state, 3-seat)
    state, older = paid_aura(state, 3-seat, target)
    controlled(state, target, 3-seat, receipts, seat)
    state = next_main(state, seat)
    state, newer = paid_aura(state, seat, older)
    controlled(state, older, seat, receipts, 3-seat)
    controlled(state, target, seat, receipts, 3-seat)
    assert state.cards[older].owner == 3-seat
    assert state.cards[older].effect_timestamp < state.cards[newer].effect_timestamp
    assert state.cards[newer].attached_to == older
    assert state.cards[older].attached_to == target
    state = paid_bounce(restart(state), seat, newer)
    controlled(state, older, 3-seat, receipts, seat)
    controlled(state, target, 3-seat, receipts, seat)
    assert state.cards[newer].zone == Zone.HAND
    state = paid_bounce(restart(state), seat, older)
    controlled(state, target, seat, receipts, 3-seat)
    assert state.cards[older].zone == Zone.HAND
    assert state.cards[older].owner == 3-seat
    assert state.cards[target].owner == seat
    restart(state)
