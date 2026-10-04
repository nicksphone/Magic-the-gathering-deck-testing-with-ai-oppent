from __future__ import annotations
from rules_engine.type_effects import effective_types

import re
from collections import Counter
from functools import lru_cache
from typing import Set

from game_state.state import MatchState
from rules_engine.continuous import has_keyword
from rules_engine.hooks import CostContext, apply_cost_modifiers
from rules_engine.mana_restrictions import available_pool, consume_pool, eligible, spending_rule


MANA_SYMBOL_RE = re.compile(r"\{([^}]+)\}")
MANA_COLORS = ("C", "W", "U", "B", "R", "G")
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
        return {"generic": 0, "W": 0, "U": 0, "B": 0, "R": 0, "G": 0, "C": 0, "S": 0}
    if not mana_cost:
        return {"generic": 0, "W": 0, "U": 0, "B": 0, "R": 0, "G": 0, "C": 0, "S": 0}

    req = {"generic": 0, "W": 0, "U": 0, "B": 0, "R": 0, "G": 0, "C": 0, "S": 0}
    for sym in MANA_SYMBOL_RE.findall(mana_cost.upper()):
        if sym.isdigit():
            req["generic"] += int(sym)
        elif sym in {"W", "U", "B", "R", "G", "S"}:
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
        if land_can_produce_mana(state, cid):
            amount = land_mana_amount(state, player_id, cid)
            for color in land_mana_colors(card):
                out[color] += amount
            out["ANY"] += amount
    return out


def land_can_produce_mana(state: MatchState, card_id: str, *, free_only=True) -> bool:
    from rules_engine.continuous import printed_abilities_suppressed
    card = state.cards[card_id]
    return (
        "Land" in effective_types(state, card) and not card.tapped
        and not printed_abilities_suppressed(state, card_id)
        and ("Creature" not in effective_types(state, card) or not card.summoning_sick or has_keyword(state, card_id, "haste"))
        and (not free_only or mana_activation_is_free(state, card_id, ''))
    )


def land_mana_amount(state: MatchState, player_id: int, card_id: str) -> int:
    """Return how much mana one untapped land produces for this controller."""
    from rules_engine.continuous import printed_abilities_suppressed
    for cid in state.players[player_id].battlefield:
        card = state.cards[cid]
        if "Planeswalker" not in effective_types(state, card) or card.controller != player_id:
            continue
        if printed_abilities_suppressed(state, cid):
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


def mana_source_outputs(state: MatchState, player_id: int, card_id: str) -> dict[str, int]:
    """Ready outputs used by both ordinary and snow payment planning."""
    card = state.cards[card_id]
    if "Land" in effective_types(state, card) and land_can_produce_mana(state, card_id):
        amount = land_mana_amount(state, player_id, card_id)
        return {color: amount for color in land_mana_colors(card)}
    return nonland_mana_outputs(state, card_id, card)


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
    reserved_life: int = 0,
    oracle_text: str = "",
    restricted_x_color: str | None = None,
    payment_kind: str = "spell",
    payment_types: set[str] | None = None,
    ability_kind: str | None = None,
    source_card_id: str | None = None,
    target_card_id: str | None = None,
    excluded_sources: set[str] | None = None,
    spell_is_aura: bool = False,
    spell_kicked: bool = False,
    ability_index: int | None = None,
) -> bool:
    context = CostContext(
        player_id=player_id, card_name=card_name, mana_cost=mana_cost,
        state=state, spell_types=spell_types, spell_is_aura=spell_is_aura,
        spell_kicked=spell_kicked,
        oracle_text=oracle_text,
        is_spell=payment_kind == "spell", ability_kind=ability_kind, ability_index=ability_index,
        source_card_id=source_card_id, target_card_id=target_card_id,
    )
    if apply_modifiers:
        context = apply_cost_modifiers(context)
    from rules_engine.replacement import can_pay_life
    return any(
        can_pay_life(state, player_id, req.get("life", 0) + reserved_life)
        and (not any(req.get(key, 0) for key in ('generic', 'W', 'U', 'B', 'R', 'G', 'C', 'S'))
             or _plan_payment(state, player_id, req, payment_context=(payment_kind, payment_types if payment_types is not None else spell_types or set()), excluded_sources=excluded_sources) is not None)
        for req in _payment_requirements(context.mana_cost, is_land, x_value, context.generic_reduction, context.generic_increase, hybrid_choices, restricted_x_color, floored_reductions=context.floored_reductions)
    )


