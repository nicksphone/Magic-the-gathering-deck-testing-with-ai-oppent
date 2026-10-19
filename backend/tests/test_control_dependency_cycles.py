"""Controlled canonical layer-query fixtures; no paid/natural-game certificate.

The three attached Auras include a no-op edge, not a dependency loop (613.8a).
613.8c requires reevaluation after each application. True loops are tested in
test_control_dependency_noop with four alternating controllers.
"""
from itertools import permutations
from game_state.state import assign_static_order_on_battlefield_entry

import pytest

from tests.test_control_layer_contract import metadata_position
from tests.test_static_aura_control_desired import raw_card, ROWS, Zone, snap
from rules_engine.control_effects import control_layer_view


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('entry_order', list(permutations(range(3))))
def test_three_canonical_aura_cycle_noop_edge_and_query_purity(seat, entry_order):
    state, _ = metadata_position(seat)
    owners = [seat, 3-seat, 3-seat]
    cards = {}
    for label in entry_order:
        cards[label] = raw_card(state, ROWS['Confiscate'], owners[label], Zone.BATTLEFIELD)
        assign_static_order_on_battlefield_entry(state, cards[label].id)
    for label in range(3):
        # Explicit internal controlled-board cycle; not fabricated paid actions.
        cards[label].attached_to = cards[(label+1) % 3].id
    stamps = [cards[i].effect_timestamp or cards[i].static_order for i in entry_order]
    assert stamps == sorted(stamps) and len(set(stamps)) == 3
    # Aura 1 does not change Aura 2's controller, so it creates no dependency.
    # The genuine 2 -> 0 -> 1 chain propagates the opposing controller.
    expected = {card.id: 3 - seat for card in cards.values()}
    before = snap(state)
    actual = control_layer_view(state)
    assert {cid: actual[cid] for cid in expected} == expected
    assert snap(state) == before
    assert control_layer_view(state) == actual
    assert snap(state) == before
