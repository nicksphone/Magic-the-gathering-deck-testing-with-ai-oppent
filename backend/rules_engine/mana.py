from __future__ import annotations

import re
from collections import Counter
from functools import lru_cache
from typing import Set

from game_state.state import MatchState
from rules_engine.continuous import has_keyword
from rules_engine.hooks import CostContext, apply_cost_modifiers


MANA_SYMBOL_RE = re.compile(r"\{([^}]+)\}")
NONLAND_MANA_ABILITY_RE = re.compile(r"(?m)^([^:\n]*\{T\}[^:\n]*):\s*(Add[^\n.]*)", re.IGNORECASE)
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
    """Return a single cost estimate; payment alternatives use _payment_requirements."""
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
        outputs = nonland_mana_outputs(state, cid, card)
        if not outputs:
            continue
        for color, amount in outputs.items():
            out[color] += amount
        out["ANY"] += max(outputs.values())
    return out


def can_pay_with_pool_and_lands(
    state: MatchState,
    player_id: int,
    mana_cost: str,
    is_land: bool = False,
    card_name: str = "",
    x_value: int = 0,
    spell_types: set[str] | None = None,
    apply_modifiers: bool = True,
    hybrid_choices: list[str] | None = None,
) -> bool:
    context = CostContext(
        player_id=player_id, card_name=card_name, mana_cost=mana_cost,
        state=state, spell_types=spell_types,
    )
    if apply_modifiers:
        context = apply_cost_modifiers(context)
    return any(
        _plan_mana_sources(state, player_id, req) is not None
        for req in _payment_requirements(context.mana_cost, is_land, x_value, context.generic_reduction, context.generic_increase, hybrid_choices)
    )


def hybrid_payment_symbols(mana_cost: str) -> list[dict[str, object]]:
    out = []
    for symbol in MANA_SYMBOL_RE.findall((mana_cost or "").upper()):
        parts = symbol.split("/")
        if len(parts) == 2 and all(part in {"W", "U", "B", "R", "G", "C", "2"} for part in parts):
            out.append({"symbol": symbol, "choices": parts})
    return out


def _payment_requirements(
    mana_cost: str, is_land: bool, x_value: int, generic_reduction: int, generic_increase: int,
    hybrid_choices: list[str] | None = None,
) -> list[dict[str, int]]:
    if is_land:
        return [parse_mana_cost("", is_land=True)]
    hybrid_symbols = hybrid_payment_symbols(mana_cost)
    if hybrid_choices is not None and (
        len(hybrid_choices) != len(hybrid_symbols)
        or any(choice not in symbol["choices"] for choice, symbol in zip(hybrid_choices, hybrid_symbols))
    ):
        return []
    keys = ("generic", "W", "U", "B", "R", "G", "C")
    choices: list[dict[str, int]] = [{key: 0 for key in keys}]
    hybrid_index = 0
    for symbol in MANA_SYMBOL_RE.findall((mana_cost or "").upper()):
        parts = symbol.split("/")
        if len(parts) == 2 and all(part in {"W", "U", "B", "R", "G", "C", "2"} for part in parts):
            options = [("generic", 2) if part == "2" else (part, 1) for part in parts]
            if hybrid_choices is not None:
                options = [options[parts.index(hybrid_choices[hybrid_index])]]
            else:
                options.sort(key=lambda item: item[0] == "generic")
            hybrid_index += 1
        else:
            parsed = parse_mana_cost("{" + symbol + "}", x_value=x_value)
            options = [(key, amount) for key, amount in parsed.items() if amount]
        next_choices = []
        seen: set[tuple[int, ...]] = set()
        for base in choices:
            for key, amount in options or [("generic", 0)]:
                option = dict(base)
                option[key] += amount
                signature = tuple(option[item] for item in keys)
                if signature not in seen:
                    seen.add(signature)
                    next_choices.append(option)
        choices = next_choices
    for option in choices:
        option["generic"] = max(0, option["generic"] + generic_increase - generic_reduction)
    return choices


