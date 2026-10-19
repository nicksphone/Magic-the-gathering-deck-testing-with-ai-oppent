"""Canonical fixture replacement must update the retained printed stock too."""
from copy import deepcopy

import pytest

from game_state.state import Zone
from rules_engine.copiable_values import values
from tests.stack_copy_printed_b720 import SOURCES, canonical_stack_card, set_stack_printed


@pytest.mark.parametrize('name', sorted(SOURCES))
def test_replacing_printed_fixture_data_keeps_the_actual_card_identity(name):
    card = canonical_stack_card('Island', id='retained-card', owner=2,
                                controller=1, zone=Zone.BATTLEFIELD)
    card.counters['+1/+1'] = 3
    card.tapped = True
    card.zone_change_sequence = 4
    physical = (card.id, card.owner, card.controller, card.zone, card.tapped,
                deepcopy(card.counters), card.zone_change_sequence)
    expected = canonical_stack_card(name, id='independent-expectation', owner=1,
                                    controller=2, zone=Zone.HAND)

    set_stack_printed(card, name)

    assert card.characteristic_record == expected.characteristic_record
    assert values(card) == values(expected)
    assert (card.id, card.owner, card.controller, card.zone, card.tapped,
            card.counters, card.zone_change_sequence) == physical
    card.characteristic_record['physical']['keywords'].append('local-alias-probe')
    assert expected.characteristic_record['physical']['keywords'] != card.characteristic_record['physical']['keywords']
