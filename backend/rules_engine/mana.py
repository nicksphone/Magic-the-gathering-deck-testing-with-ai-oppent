from __future__ import annotations

import re
from collections import Counter

from game_state.state import MatchState
from rules_engine.hooks import CostContext, apply_cost_modifiers


MANA_SYMBOL_RE = re.compile(r"\{([^}]+)\}")


def parse_mana_cost(mana_cost: str, is_land: bool = False) -> dict[str, int]:
    if is_land:
        return {"generic": 0, "W": 0, "U": 0, "B": 0, "R": 0, "G": 0}
    if not mana_cost:
        return {"generic": 0, "W": 0, "U": 0, "B": 0, "R": 0, "G": 0}

    req = {"generic": 0, "W": 0, "U": 0, "B": 0, "R": 0, "G": 0}
    for sym in MANA_SYMBOL_RE.findall(mana_cost.upper()):
        if sym.isdigit():
            req["generic"] += int(sym)
        elif sym in {"W", "U", "B", "R", "G"}:
            req[sym] += 1
        elif "/" in sym:
            left = sym.split("/")[0]
            if left in req:
                req[left] += 1
            else:
                req["generic"] += 1
        else:
            req["generic"] += 1
    return req


def count_untapped_lands_by_color(state: MatchState, player_id: int) -> Counter:
    from rules_engine.engine import _infer_mana_from_land

    out: Counter = Counter()
    for cid in state.players[player_id].battlefield:
        card = state.cards[cid]
        if "Land" in card.types and not card.tapped:
            out[_infer_mana_from_land(card.name)] += 1
            out["ANY"] += 1
    return out


def can_pay_with_pool_and_lands(
    state: MatchState,
    player_id: int,
    mana_cost: str,
    is_land: bool = False,
    card_name: str = "",
) -> bool:
    context = apply_cost_modifiers(CostContext(player_id=player_id, card_name=card_name, mana_cost=mana_cost))
    mana_cost = _apply_generic_delta_to_cost(context.mana_cost, context.generic_reduction, context.generic_increase)
    req = parse_mana_cost(mana_cost, is_land=is_land)
    pool = dict(state.players[player_id].mana_pool)
    lands = count_untapped_lands_by_color(state, player_id)

    for color in ["W", "U", "B", "R", "G"]:
        need = req[color]
        paid = min(need, pool.get(color, 0))
        need -= paid
        if need <= 0:
            continue
        use_from_lands = min(need, lands.get(color, 0))
        need -= use_from_lands
        lands[color] -= use_from_lands
        lands["ANY"] -= use_from_lands
        if need > 0:
            return False

    generic_need = req["generic"]
    for color in ["C", "W", "U", "B", "R", "G"]:
        pay = min(generic_need, pool.get(color, 0))
        generic_need -= pay
        if generic_need <= 0:
            return True
    if lands.get("ANY", 0) < generic_need:
        return False
    return True


def auto_pay_cost(
    state: MatchState,
    player_id: int,
    mana_cost: str,
    is_land: bool = False,
    card_name: str = "",
) -> bool:
    from rules_engine.engine import _infer_mana_from_land

    context = apply_cost_modifiers(CostContext(player_id=player_id, card_name=card_name, mana_cost=mana_cost))
    mana_cost = _apply_generic_delta_to_cost(context.mana_cost, context.generic_reduction, context.generic_increase)
    if not can_pay_with_pool_and_lands(state, player_id, mana_cost, is_land=is_land, card_name=card_name):
        return False
    req = parse_mana_cost(mana_cost, is_land=is_land)
    player = state.players[player_id]

    for color in ["W", "U", "B", "R", "G"]:
        need = req[color]
        use_pool = min(need, player.mana_pool.get(color, 0))
        player.mana_pool[color] -= use_pool
        req[color] -= use_pool

    for color in ["W", "U", "B", "R", "G"]:
        while req[color] > 0:
            land_id = _find_untapped_land_for_color(state, player_id, color)
            if not land_id:
                return False
            state.cards[land_id].tapped = True
            req[color] -= 1

    generic_need = req["generic"]
    for color in ["C", "W", "U", "B", "R", "G"]:
        if generic_need <= 0:
            break
        pay = min(generic_need, player.mana_pool.get(color, 0))
        player.mana_pool[color] -= pay
        generic_need -= pay

    while generic_need > 0:
        land_id = _find_any_untapped_land(state, player_id)
        if not land_id:
            return False
        produced = _infer_mana_from_land(state.cards[land_id].name)
        state.cards[land_id].tapped = True
        state.log.append(f"{player.name} taps {state.cards[land_id].name} for {produced} to pay spell cost.")
        generic_need -= 1

    return True


def _find_untapped_land_for_color(state: MatchState, player_id: int, color: str) -> str | None:
    from rules_engine.engine import _infer_mana_from_land

    for cid in state.players[player_id].battlefield:
        c = state.cards[cid]
        if "Land" in c.types and not c.tapped and _infer_mana_from_land(c.name) == color:
            return cid
    return None


def _find_any_untapped_land(state: MatchState, player_id: int) -> str | None:
    for cid in state.players[player_id].battlefield:
        c = state.cards[cid]
        if "Land" in c.types and not c.tapped:
            return cid
    return None


def _apply_generic_delta_to_cost(mana_cost: str, generic_reduction: int, generic_increase: int) -> str:
    req = parse_mana_cost(mana_cost)
    req["generic"] = max(0, req["generic"] + generic_increase - generic_reduction)
    return (
        ("{" + str(req["generic"]) + "}" if req["generic"] > 0 else "")
        + ("{W}" * req["W"])
        + ("{U}" * req["U"])
        + ("{B}" * req["B"])
        + ("{R}" * req["R"])
        + ("{G}" * req["G"])
    )
