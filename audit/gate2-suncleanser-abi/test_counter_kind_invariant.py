"""Predicate invariant on real paid frames; not all producer execution proof."""
from pathlib import Path

import pytest
import inventory as inv
import test_suncleanser_desired as s
import test_paid_modal as m
import training.environment as training
from rules_engine.counter_placement import counter_placement_forbidden

facts = s.facts
KINDS = ('+1/+1', '-1/-1', 'poison', 'loyalty', 'lore', 'stun', 'shield', 'experience', 'energy')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('mode', ['creature', 'player'])
def test_all_kinds_share_actual_paid_duration_predicate(facts, seat, mode):
    assert Path(training.__file__).resolve() == inv.ROOT / 'backend/training/environment.py'
    state, source, target = m.resolved(facts, seat, mode)
    query = {'target_card_id': target} if mode == 'creature' else {'target_player': target}
    assert all(counter_placement_forbidden(s.cold(state), kind, **query) for kind in KINDS)
    state, _ = s.paid(state, facts, seat, 'Long Goodbye', {'C': 1, 'B': 1}, target_card_id=source)
    assert state.cards[source].zone == s.Zone.GRAVEYARD
    assert all(not counter_placement_forbidden(s.cold(state), kind, **query) for kind in KINDS)
    s.record('predicate-kinds-' + mode + '-' + str(seat), state,
             kinds=list(KINDS), qualification='predicate only; not execution of all nine producers')
