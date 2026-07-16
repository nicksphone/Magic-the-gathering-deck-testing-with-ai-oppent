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


def parse_mana_cost(mana_cost: str, is_land: bool = False, x_value: int = 0) -> dict[str, int]:
    if is_land:
        return {"generic": 0, "W": 0, "U": 0, "B": 0, "R": 0, "G": 0, "C": 0}
    if not mana_cost:
        return {"generic": 0, "W": 0, "U": 0, "B": 0, "R": 0, "G": 0, "C": 0}

    req = {"generic": 0, "W": 0, "U": 0, "B": 0, "R": 0, "G": 0, "C": 0}
    for sym in MANA_SYMBOL_RE.findall(mana_cost.upper()):
        if sym.isdigit():
            req["generic"] += int(sym)
        elif sym in {"W", "U", "B", "R", "G"}:
            req[sym] += 1
        elif sym == "C":
            req["C"] += 1
        elif sym in {"X", "Y"}:
            # {X} and {Y} are variable generic costs — substitute the actual X value.
            req["generic"] += max(0, x_value)
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
            amount = land_mana_amount(state, player_id, cid)
            for color in _land_colors(card.name, card.type_line, card.oracle_text):
                out[color] += amount
            out["ANY"] += amount
    return out


def land_mana_amount(state: MatchState, player_id: int, card_id: str) -> int:
    """Return how much mana one untapped land produces for this controller."""
    for cid in state.players[player_id].battlefield:
        card = state.cards[cid]
        if "Planeswalker" not in card.types or card.controller != player_id:
            continue
        oracle = (getattr(card, "oracle_text", "") or "").lower()
        if "lands you control have" in oracle and "add two mana" in oracle:
            return 2
    return 1


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
    x_value: int = 0,
) -> bool:
    context = apply_cost_modifiers(CostContext(player_id=player_id, card_name=card_name, mana_cost=mana_cost))
    mana_cost = _apply_generic_delta_to_cost(context.mana_cost, context.generic_reduction, context.generic_increase)
    req = parse_mana_cost(mana_cost, is_land=is_land, x_value=x_value)
    pool = dict(state.players[player_id].mana_pool)
    lands = count_untapped_lands_by_color(state, player_id)
    nonlands = count_untapped_nonland_mana_sources_by_color(state, player_id)

    for color in ["W", "U", "B", "R", "G"]:
        need = req[color]
        paid = min(need, pool.get(color, 0))
        pool[color] = max(0, pool.get(color, 0) - paid)
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

    colorless_need = req["C"]
    use_from_pool = min(colorless_need, pool.get("C", 0))
    pool["C"] = max(0, pool.get("C", 0) - use_from_pool)
    colorless_need -= use_from_pool
    if colorless_need > 0:
        use_from_lands = min(colorless_need, lands.get("C", 0))
        colorless_need -= use_from_lands
        lands["C"] -= use_from_lands
        lands["ANY"] -= use_from_lands
    if colorless_need > 0:
        use_from_nonlands = min(colorless_need, nonlands.get("C", 0))
        colorless_need -= use_from_nonlands
        nonlands["C"] -= use_from_nonlands
        nonlands["ANY"] -= use_from_nonlands
    if colorless_need > 0:
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
    x_value: int = 0,
) -> bool:
    context = apply_cost_modifiers(CostContext(player_id=player_id, card_name=card_name, mana_cost=mana_cost))
    mana_cost = _apply_generic_delta_to_cost(context.mana_cost, context.generic_reduction, context.generic_increase)
    if not can_pay_with_pool_and_lands(state, player_id, mana_cost, is_land=is_land, card_name=card_name, x_value=x_value):
        return False
    req = parse_mana_cost(mana_cost, is_land=is_land, x_value=x_value)
    player = state.players[player_id]

    for color in ["W", "U", "B", "R", "G"]:
        need = req[color]
        use_pool = min(need, max(0, player.mana_pool.get(color, 0)))
        player.mana_pool[color] = max(0, player.mana_pool.get(color, 0) - use_pool)
        req[color] -= use_pool

    colorless_need = req["C"]
    use_pool = min(colorless_need, max(0, player.mana_pool.get("C", 0)))
    player.mana_pool["C"] = max(0, player.mana_pool.get("C", 0) - use_pool)
    colorless_need -= use_pool
    while colorless_need > 0:
        land_id = _find_untapped_land_for_color(state, player_id, "C")
        if land_id:
            state.cards[land_id].tapped = True
            state.log.append(f"{player.name} taps {state.cards[land_id].name} for C to pay spell cost.")
            colorless_need -= 1
            continue
        nonland_id = _find_untapped_nonland_mana_source_for_color(state, player_id, "C")
        if nonland_id:
            state.cards[nonland_id].tapped = True
            state.log.append(f"{player.name} taps {state.cards[nonland_id].name} for C to pay spell cost.")
            colorless_need -= 1
            continue
        return False

    for color in ["W", "U", "B", "R", "G"]:
        while req[color] > 0:
            land_id = _find_untapped_land_for_color(state, player_id, color)
            if land_id:
                state.cards[land_id].tapped = True
                state.log.append(f"{player.name} taps {state.cards[land_id].name} for {color} to pay spell cost.")
                amount = land_mana_amount(state, player_id, land_id)
                used = min(req[color], amount)
                req[color] -= used
                if amount > used:
                    player.mana_pool[color] += amount - used
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
        pay = min(generic_need, max(0, player.mana_pool.get(color, 0)))
        player.mana_pool[color] = max(0, player.mana_pool.get(color, 0) - pay)
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
            amount = land_mana_amount(state, player_id, land_id)
            used = min(generic_need, amount)
            generic_need -= used
            if amount > used:
                player.mana_pool[produced] += amount - used
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


def mana_value(mana_cost: str, is_land: bool = False, x_value: int = 0) -> int:
    req = parse_mana_cost(mana_cost, is_land=is_land, x_value=x_value)
    return int(req["generic"] + req["C"] + sum(req[c] for c in ["W", "U", "B", "R", "G"]))


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
        + ("{C}" * req["C"])
    )


def add_generic_to_cost(mana_cost: str, generic_add: int) -> str:
    req = parse_mana_cost(mana_cost)
    req["generic"] = max(0, req["generic"] + max(0, int(generic_add)))
    return (
        ("{" + str(req["generic"]) + "}" if req["generic"] > 0 else "")
        + ("{W}" * req["W"])
        + ("{U}" * req["U"])
        + ("{B}" * req["B"])
        + ("{R}" * req["R"])
        + ("{G}" * req["G"])
        + ("{C}" * req["C"])
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


def choose_mana_color_for_player(state: MatchState, player_id: int, preferred: list[str] | None = None) -> str:
    preferred = [c for c in (preferred or ["U", "B", "R", "G", "W", "C"]) if c in {"W", "U", "B", "R", "G", "C"}]
    scores = {c: 0 for c in ["W", "U", "B", "R", "G", "C"]}
    for cid in getattr(state.players[player_id], "hand", []) or []:
        card = state.cards.get(cid)
        if not card:
            continue
        cost = parse_mana_cost(getattr(card, "mana_cost", "") or "", is_land=("Land" in getattr(card, "types", []) or []))
        for color in ["W", "U", "B", "R", "G"]:
            scores[color] += int(cost.get(color, 0))
    if all(scores[c] == 0 for c in ["W", "U", "B", "R", "G"]):
        for color in preferred:
            return color
        return "C"
    best = max(
        ["W", "U", "B", "R", "G", "C"],
        key=lambda c: (scores.get(c, 0), -preferred.index(c) if c in preferred else -999),
    )
    return best


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
