"""Exact accepted fund/finish helpers, without importing the whole counter suite."""
from game_state.state import PlayerState, Zone
import domain_paid_support as g

def fund(state,seat,**pool):
    for player in state.players.values():
        player.mana_pool={**PlayerState(id=player.id,name='Fixture').mana_pool,**player.mana_pool}
    state.players[seat].mana_pool=PlayerState(id=seat,name='Fixture').mana_pool
    state.players[seat].mana_pool.update(pool)

def finish(state,source):
    for _ in range(32):
        if state.cards[source].zone!=Zone.STACK:return state
        assert not state.pending_mechanic_choice and not state.pending_trigger_order
        state=g.act(state,state.priority_player,'pass_priority')
    raise AssertionError('Paid source did not resolve in bounded public priority actions')
