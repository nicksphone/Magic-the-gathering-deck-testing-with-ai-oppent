"""Birth-only stock-preserving blocker variant; Battle is always really cast."""
from game_state.state import Zone, assign_static_order_on_battlefield_entry
from tests.battle_payment_browser_fixture import midgame


def routing_midgame(seat, *, blocked=False):
    state, ids = midgame(seat)
    blocker = None
    if blocked:
        player = state.players[3-seat]
        blocker = next(cid for cid in player.library if state.cards[cid].name == "Grizzly Bears")
        player.library.remove(blocker)
        card = state.cards[blocker]
        card.move_to_zone(Zone.BATTLEFIELD)
        player.battlefield.append(blocker)
        assign_static_order_on_battlefield_entry(state, blocker)
        card.summoning_sick = False
    return state, {**ids, "blocker": blocker}
