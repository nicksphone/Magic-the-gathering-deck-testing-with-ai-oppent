"""Separate strict ledger: an existing static protection seam, NOT shuffle scope."""
import pytest

from game_state.state import Zone
from rules_engine.continuous import effective_keywords
from tests.test_shuffle_observer_audit import prepare, order_prompt, finish
from tests.test_shuffle_observer_resolution import EXTRA
from tests.test_linked_damage_targets import raw_card


@pytest.mark.parametrize('seat', [1, 2])
def test_canonical_absolute_law_static_protection_gap(seat):
    state, spell, source = prepare('Ponder', seat, "Cosi's Trickster")
    raw_card(state, EXTRA['Absolute Law'], 3-seat, Zone.BATTLEFIELD)
    state = finish(order_prompt(state, seat, spell), seat, 'shuffle')
    assert 'protection from red' in effective_keywords(state, source)
