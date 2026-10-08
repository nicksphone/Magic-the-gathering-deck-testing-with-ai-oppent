"""Paid complete loyalty bodies against canonical physical target fixtures."""
import pytest

from game_state.state import Zone
from rules_engine.continuous import has_keyword
import test_brainstorm_desired as brain
from test_emperor_timing_audit import paid_emperor


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restore', [False, True])
@pytest.mark.parametrize('mode', ['counter-and-first-strike', 'exile-and-life'])
def test_actual_paid_complete_targeted_loyalty_bodies(seat, restore, mode):
    state, source = paid_emperor(seat, 'opponent-turn', restore)
    # This is a declared canonical battlefield/tapped-target fixture, not a
    # creature casting or attack qualification. The Emperor cast is real/paid.
    target = brain.add(state, 'Twinshot Sniper', 3 - seat, Zone.BATTLEFIELD)
    before_life = state.players[seat].life
    assert state.cards[target].oracle_text == brain.ROWS['Twinshot Sniper']['oracle_text']
    state.cards[target].tapped = mode == 'exile-and-life'
    state = brain.cold(state) if restore else state
    index = 0 if mode == 'counter-and-first-strike' else 2
    state = brain.act(state, seat, {
        'type': 'activate_loyalty', 'card_id': source, 'ability_index': index,
        'targets': {'target_card_id': target},
    })
    assert state.cards[source].loyalty == (4 if index == 0 else 1)
    frame = next(item.id for item in state.stack if item.source_card_id == source)
    state = brain.advance(state, lambda s: all(item.id != frame for item in s.stack))
    if index == 0:
        assert state.cards[target].zone == Zone.BATTLEFIELD
        assert state.cards[target].counters.get('+1/+1') == 1
        assert has_keyword(state, target, 'first strike')
        assert state.players[seat].life == before_life
    else:
        assert state.cards[target].zone == Zone.EXILE
        assert target in state.players[3 - seat].exile
        assert state.players[seat].life == before_life + 2
    brain.cold(state)
