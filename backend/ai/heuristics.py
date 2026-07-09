from __future__ import annotations

from game_state.state import MatchState
from rules_engine.continuous import effective_keywords, effective_power, effective_toughness


def evaluate_board(state: MatchState, player_id: int) -> float:
    me = state.players[player_id]
    opp_id = 1 if player_id == 2 else 2
    opp = state.players[opp_id]
    my_battlefield = _board_value(state, player_id)
    opp_battlefield = _board_value(state, opp_id)
    life_delta = me.life - opp.life
    cards_delta = len(me.hand) - len(opp.hand)
    my_mana_pool = getattr(me, "mana_pool", {}) or {}
    opp_mana_pool = getattr(opp, "mana_pool", {}) or {}
    mana_delta = sum(my_mana_pool.values()) - sum(opp_mana_pool.values())
    return (
        life_delta * 1.6
        + cards_delta * 0.9
        + (my_battlefield - opp_battlefield) * 0.95
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


def _board_value(state: MatchState, player_id: int) -> float:
    total = 0.0
    for cid in getattr(state.players[player_id], "battlefield", []) or []:
        card = state.cards.get(cid)
        if not card:
            continue
        types = set(getattr(card, "types", []) or [])
        if "Creature" in types:
            total += _creature_value(state, cid)
            continue
        total += _noncreature_value(card)
        if "Land" in types and not getattr(card, "tapped", False):
            total += 0.12
    return total


def _creature_value(state: MatchState, card_id: str) -> float:
    card = state.cards[card_id]
    power = max(0, int(effective_power(state, card_id) or 0))
    toughness = max(0, int(effective_toughness(state, card_id) or 0))
    kws = {str(k).lower() for k in (effective_keywords(state, card_id) or [])}
    value = power * 1.35 + toughness * 0.55
    value += 0.25 if not getattr(card, "tapped", False) else -0.1
    if "flying" in kws:
        value += 1.1
    if "trample" in kws:
        value += 0.7
    if "menace" in kws:
        value += 0.6
    if "lifelink" in kws:
        value += 0.9
    if "deathtouch" in kws:
        value += 0.8
    if "vigilance" in kws:
        value += 0.35
    if "haste" in kws:
        value += 0.45
    if "indestructible" in kws:
        value += 0.75
    if "hexproof" in kws or "shroud" in kws:
        value += 0.45
    if "ward" in kws:
        value += 0.25
    if "defender" in kws:
        value -= 0.55
    return value


def _noncreature_value(card) -> float:
    types = set(getattr(card, "types", []) or [])
    text = f"{getattr(card, 'name', '')} {getattr(card, 'oracle_text', '')}".lower()
    value = 0.0
    if "Planeswalker" in types:
        value += 7.0
        value += max(0, int(getattr(card, "loyalty", 0) or 0)) * 0.35
    if "Artifact" in types:
        value += 2.0
    if "Enchantment" in types:
        value += 2.1
    if any(k in text for k in ["draw", "search your library", "return target"]):
        value += 1.2
    if any(k in text for k in ["creatures you control get", "+1/+1", "anthem"]):
        value += 2.0
    if any(k in text for k in ["counter target", "destroy target", "exile target"]):
        value += 1.1
    if any(k in text for k in ["add {", "treasure", "create token", "token"]):
        value += 1.0
    if any(k in text for k in ["lifelink", "gain life", "can't lose life"]):
        value += 0.7
    return value
