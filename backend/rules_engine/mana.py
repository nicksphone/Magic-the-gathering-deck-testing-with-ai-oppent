from __future__ import annotations

import re
from collections import Counter
from typing import Set

from game_state.state import MatchState
from rules_engine.continuous import has_keyword
from rules_engine.hooks import CostContext, apply_cost_modifiers


MANA_SYMBOL_RE = re.compile(r"\{([^}]+)\}")
DUAL_LAND_NAME_COLORS: dict[str, set[str]] = {
    "hallowed fountain": {"W", "U"},
    "sacred foundry": {"R", "W"},
    "watery grave": {"U", "B"},
    "blood crypt": {"B", "R"},
    "overgrown tomb": {"B", "G"},
    "breeding pool": {"U", "G"},
    "stomping ground": {"R", "G"},
    "steam vents": {"U", "R"},
    "godless shrine": {"W", "B"},
    "temple garden": {"W", "G"},
}


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
        elif sym == "C":
            # Simulator rule: treat explicit colorless symbol as generic payable by any mana.
            req["generic"] += 1
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
    out: Counter = Counter()
    for cid in state.players[player_id].battlefield:
        card = state.cards[cid]
        if "Land" in card.types and not card.tapped:
            for color in _land_colors(card.name, card.type_line, card.oracle_text):
                out[color] += 1
            out["ANY"] += 1
    return out


def count_untapped_nonland_mana_sources_by_color(state: MatchState, player_id: int) -> Counter:
    out: Counter = Counter()
    for cid in state.players[player_id].battlefield:
        card = state.cards[cid]
        colors = _nonland_mana_source_colors(state, cid, card)
        if not colors:
            continue
        for color in colors:
            out[color] += 1
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
    nonlands = count_untapped_nonland_mana_sources_by_color(state, player_id)

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
        use_from_nonlands = min(need, nonlands.get(color, 0))
        need -= use_from_nonlands
        nonlands[color] -= use_from_nonlands
        nonlands["ANY"] -= use_from_nonlands
        if need > 0:
            return False

    generic_need = req["generic"]
    for color in ["C", "W", "U", "B", "R", "G"]:
        pay = min(generic_need, pool.get(color, 0))
        generic_need -= pay
        if generic_need <= 0:
            return True
    if lands.get("ANY", 0) + nonlands.get("ANY", 0) < generic_need:
        return False
    return True


def auto_pay_cost(
    state: MatchState,
    player_id: int,
    mana_cost: str,
    is_land: bool = False,
    card_name: str = "",
) -> bool:
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
            if land_id:
                state.cards[land_id].tapped = True
                state.log.append(f"{player.name} taps {state.cards[land_id].name} for {color} to pay spell cost.")
                req[color] -= 1
                continue
            nonland_id = _find_untapped_nonland_mana_source_for_color(state, player_id, color)
            if nonland_id:
                state.cards[nonland_id].tapped = True
                state.log.append(f"{player.name} taps {state.cards[nonland_id].name} for {color} to pay spell cost.")
                req[color] -= 1
                continue
            return False

    generic_need = req["generic"]
    for color in ["C", "W", "U", "B", "R", "G"]:
        if generic_need <= 0:
            break
        pay = min(generic_need, player.mana_pool.get(color, 0))
        player.mana_pool[color] -= pay
        generic_need -= pay

    while generic_need > 0:
        land_id = _find_any_untapped_land(state, player_id)
        if land_id:
            produced = next(
                iter(
                    _ordered_colors(
                        _land_colors(
                            state.cards[land_id].name,
                            state.cards[land_id].type_line,
                            state.cards[land_id].oracle_text,
                        )
                    )
                ),
                "C",
            )
            state.cards[land_id].tapped = True
            state.log.append(f"{player.name} taps {state.cards[land_id].name} for {produced} to pay spell cost.")
            generic_need -= 1
            continue
        nonland_id = _find_any_untapped_nonland_mana_source(state, player_id)
        if nonland_id:
            produced = next(iter(_ordered_colors(_nonland_mana_source_colors(state, nonland_id, state.cards[nonland_id]))), "C")
            state.cards[nonland_id].tapped = True
            state.log.append(f"{player.name} taps {state.cards[nonland_id].name} for {produced} to pay spell cost.")
            generic_need -= 1
            continue
        return False

    return True


def _find_untapped_land_for_color(state: MatchState, player_id: int, color: str) -> str | None:
    for cid in state.players[player_id].battlefield:
        c = state.cards[cid]
        if "Land" in c.types and not c.tapped and color in _land_colors(c.name, c.type_line, c.oracle_text):
            return cid
    return None


def _find_any_untapped_land(state: MatchState, player_id: int) -> str | None:
    for cid in state.players[player_id].battlefield:
        c = state.cards[cid]
        if "Land" in c.types and not c.tapped:
            return cid
    return None


def _find_untapped_nonland_mana_source_for_color(state: MatchState, player_id: int, color: str) -> str | None:
    for cid in state.players[player_id].battlefield:
        c = state.cards[cid]
        colors = _nonland_mana_source_colors(state, cid, c)
        if colors and color in colors:
            return cid
    return None


def _find_any_untapped_nonland_mana_source(state: MatchState, player_id: int) -> str | None:
    for cid in state.players[player_id].battlefield:
        c = state.cards[cid]
        if _nonland_mana_source_colors(state, cid, c):
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


def _land_colors(name: str, type_line: str | None, oracle_text: str | None) -> Set[str]:
    n = (name or "").strip().lower()
    if n in DUAL_LAND_NAME_COLORS:
        return set(DUAL_LAND_NAME_COLORS[n])
    text = f"{name or ''} {type_line or ''}".lower()
    out: Set[str] = set()
    if "plains" in text:
        out.add("W")
    if "island" in text:
        out.add("U")
    if "swamp" in text:
        out.add("B")
    if "mountain" in text:
        out.add("R")
    if "forest" in text:
        out.add("G")
    # Also infer from mana abilities printed in oracle text, e.g. "{T}: Add {R} or {W}."
    for sym in MANA_SYMBOL_RE.findall((oracle_text or "").upper()):
        if sym in {"W", "U", "B", "R", "G", "C"}:
            out.add(sym)
    if not out:
        out.add("C")
    return out


def _ordered_colors(colors: Set[str]) -> list[str]:
    order = ["W", "U", "B", "R", "G", "C"]
    return [c for c in order if c in colors]


def _nonland_mana_source_colors(state: MatchState, card_id: str, card) -> Set[str]:
    card_types = set(getattr(card, "types", []) or [])
    if "Land" in card_types:
        return set()
    if getattr(card, "tapped", False):
        return set()
    oracle = (getattr(card, "oracle_text", "") or "").upper()
    if "{T}" not in oracle or "ADD" not in oracle:
        return set()
    # Summoning sickness prevents creatures from using tap abilities unless they have haste.
    if "Creature" in card_types:
        if getattr(card, "summoning_sick", False) and not has_keyword(state, card_id, "haste"):
            return set()
    colors: Set[str] = set()
    for sym in MANA_SYMBOL_RE.findall(oracle):
        if sym in {"W", "U", "B", "R", "G", "C"}:
            colors.add(sym)
    return colors
