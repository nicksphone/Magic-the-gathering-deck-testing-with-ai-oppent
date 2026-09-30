"""Spending provenance for supported type-restricted mana, not SQL rules."""
import re
from functools import lru_cache

COLORS = "CWUBRG"
TYPES = {word.lower(): word for word in ("Artifact", "Creature", "Enchantment", "Instant", "Sorcery", "Planeswalker", "Battle")}


def spending_rule(card):
    return _parse_rule(getattr(card, "oracle_text", "") or "")


@lru_cache(maxsize=4096)
def _parse_rule(text):
    clauses = re.findall(r"spend this mana only to ([^.\n]+)", text.lower())
    if not clauses:
        return {"unsupported": True} if re.search(r"\bspend\b[^.\n]*\bonly\b|\bcan't be spent\b", text, re.I) else None
    if len(clauses) != 1:
        return {"unsupported": True}
    match = re.fullmatch(r"cast (.+?) spells(?: or activate abilities of (.+))?", clauses[0])
    if not match:
        return {"unsupported": True}

    def types(phrase, plural=False):
        words = re.split(r",? (?:or |and )?", phrase or "")
        words = [word.removesuffix("s") if plural else word for word in words if word]
        return sorted({TYPES[word] for word in words}) if words and all(word in TYPES for word in words) else None

    cast = types(match.group(1))
    activate = types(match.group(2), True) if match.group(2) else []
    if cast is None or activate is None:
        return {"unsupported": True}
    return {"cast_types": cast, "activate_types": activate}


def eligible(rule, context):
    if rule is None:
        return True
    if rule.get("unsupported") or context is None:
        return False
    kind, types = context
    allowed = rule.get("cast_types" if kind == "spell" else "activate_types" if kind == "activation" else "", [])
    return bool(set(allowed) & set(types))


def available_pool(player, context):
    pool = {color: max(0, player.mana_pool.get(color, 0)) for color in COLORS}
    snow_pool = getattr(player, "snow_mana_pool", {})
    snow = {color: min(pool[color], max(0, snow_pool.get(color, 0))) for color in COLORS}
    for lot in getattr(player, "restricted_mana_pool", []):
        if not eligible(lot["rule"], context):
            color, amount = lot["color"], lot["amount"]
            pool[color] = max(0, pool[color] - amount)
            if lot["snow"]:
                snow[color] = max(0, snow[color] - amount)
    return pool, snow


def consume_pool(player, color, amount, snow_amount, context):
    """Spend eligible restricted units first, preserving independent snow tags."""
    for snow, need in ((False, amount - snow_amount), (True, snow_amount)):
        for lot in player.restricted_mana_pool:
            if lot["color"] == color and lot["snow"] == snow and eligible(lot["rule"], context):
                used = min(need, lot["amount"])
                lot["amount"] -= used
                need -= used
                if not need:
                    break
    player.restricted_mana_pool[:] = [lot for lot in player.restricted_mana_pool if lot["amount"]]
    player.mana_pool[color] -= amount
    player.snow_mana_pool[color] = max(0, player.snow_mana_pool.get(color, 0) - snow_amount)