def hybrid_payment_symbols(mana_cost: str) -> list[dict[str, object]]:
    out = []
    for symbol in MANA_SYMBOL_RE.findall((mana_cost or "").upper()):
        parts = symbol.split("/")
        ordinary = len(parts) == 2 and all(part in {"W", "U", "B", "R", "G", "C", "2"} for part in parts)
        phyrexian = len(parts) in {2, 3} and parts[-1] == "P" and all(part in {"W", "U", "B", "R", "G"} for part in parts[:-1])
        if ordinary or phyrexian:
            out.append({"symbol": symbol, "choices": parts})
    return out


def _payment_requirements(
    mana_cost: str, is_land: bool, x_value: int, generic_reduction: int, generic_increase: int,
    hybrid_choices: list[str] | None = None,
    restricted_x_color: str | None = None,
    branch_output: list[list[str]] | None = None,
    floored_reductions=(),
) -> list[dict[str, int]]:
    if is_land:
        return [parse_mana_cost("", is_land=True)]
    if restricted_x_color and restricted_x_color not in MANA_COLORS:
        return []
    hybrid_symbols = hybrid_payment_symbols(mana_cost)
    if hybrid_choices is not None and (
        len(hybrid_choices) != len(hybrid_symbols)
        or any(choice not in symbol["choices"] for choice, symbol in zip(hybrid_choices, hybrid_symbols))
    ):
        return []
    keys = ("generic", "W", "U", "B", "R", "G", "C", "S", "life")
    choices: list[dict[str, int]] = [{key: 0 for key in keys}]
    paths = [[]]
    hybrid_index = 0
    for symbol in MANA_SYMBOL_RE.findall((mana_cost or "").upper()):
        parts = symbol.split("/")
        if any(item["symbol"] == symbol for item in hybrid_symbols):
            options = [("generic", 2) if part == "2" else ("life", 2) if part == "P" else (part, 1) for part in parts]
            if hybrid_choices is not None:
                options = [options[parts.index(hybrid_choices[hybrid_index])]]
            else:
                options.sort(key=lambda item: item[0] == "generic")
            hybrid_index += 1
        elif symbol == "X" and restricted_x_color:
            options = [(restricted_x_color, max(0, x_value))]
        else:
            parsed = parse_mana_cost("{" + symbol + "}", x_value=x_value)
            options = [(key, amount) for key, amount in parsed.items() if amount]
        next_choices = []
        next_paths = []
        seen: set[tuple[int, ...]] = set()
        for base, path in zip(choices, paths):
            for key, amount in options or [("generic", 0)]:
                option = dict(base)
                option[key] += amount
                signature = tuple(option[item] for item in keys)
                if signature not in seen:
                    seen.add(signature)
                    next_choices.append(option)
                    branch = 'P' if key == 'life' else '2' if key == 'generic' else key
                    next_paths.append(path + [branch] if any(item['symbol'] == symbol for item in hybrid_symbols) else path)
        choices = next_choices
        paths = next_paths
    for option in choices:
        generic = option['generic'] + generic_increase
        colored = sum(option[key] for key in ('W', 'U', 'B', 'R', 'G', 'C', 'S'))
        # Apply floor-bound reductions first, then unfloored reductions: this
        # is the cheapest legal automatic order, not a global minimum cost.
        for floor, amount in sorted(floored_reductions, reverse=True):
            generic -= min(generic, amount, max(0, generic + colored - floor))
        option["generic"] = max(0, generic - generic_reduction)
    if branch_output is not None:
        branch_output.extend(paths)
    return choices


def is_snow_source(card) -> bool:
    type_line = re.split(r"\s+[—–-]\s+", card.type_line or "", maxsplit=1)[0]
    return "Snow" in card.types or bool(re.search(r"\bsnow\b", type_line, re.IGNORECASE))


