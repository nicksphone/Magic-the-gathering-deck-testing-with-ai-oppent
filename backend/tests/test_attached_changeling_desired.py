"""Printed changeling must not override a later real attached subtype replacement."""
import pytest

import test_suncleanser_desired as s
from test_attached_characteristic_goldens import expanded, facts, paid
from rules_engine.library_permissions import creature_types
from rules_engine.land_types import effective_type_line


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restore', [False, True])
def test_paid_changeling_later_frogify_has_only_replaced_creature_subtype(expanded, seat, restore):
    state = s.g.position(expanded, seat)
    state, target = paid(state, expanded, seat, 'Universal Automaton', {'C': 1})
    assert {'frog', 'thopter', 'human'} <= creature_types(state.cards[target], state)
    state, aura = paid(state, expanded, seat, 'Frogify', {'C': 1, 'U': 1}, target)
    state = s.cold(state) if restore else state
    assert state.cards[aura].attached_to == target
    actual = creature_types(state.cards[target], state)
    line = effective_type_line(state, state.cards[target])
    s.record(f'changeling-{seat}-{restore}', state, actual_subtypes=sorted(actual), actual_type_line=line)
    assert line.endswith('Frog')
    assert actual == {'frog'}, 'printed CDA cannot re-add every subtype after layer-four attached replacement'
