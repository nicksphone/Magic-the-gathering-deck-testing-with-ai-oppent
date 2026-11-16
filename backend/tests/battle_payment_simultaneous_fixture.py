"""Birth-only canonical variant; all Pact debts must be created by real casts."""
from game_state.state import Zone, assign_static_order_on_battlefield_entry
from tests.battle_payment_browser_fixture import midgame


def simultaneous_midgame(seat):
    state,ids=midgame(seat)
    player=state.players[seat]
    # Preserve all120 original cards while leaving two genuine green searches.
    returned=ids['attackers'][-1]
    player.battlefield.remove(returned)
    state.cards[returned].move_to_zone(Zone.LIBRARY)
    player.library.append(returned)
    ids={**ids,'attackers':ids['attackers'][:-1]}
    for _ in range(2):
        cid=next(cid for cid in player.library if state.cards[cid].name=='Forest')
        player.library.remove(cid)
        state.cards[cid].move_to_zone(Zone.BATTLEFIELD)
        player.battlefield.append(cid)
        assign_static_order_on_battlefield_entry(state,cid)
        state.cards[cid].summoning_sick=False
    state.trigger_order_choice_required=True
    state.trigger_order_choice_players={1,2}
    state.log.append('Declared canonical simultaneous-Pact variant: eight Forests and two search targets; no debt is injected.')
    return state,ids
