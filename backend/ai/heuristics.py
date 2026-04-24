from __future__ import annotations

from game_state.state import MatchState


def evaluate_board(state: MatchState, player_id: int) -> float:
    me = state.players[player_id]
    opp_id = 1 if player_id == 2 else 2
    opp = state.players[opp_id]
    my_power = sum((state.cards[c].power or 0) for c in me.battlefield if "Creature" in state.cards[c].types)
    opp_power = sum((state.cards[c].power or 0) for c in opp.battlefield if "Creature" in state.cards[c].types)
    my_toughness = sum((state.cards[c].toughness or 0) for c in me.battlefield if "Creature" in state.cards[c].types)
    opp_toughness = sum((state.cards[c].toughness or 0) for c in opp.battlefield if "Creature" in state.cards[c].types)
    my_untapped = sum(
        1
        for c in me.battlefield
        if "Creature" in state.cards[c].types and not state.cards[c].tapped
    )
    opp_untapped = sum(
        1
        for c in opp.battlefield
        if "Creature" in state.cards[c].types and not state.cards[c].tapped
    )
    life_delta = me.life - opp.life
    cards_delta = len(me.hand) - len(opp.hand)
    mana_delta = sum(me.mana_pool.values()) - sum(opp.mana_pool.values())
    return (
        life_delta * 1.6
        + cards_delta * 0.9
        + (my_power - opp_power) * 1.1
        + (my_toughness - opp_toughness) * 0.5
        + (my_untapped - opp_untapped) * 0.4
        + mana_delta * 0.15
    )