def add_mana_to_pool(state: MatchState, player_id: int, color: str, amount: int, *, source_id: str | None = None) -> None:
    player = state.players[player_id]
    player.mana_pool[color] = player.mana_pool.get(color, 0) + amount
    if source_id in state.cards and is_snow_source(state.cards[source_id]):
        player.snow_mana_pool[color] = player.snow_mana_pool.get(color, 0) + amount
    if source_id in state.cards and (rule := spending_rule(state.cards[source_id])) is not None and amount > 0:
        from copy import deepcopy
        player.restricted_mana_pool.append({"color": color, "amount": amount,
                                           "snow": is_snow_source(state.cards[source_id]), "rule": deepcopy(rule)})


def _plan_mana_sources(
    state: MatchState, player_id: int, req: dict[str, int], *,
    pool_override: dict[str, int] | None = None, excluded_sources: set[str] | None = None,
    payment_context=None,
) -> list[tuple[str, str, int, bool]] | None:
    colors = MANA_COLORS
    pool = pool_override if pool_override is not None else available_pool(state.players[player_id], payment_context)[0]
    needs = tuple(max(0, req[color] - max(0, pool.get(color, 0))) for color in colors)
    spare = sum(max(0, pool.get(color, 0) - req[color]) for color in colors)
    sources: list[tuple[str, dict[str, int], bool]] = []
    for cid in state.players[player_id].battlefield:
        if cid in (excluded_sources or set()):
            continue
        card = state.cards[cid]
        if not eligible(spending_rule(card), payment_context):
            continue
        land = "Land" in effective_types(state, card)
        outputs = mana_source_outputs(state, player_id, cid)
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
            available.sort(key=lambda entry: (
                is_snow_source(state.cards[sources[entry[0]][0]]),
                -entry[1][1], len(sources[entry[0]][1]), entry[0],
            ))
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
            key=lambda i: (
                is_snow_source(state.cards[sources[i][0]]), len(sources[i][1]),
                -sources[i][1][color], not sources[i][2], i,
            ),
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


def _plan_payment(state: MatchState, player_id: int, req: dict[str, int], *, payment_context=None, excluded_sources=None) -> tuple[list[tuple[str, str, int, bool]], dict[str, int]] | None:
    snow_needed = req.get("S", 0)
    if not snow_needed:
        plan = _plan_mana_sources(state, player_id, req, payment_context=payment_context, excluded_sources=excluded_sources)
        return (plan, {}) if plan is not None else None

    player = state.players[player_id]
    pool, snow = available_pool(player, payment_context)
    sources = []
    for cid in player.battlefield:
        if cid in (excluded_sources or set()):
            continue
        card = state.cards[cid]
        if not is_snow_source(card) or not eligible(spending_rule(card), payment_context):
            continue
        land = "Land" in effective_types(state, card)
        outputs = mana_source_outputs(state, player_id, cid)
        if outputs:
            sources.append((cid, outputs, land))

    def solve(remaining: int, totals: dict[str, int], snow_left: dict[str, int],
              selected: list[tuple[str, str, int, bool]], spent: dict[str, int]):
        if remaining == 0:
            ordinary = _plan_mana_sources(state, player_id, req, pool_override=totals,
                                          excluded_sources={entry[0] for entry in selected} | (excluded_sources or set()), payment_context=payment_context)
            return (selected + ordinary, spent) if ordinary is not None else None
        for color in MANA_COLORS:
            if snow_left[color] <= 0:
                continue
            next_totals, next_snow, next_spent = totals.copy(), snow_left.copy(), spent.copy()
            next_totals[color] -= 1
            next_snow[color] -= 1
            next_spent[color] = next_spent.get(color, 0) + 1
            found = solve(remaining - 1, next_totals, next_snow, selected, next_spent)
            if found is not None:
                return found
        if len(selected) >= snow_needed:
            return None
        used = {entry[0] for entry in selected}
        for cid, outputs, land in sources:
            if cid in used:
                continue
            for color in MANA_COLORS:
                if not outputs.get(color):
                    continue
                amount = outputs[color]
                next_totals, next_snow = totals.copy(), snow_left.copy()
                next_totals[color] += amount
                next_snow[color] += amount
                found = solve(remaining, next_totals, next_snow,
                              selected + [(cid, color, amount, land)], spent)
                if found is not None:
                    return found
        return None

    return solve(snow_needed, pool, snow, [], {})