def _plan_mana_sources(state: MatchState, player_id: int, req: dict[str, int]) -> list[tuple[str, str, int, bool]] | None:
    colors = ("C", "W", "U", "B", "R", "G")
    pool = state.players[player_id].mana_pool
    needs = tuple(max(0, req[color] - max(0, pool.get(color, 0))) for color in colors)
    spare = sum(max(0, pool.get(color, 0) - req[color]) for color in colors)
    sources: list[tuple[str, dict[str, int], bool]] = []
    for cid in state.players[player_id].battlefield:
        card = state.cards[cid]
        land = "Land" in card.types
        if land and not card.tapped:
            amount = land_mana_amount(state, player_id, cid)
            outputs = {color: amount for color in _land_colors(card.name, card.type_line, card.oracle_text)}
        else:
            outputs = nonland_mana_outputs(state, cid, card)
        if outputs:
            sources.append((cid, outputs, land))

    @lru_cache(maxsize=None)
    def solve(remaining: tuple[int, ...], used: int, generic_credit: int) -> tuple[tuple[int, str], ...] | None:
        color_index = next((i for i, need in enumerate(remaining) if need), None)
        if color_index is None:
            generic_need = req["generic"] - generic_credit
            if generic_need <= 0:
                return ()
            available = []
            for i, (_, outputs, _) in enumerate(sources):
                if used & (1 << i):
                    continue
                chosen_color = max(_ordered_colors(set(outputs)), key=outputs.__getitem__)
                available.append((i, (chosen_color, outputs[chosen_color])))
            available.sort(key=lambda entry: (-entry[1][1], len(sources[entry[0]][1]), entry[0]))
            chosen = []
            for i, (color, amount) in available:
                chosen.append((i, color))
                generic_need -= amount
                if generic_need <= 0:
                    return tuple(chosen)
            return None

        color = colors[color_index]
        if sum(outputs.get(color, 0) for i, (_, outputs, _) in enumerate(sources) if not used & (1 << i)) < remaining[color_index]:
            return None
        candidates = sorted(
            (i for i, (_, outputs, _) in enumerate(sources) if not used & (1 << i) and color in outputs),
            key=lambda i: (len(sources[i][1]), -sources[i][1][color], not sources[i][2], i),
        )
        tried: set[tuple[tuple[str, int], ...]] = set()
        for i in candidates:
            signature = tuple(sorted(sources[i][1].items()))
            if signature in tried:
                continue
            tried.add(signature)
            amount = sources[i][1][color]
            next_remaining = list(remaining)
            next_remaining[color_index] = max(0, remaining[color_index] - amount)
            tail = solve(tuple(next_remaining), used | (1 << i), generic_credit + max(0, amount - remaining[color_index]))
            if tail is not None:
                return ((i, color),) + tail
        return None

    choices = solve(needs, 0, spare)
    return [(sources[i][0], color, sources[i][1][color], sources[i][2]) for i, color in choices] if choices is not None else None


def auto_pay_cost(
    state: MatchState,
    player_id: int,
    mana_cost: str,
    is_land: bool = False,
    card_name: str = "",
    x_value: int = 0,
    spell_types: set[str] | None = None,
    hybrid_choices: list[str] | None = None,
) -> bool:
    context = apply_cost_modifiers(CostContext(
        player_id=player_id, card_name=card_name, mana_cost=mana_cost,
        state=state, spell_types=spell_types,
    ))
    payment = next(
        ((req, plan) for req in _payment_requirements(
            context.mana_cost, is_land, x_value, context.generic_reduction, context.generic_increase, hybrid_choices,
        ) if (plan := _plan_mana_sources(state, player_id, req)) is not None),
        None,
    )
    if payment is None:
        return False
    req, plan = payment
    player = state.players[player_id]
    for color in ("C", "W", "U", "B", "R", "G"):
        player.mana_pool.setdefault(color, 0)
    for cid, color, amount, land in plan:
        if land:
            state.cards[cid].tapped = True
        elif not _consume_nonland_mana_source(state, player_id, cid):
            return False
        player.mana_pool[color] += amount
        state.log.append(f"{player.name} taps {state.cards[cid].name} for {amount} {color} to pay spell cost.")
    for color in ("C", "W", "U", "B", "R", "G"):
        player.mana_pool[color] -= req[color]
    generic_need = req["generic"]
    for color in ("C", "W", "U", "B", "R", "G"):
        paid = min(generic_need, player.mana_pool[color])
        player.mana_pool[color] -= paid
        generic_need -= paid
    return True


