"""Canonical paid paused resolutions retain public STACK sources, not hidden IDs."""
import pytest

from ai.information import decision_view, is_unknown
from game_state.observations import public_card_ids
from game_state.state import Zone
from tests.test_library_reorder import setup, cast_and_resolve, restore


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Index', 'Ponder'])
def test_paid_popped_source_and_owned_inspection_remain_visible(seat, name):
    state, source = setup(name, seat)
    state = restore(cast_and_resolve(state, source, seat))
    assert state.cards[source.id].zone == Zone.STACK
    assert not any(item.source_card_id == source.id for item in state.stack)
    assert source.id in public_card_ids(state)
    pending = state.pending_mechanic_choice
    assert pending and pending['player_id'] == seat
    inspected = pending['inspected_card_ids']
    for viewer in (1, 2):
        view, _ = decision_view(state, viewer, [])
        assert view.cards[source.id].name == name
        assert view.cards[source.id].oracle_text == state.cards[source.id].oracle_text
        for cid in inspected:
            if viewer == seat:
                assert view.cards[cid].name == state.cards[cid].name
            else:
                assert is_unknown(view.cards[cid])
        assert all(is_unknown(view.cards[cid]) for cid in state.players[3-seat].library)
