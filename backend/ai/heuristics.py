from __future__ import annotations

from game_state.state import MatchState


def evaluate_board(state: MatchState, player_id: int) -> float:
    me = state.players[player_id]
    opp_id = 1 if player_id == 2 else 2
    opp = state.players[opp_id]
    my_power = sum((state.cards[c].power or 0) for c in me.battlefield if "Creature" in state.cards[c].types)
    opp_power = sum((state.cards[c].power or 0) for c in opp.battlefield if "Creature" in state.cards[c].types)
    life_delta = me.life - opp.life
    cards_delta = len(me.hand) - len(opp.hand)
    return life_delta * 1.5 + cards_delta * 0.8 + (my_power - opp_power)