def auto_pay_cost(
    state: MatchState,
    player_id: int,
    mana_cost: str,
    is_land: bool = False,
    card_name: str = "",
    x_value: int = 0,
    spell_types: set[str] | None = None,
    hybrid_choices: list[str] | None = None,
    reserved_life: int = 0,
    payment_details: dict | None = None,
    oracle_text: str = "",
    restricted_x_color: str | None = None,
    payment_kind: str = "spell",
    payment_types: set[str] | None = None,
    ability_kind: str | None = None,
    source_card_id: str | None = None,
    target_card_id: str | None = None,
    excluded_sources: set[str] | None = None,
    spell_is_aura: bool = False,
    spell_kicked: bool = False,
    ability_index: int | None = None,
) -> bool:
    payment_context = (payment_kind, payment_types if payment_types is not None else spell_types or set())
    context = apply_cost_modifiers(CostContext(
        player_id=player_id, card_name=card_name, mana_cost=mana_cost,
        state=state, spell_types=spell_types, spell_is_aura=spell_is_aura,
        spell_kicked=spell_kicked,
        oracle_text=oracle_text,
        is_spell=payment_kind == "spell", ability_kind=ability_kind, ability_index=ability_index,
        source_card_id=source_card_id, target_card_id=target_card_id,
    ))
    from rules_engine.replacement import can_pay_life, pay_life
    branches = []
    requirements = _payment_requirements(
        context.mana_cost, is_land, x_value, context.generic_reduction, context.generic_increase,
        hybrid_choices, restricted_x_color, branches, context.floored_reductions,
    )
    payment = next(
        ((req, plan) for req in requirements if can_pay_life(state, player_id, req.get("life", 0) + reserved_life)
        and (plan := ([], {}) if not any(req.get(key, 0) for key in ('generic', 'W', 'U', 'B', 'R', 'G', 'C', 'S'))
             else _plan_payment(state, player_id, req, payment_context=payment_context, excluded_sources=excluded_sources)) is not None),
        None,
    )
    if payment is None:
        return False
    req, (plan, snow_spent) = payment
    player = state.players[player_id]
    if payment_details is not None:
        payment_details['mana_spent'] = sum(req.get(key, 0) for key in ('generic', 'W', 'U', 'B', 'R', 'G', 'C', 'S'))
        payment_details["phyrexian_life_symbols"] = req.get("life", 0) // 2
        payment_details['hybrid_choices'] = branches[requirements.index(req)] if branches else []
    if req.get("life", 0):
        if not pay_life(state, player_id, req["life"]):
            return False
        state.log.append(f"{player.name} pays {req['life']} life for Phyrexian mana.")
    if not any(req.get(key, 0) for key in ('generic', 'W', 'U', 'B', 'R', 'G', 'C', 'S')):
        return True
    for color in MANA_COLORS:
        player.mana_pool.setdefault(color, 0)
    for cid, color, amount, land in plan:
        if land:
            state.cards[cid].tapped = True
        elif not _consume_nonland_mana_source(state, player_id, cid):
            return False
        add_mana_to_pool(state, player_id, color, amount, source_id=cid)
        cost_kind = payment_kind
        state.log.append(f"{player.name} taps {state.cards[cid].name} for {amount} {color} to pay {cost_kind} cost.")
    snow_by_color = dict(snow_spent)
    from types import SimpleNamespace
    totals, snow_totals = available_pool(player, payment_context)
    payer = SimpleNamespace(mana_pool=dict(totals), snow_mana_pool=dict(snow_totals))
    for color, amount in snow_spent.items():
        payer.snow_mana_pool[color] -= amount
        payer.mana_pool[color] -= amount
    for color in MANA_COLORS:
        spent = _spend_pool_color(payer, color, req[color])
        snow_by_color[color] = snow_by_color.get(color, 0) + spent
    generic_need = req["generic"]
    for spend_snow in (False, True):
        for color in MANA_COLORS:
            available = (payer.snow_mana_pool.get(color, 0) if spend_snow else
                         payer.mana_pool[color] - payer.snow_mana_pool.get(color, 0))
            paid = min(generic_need, available)
            spent = _spend_pool_color(payer, color, paid)
            snow_by_color[color] = snow_by_color.get(color, 0) + spent
            generic_need -= paid
    for color in MANA_COLORS:
        consume_pool(player, color, totals[color] - payer.mana_pool[color],
                     snow_totals[color] - payer.snow_mana_pool[color], payment_context)
    if payment_details is not None:
        payment_details["snow_mana_colors"] = {color: amount for color, amount in snow_by_color.items() if amount}
        payment_details["snow_mana_spent"] = sum(snow_by_color.values())
    return True


