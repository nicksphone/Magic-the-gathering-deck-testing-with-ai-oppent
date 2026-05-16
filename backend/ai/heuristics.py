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
    my_mana_pool = getattr(me, "mana_pool", {}) or {}
    opp_mana_pool = getattr(opp, "mana_pool", {}) or {}
    mana_delta = sum(my_mana_pool.values()) - sum(opp_mana_pool.values())
    return (
        life_delta * 1.6
        + cards_delta * 0.9
        + (my_power - opp_power) * 1.1
        + (my_toughness - opp_toughness) * 0.5
        + (my_untapped - opp_untapped) * 0.4
        + mana_delta * 0.15
        + evaluate_inevitability(state, player_id) * 0.7
    )


def evaluate_inevitability(state: MatchState, player_id: int) -> float:
    me = state.players[player_id]
    opp_id = 1 if player_id == 2 else 2
    opp = state.players[opp_id]
    me_library = getattr(me, "library", []) or []
    me_hand = getattr(me, "hand", []) or []
    me_graveyard = getattr(me, "graveyard", []) or []
    opp_library = getattr(opp, "library", []) or []
    opp_hand = getattr(opp, "hand", []) or []
    opp_graveyard = getattr(opp, "graveyard", []) or []
    me_long = len(me_library) + len(me_hand) + len(me_graveyard)
    opp_long = len(opp_library) + len(opp_hand) + len(opp_graveyard)
    pw_delta = _planeswalker_count(state, player_id) - _planeswalker_count(state, opp_id)
    return (me_long - opp_long) * 0.08 + pw_delta * 1.6


def _planeswalker_count(state: MatchState, player_id: int) -> int:
    return sum(
        1
        for cid in (getattr(state.players[player_id], "battlefield", []) or [])
        if cid in state.cards and "Planeswalker" in (getattr(state.cards[cid], "types", []) or [])
    )
