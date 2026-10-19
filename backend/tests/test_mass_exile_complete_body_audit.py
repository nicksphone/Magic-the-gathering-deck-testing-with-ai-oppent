"""Separate canonical complete-tail diagnostic; no claim Sunfall proves other bodies."""
import pytest
from game_state.state import Zone
from tests.test_mass_exile_lifecycle_audit import board, add, cast, resolve


@pytest.mark.parametrize('seat', [1, 2])
def test_full_descend_delirium_exiles_and_creates_printed_angel(seat):
    state, cid, creatures = board(seat, 'Descend upon the Sinful')
    for name in ['Plains', 'Glorious Anthem', 'Llanowar Elves', 'Raise the Alarm']:
        add(state, name, seat, Zone.GRAVEYARD)
    state = resolve(cast(state, seat, cid, 6))
    assert all(state.cards[x].zone == Zone.EXILE for x in creatures)
    angels = [state.cards[x] for x in state.players[seat].battlefield if state.cards[x].name == 'Angel']
    assert len(angels) == 1, 'Complete canonical delirium suffix must not silently resolve exile-only'
    assert angels[0].power == angels[0].toughness == 4