def _spend_pool_color(player, color: str, amount: int) -> int:
    ordinary = player.mana_pool[color] - player.snow_mana_pool.get(color, 0)
    snow_spent = max(0, amount - ordinary)
    player.snow_mana_pool[color] = max(0, player.snow_mana_pool.get(color, 0) - snow_spent)
    player.mana_pool[color] -= amount
    return snow_spent


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


@lru_cache(maxsize=8192)
def _counter_mana_replacement(name: str, text: str):
    subject = rf"(?:this land|this card|{re.escape(name)})"
    conditional = re.compile(
        rf"\{{T\}}: Add \{{([WUBRGC])\}}\. If {subject} has a ([\w-]+) counter on it, "
        r"instead add one mana of any color\.", re.I,
    )
    match = next((conditional.fullmatch(line.strip()) for line in text.split("\n")
                  if conditional.fullmatch(line.strip())), None)
    if match:
        remaining = "\n".join(line for line in text.split("\n") if not conditional.fullmatch(line.strip()))
        return match[1].upper(), match[2].lower(), remaining
    return None


def land_mana_colors(card) -> Set[str]:
    """Supported counter-presence replacement, using current permanent state."""
    text = card.oracle_text or ""
    replacement = _counter_mana_replacement(card.name, text)
    if replacement:
        base, counter, remaining = replacement
        colors = set("WUBRG") if card.counters.get(counter, 0) > 0 else {base}
        return colors | _land_colors(card.name, card.type_line, remaining, fallback=False)
    return _land_colors(card.name, card.type_line, text)


def _land_colors(name: str, type_line: str | None, oracle_text: str | None, *, fallback: bool = True) -> Set[str]:
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
    if re.search(r"\{T\}: Add one mana of any color\.", oracle_text or "", re.I):
        out.update("WUBRG")
    if not out and fallback:
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
        cost = parse_mana_cost(getattr(card, "mana_cost", "") or "", is_land=("Land" in effective_types(state, card) or []))
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
    return set(nonland_mana_outputs(state, card_id, card, free_only=False))


def mana_activation_is_free(state, card_id, cost):
    card = state.cards[card_id]
    controller = getattr(card, 'controller', None)
    if controller is None:
        controller = next((pid for pid, player in state.players.items() if card_id in player.battlefield), None)
    context = apply_cost_modifiers(CostContext(
        state=state, player_id=controller, card_name=card.name,
        mana_cost=cost, is_spell=False, ability_kind='mana', source_card_id=card_id))
    return any(not any(req.values()) for req in _payment_requirements(
        context.mana_cost, False, 0, context.generic_reduction, context.generic_increase,
        floored_reductions=context.floored_reductions))


def nonland_mana_outputs(state: MatchState, card_id: str, card, *, free_only=True) -> dict[str, int]:
    from rules_engine.continuous import printed_abilities_suppressed
    if printed_abilities_suppressed(state, card_id):
        return {}
    card_types = set(effective_types(state, card) or [])
    if "Land" in card_types:
        return {}
    if getattr(card, "tapped", False):
        return {}
    ability = NONLAND_MANA_ABILITY_RE.search(getattr(card, "oracle_text", "") or "")
    if ability is None:
        return {}
    if (rule := spending_rule(card)) is not None and rule.get("unsupported"):
        return {}
    from rules_engine.costs import activated_cost_available, parse_activated_cost
    cost = parse_activated_cost(ability.group(1))
    if not cost.supported or (free_only and not mana_activation_is_free(state, card_id, cost.mana_cost)) or not activated_cost_available(state, card.controller, card_id, ability.group(1), ability_kind='mana'):
        return {}
    # Summoning sickness prevents creatures from using tap abilities unless they have haste.
    if "Creature" in card_types:
        if getattr(card, "summoning_sick", False) and not has_keyword(state, card_id, "haste"):
            return {}
    return _nonland_mana_effect_outputs(ability.group(2), state=state, card=card)