def mana_value(mana_cost: str, is_land: bool = False, x_value: int = 0) -> int:
    if is_land:
        return 0
    total = 0
    for symbol in MANA_SYMBOL_RE.findall((mana_cost or "").upper()):
        if symbol in {"X", "Y"}:
            total += max(0, x_value)
        elif "/" in symbol:
            total += max((int(part) if part.isdigit() else 1 for part in symbol.split("/") if part != "P"), default=1)
        else:
            total += int(symbol) if symbol.isdigit() else 1
    return total


def _apply_generic_delta_to_cost(mana_cost: str, generic_reduction: int, generic_increase: int) -> str:
    symbols = MANA_SYMBOL_RE.findall((mana_cost or "").upper())
    generic = max(0, sum(int(symbol) for symbol in symbols if symbol.isdigit()) + generic_increase - generic_reduction)
    return ("{" + str(generic) + "}" if generic else "") + "".join(
        "{" + symbol + "}" for symbol in symbols if not symbol.isdigit()
    )


def add_generic_to_cost(mana_cost: str, generic_add: int) -> str:
    return _apply_generic_delta_to_cost(mana_cost, 0, max(0, int(generic_add)))


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
    return set(nonland_mana_outputs(state, card_id, card))


def nonland_mana_outputs(state: MatchState, card_id: str, card) -> dict[str, int]:
    card_types = set(getattr(card, "types", []) or [])
    if "Land" in card_types:
        return {}
    if getattr(card, "tapped", False):
        return {}
    ability = NONLAND_MANA_ABILITY_RE.search(getattr(card, "oracle_text", "") or "")
    if ability is None:
        return {}
    from rules_engine.costs import activated_cost_available, parse_activated_cost
    cost = parse_activated_cost(ability.group(1))
    if not cost.supported or cost.mana_cost or not activated_cost_available(state, card.controller, card_id, ability.group(1)):
        return {}
    # Summoning sickness prevents creatures from using tap abilities unless they have haste.
    if "Creature" in card_types:
        if getattr(card, "summoning_sick", False) and not has_keyword(state, card_id, "haste"):
            return {}
    effect = ability.group(2).upper()
    any_color = re.fullmatch(r"ADD (ONE|TWO|THREE|FOUR|FIVE|SIX|\d+) MANA OF ANY (ONE )?COLOR", effect.strip())
    if any_color:
        words = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5, "SIX": 6}
        amount = words.get(any_color.group(1), None)
        amount = amount if amount is not None else int(any_color.group(1))
        if 1 <= amount <= 20 and (amount == 1 or any_color.group(2)):
            return {color: amount for color in "WUBRG"}
        return {}
    symbols = [sym for sym in MANA_SYMBOL_RE.findall(effect) if sym in "WUBRGC"]
    if not symbols:
        return {}
    if len(set(symbols)) == 1:
        return {symbols[0]: len(symbols)}
    if " OR " in effect and len(symbols) == len(set(symbols)):
        return {color: 1 for color in symbols}
    return {}


def _consume_nonland_mana_source(state: MatchState, player_id: int, card_id: str) -> bool:
    from rules_engine.costs import apply_activated_costs
    ability = NONLAND_MANA_ABILITY_RE.search(state.cards[card_id].oracle_text or "")
    return bool(ability and apply_activated_costs(state, player_id, card_id, ability.group(1)))
