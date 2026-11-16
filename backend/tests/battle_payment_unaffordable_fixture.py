"""Unfunded declared midgame variant; debt is created later by real Pact play."""
from game_state.state import Zone
from tests.battle_payment_browser_fixture import midgame


def unaffordable_midgame(seat):
    state, ids = midgame(seat)
    player = state.players[seat]
    # Fixture birth only, not a claimed played land-removal history. Preserve all
    # canonical objects/deck stock and let the zero-cost Pact work normally.
    for cid in list(player.battlefield):
        card = state.cards[cid]
        if card.name == 'Forest':
            player.battlefield.remove(cid)
            card.move_to_zone(Zone.LIBRARY)
            player.library.append(cid)
    state.log.append('Declared canonical midgame variant: no funded sources for the next Pact upkeep.')
    return state, ids