def repeatable_nonland_mana_outputs(card, *, state=None, payment_context=None) -> dict[str, int]:
    """Printed tap-only capacity; never an assertion that it is usable now."""
    if state is not None:
        from rules_engine.continuous import printed_abilities_suppressed
        if printed_abilities_suppressed(state, getattr(card, 'id', None)):
            return {}
    if "Land" in (effective_types(state, card) or []):
        return {}
    text = getattr(card, "oracle_text", "") or ""
    ability = NONLAND_MANA_ABILITY_RE.search(text)
    if ability is None or not eligible(spending_rule(card), payment_context) or re.search(
        r"\bactivate (?:this ability )?only\b"
        r"|\bdoesn't untap during your untap step\b", text, re.I,
    ):
        return {}
    from rules_engine.costs import ActivatedCost, parse_activated_cost
    if parse_activated_cost(ability.group(1)) != ActivatedCost(tap_source=True):
        return {}
    if state is not None and not mana_activation_is_free(state, card.id, ''):
        return {}
    return _nonland_mana_effect_outputs(ability.group(2), state=state, card=card)


def _nonland_mana_effect_outputs(effect: str, *, state=None, card=None) -> dict[str, int]:
    effect = effect.strip().upper()
    any_color = re.fullmatch(r"ADD (ONE|TWO|THREE|FOUR|FIVE|SIX|\d+) MANA OF ANY (ONE )?COLOR", effect.strip())
    if any_color:
        words = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5, "SIX": 6}
        amount = words.get(any_color.group(1), None)
        amount = amount if amount is not None else int(any_color.group(1))
        if 1 <= amount <= 20 and (amount == 1 or any_color.group(2)):
            return {color: amount for color in "WUBRG"}
        return {}
    if re.fullmatch(r"ADD (?:\{[WUBRGC]\})+", effect):
        symbols = MANA_SYMBOL_RE.findall(effect)
        if len(set(symbols)) == 1:
            return {symbols[0]: len(symbols)}
    if re.fullmatch(r"ADD \{[WUBRGC]\}(?:,? (?:OR )?\{[WUBRGC]\})+", effect) and " OR " in effect:
        return {color: 1 for color in MANA_SYMBOL_RE.findall(effect)}
    if state is None or card is None:
        return {}
    amount = None
    count = re.fullmatch(r"ADD \{([WUBRGC])\} FOR EACH (.+) (YOU CONTROL|ON THE BATTLEFIELD)", effect)
    if count:
        from rules_engine.continuous import _subject_matches
        subject = count.group(2).lower()
        other = subject.startswith("other ")
        subject = subject.removeprefix("other ")
        if subject in {"creature", "artifact", "enchantment", "land", "planeswalker", "battle", "permanent", "token"}:
            subject += "s"
        elif subject.endswith(" creature"):
            subject += "s"
        amount = sum(
            (not other or cid != card.id) and _subject_matches(state, cid, subject)
            for player in state.players.values() for cid in player.battlefield
            if count.group(3) == "ON THE BATTLEFIELD" or state.cards[cid].controller == card.controller
        )
        color = count.group(1)
    else:
        names = {card.name.upper(), card.name.split(",", 1)[0].upper(), "THIS CREATURE", "THIS PERMANENT"}
        counter = re.fullmatch(r"ADD \{([WUBRGC])\} FOR EACH (.+) COUNTER ON (.+)", effect)
        power = re.fullmatch(r"ADD AN AMOUNT OF \{([WUBRGC])\} EQUAL TO (.+)'S POWER", effect)
        if counter and counter.group(3) in names:
            amount = max(0, (card.counters or {}).get(counter.group(2).lower(), 0))
            color = counter.group(1)
        elif power and power.group(2) in names:
            from rules_engine.continuous import effective_power
            amount = max(0, effective_power(state, card.id))
            color = power.group(1)
    if amount:
        return {color: amount}
    return {}


def _consume_nonland_mana_source(state: MatchState, player_id: int, card_id: str) -> bool:
    from rules_engine.costs import apply_activated_costs
    ability = NONLAND_MANA_ABILITY_RE.search(state.cards[card_id].oracle_text or "")
    return bool(ability and apply_activated_costs(state, player_id, card_id, ability.group(1), ability_kind='mana'))
