"""Conservative matchup swaps using public evidence and cached card text."""

from __future__ import annotations

from collections import Counter

from rules_engine.card_types import is_land_card
from rules_engine.mana import _land_colors, parse_mana_cost


def plan_sideboard(
    mainboard: list[dict],
    sideboard: list[dict],
    observed_types: set[str],
    opponent_archetype: str | None = None,
    max_swaps: int = 4,
) -> tuple[list[dict], list[dict]]:
    if not sideboard or max_swaps <= 0:
        return [], []
    observed = {kind.lower() for kind in observed_types}
    archetype = (opponent_archetype or "").lower()
    sources: Counter[str] = Counter()
    for item in mainboard:
        card = {**item, "name": item.get("card_name", "")}
        if is_land_card(card):
            for color in _land_colors(card["name"], card.get("type_line"), card.get("oracle_text")):
                sources[color] += int(item["quantity"])

    def castable(item: dict) -> bool:
        req = parse_mana_cost(str(item.get("mana_cost") or ""))
        return all(sources[color] >= max(4, amount * 4) for color, amount in req.items() if color != "generic" and amount)

    def value(item: dict) -> float:
        text = str(item.get("oracle_text") or "").lower()
        creature_match = "creature" in observed or archetype in {"aggro", "tribal", "tokens", "midrange", "drain", "aristocrats"}
        score = 0.0
        if "destroy target creature" in text or "exile target creature" in text or "return target creature" in text:
            score += 1.5 if creature_match else -1.5
        if "destroy target nonland permanent" in text or "destroy target artifact" in text or "exile target artifact" in text:
            score += 3.5 if "artifact" in observed or "enchantment" in observed else 0.0
        if "counter target noncreature spell" in text or "counter target spell" in text:
            score += (2.5 if archetype in {"control", "counter-heavy", "combo-lite", "ramp"}
                      else 1.5 if {"instant", "sorcery"} & observed else 0.0)
        if "all creatures" in text and ("destroy" in text or "exile" in text or "-x/-x" in text):
            score += 2.5 if creature_match else -1.0
        return score

    incoming = sorted(
        (item for item in sideboard if item.get("oracle_text") and item.get("type_line") and not is_land_card({**item, "name": item.get("card_name", "")}) and castable(item)),
        key=lambda item: (-value(item), item["card_name"]),
    )
    outgoing = sorted(
        (item for item in mainboard if item.get("oracle_text") and item.get("type_line") and not is_land_card({**item, "name": item.get("card_name", "")})),
        key=lambda item: (value(item), item["card_name"]),
    )
    removed: Counter[str] = Counter()
    added: Counter[str] = Counter()
    for side in incoming:
        if value(side) < 1.5:
            continue
        for _ in range(int(side["quantity"])):
            if sum(added.values()) >= max_swaps:
                break
            cut = next((item for item in outgoing if item["card_name"] != side["card_name"]
                        and removed[item["card_name"]] < int(item["quantity"])
                        and value(side) - value(item) >= 1.5), None)
            if cut is None:
                break
            removed[cut["card_name"]] += 1
            added[side["card_name"]] += 1
    to_entries = lambda counts: [{"card_name": name, "quantity": count} for name, count in sorted(counts.items())]
    return to_entries(removed), to_entries(added)
