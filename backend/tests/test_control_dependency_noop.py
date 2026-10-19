"""Canonical controlled layer queries, not paid attachment episodes."""
import pytest
from itertools import permutations

from game_state.state import (allocate_effect_timestamp,
                             assign_static_order_on_battlefield_entry,
                             object_incarnation)
from rules_engine.control_effects import control_layer_view
from tests.test_control_layer_contract import metadata_position
from tests.test_static_aura_control_desired import raw_card, ROWS, Zone, snap


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('changes_source_controller', [False, True])
def test_source_control_dependency_requires_actual_change(seat, changes_source_controller):
    state, target = metadata_position(seat)
    source_controller = 3 - seat if changes_source_controller else seat
    older = raw_card(state, ROWS['Confiscate'], seat, Zone.BATTLEFIELD)
    middle = raw_card(state, ROWS['Confiscate'], 3 - source_controller, Zone.BATTLEFIELD)
    newer = raw_card(state, ROWS['Confiscate'], source_controller, Zone.BATTLEFIELD)
    for aura in (older, middle, newer):
        assign_static_order_on_battlefield_entry(state, aura.id)
    older.attached_to = middle.attached_to = target
    newer.attached_to = older.id
    assert older.effect_timestamp < middle.effect_timestamp < newer.effect_timestamp
    before = snap(state)
    actual = control_layer_view(state)
    assert actual[older.id] == source_controller
    assert actual[target] == 3 - seat
    assert control_layer_view(state) == actual
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_dependency_loop_oldest_waits_for_external_prerequisites(seat):
    state, _ = metadata_position(seat)
    owners = [seat, 3 - seat, seat, 3 - seat]
    cards = []
    for owner in owners:
        card = raw_card(state, ROWS['Confiscate'], owner, Zone.BATTLEFIELD)
        assign_static_order_on_battlefield_entry(state, card.id)
        cards.append(card)
    for index, card in enumerate(cards):
        card.attached_to = cards[(index + 1) % 4].id
    for card, controller in ((cards[0], 3 - seat), (cards[1], seat)):
        card.control_effect_base = card.controller
        card.control_effects.append({
            'controller': controller,
            'timestamp': allocate_effect_timestamp(state),
            'incarnation': object_incarnation(card),
            'sequence': card.zone_change_sequence,
        })
    before = snap(state)
    actual = control_layer_view(state)
    # The loop's oldest effect cannot be overtaken while it waits on X.
    # Applying X, A, Y, B, C, D propagates the underlying first controller.
    assert [actual[card.id] for card in cards] == [seat] * 4
    assert control_layer_view(state) == actual
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('entry_order', list(permutations(range(4))))
def test_four_alternating_aura_dependencies_reevaluate_after_first_effect(seat, entry_order):
    state, _ = metadata_position(seat)
    owners = [seat, 3 - seat, seat, 3 - seat]
    cards = {}
    for label in entry_order:
        cards[label] = raw_card(state, ROWS['Confiscate'], owners[label], Zone.BATTLEFIELD)
        assign_static_order_on_battlefield_entry(state, cards[label].id)
    for label in range(4):
        cards[label].attached_to = cards[(label + 1) % 4].id
    before = snap(state)
    actual = control_layer_view(state)
    # All four initial dependencies change a controller. The oldest breaks
    # the loop; reevaluating the remaining chain propagates that controller.
    expected = {card.id: owners[entry_order[0]] for card in cards.values()}
    assert {cid: actual[cid] for cid in expected} == expected
    assert control_layer_view(state) == actual
    assert snap(state) == before
