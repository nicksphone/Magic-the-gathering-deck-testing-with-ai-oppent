from __future__ import annotations

from collections import Counter

ARCHETYPES = [
    "Aggro",
    "Burn",
    "Midrange",
    "Control",
    "Tempo",
    "Ramp",
    "Drain",
    "Aristocrats",
    "Reanimator",
    "Tokens",
    "Tribal",
    "Combo-lite",
    "Counter-heavy",
    "Removal-heavy",
]


def guess_archetype(mainboard: list[dict]) -> str:
    return analyze_deck(mainboard)["primary_archetype"]


def analyze_deck(mainboard: list[dict]) -> dict:
    expanded_names = [str(item["card_name"]).strip().lower() for item in mainboard for _ in range(int(item.get("quantity", 0) or 0))]
    names = " ".join(expanded_names)
    total_cards = max(1, len(expanded_names))
    land_count = sum(1 for n in expanded_names if n in {"plains", "island", "swamp", "mountain", "forest"} or "triome" in n)
    creature_like = sum(
        1
        for n in expanded_names
        if any(k in n for k in ["elf", "goblin", "guide", "adeline", "sheoldred", "dragon", "cathar", "spirit", "delver"])
    )
    score = Counter()
    signals: list[str] = []

    def has_any(keys: list[str]) -> bool:
        return any(k in names for k in keys)

    if has_any(["bolt", "spike", "skullcrack", "boros charm", "burn"]):
        score["Burn"] += 4
        score["Aggro"] += 2
        signals.append("direct_damage_package")
    if has_any(["counterspell", "memory deluge", "consider", "teferi", "supreme verdict", "drown in the loch"]):
        score["Control"] += 4
        score["Counter-heavy"] += 3
        signals.append("stack_interaction_package")
    if has_any(["elves", "archdruid", "clancaller", "warmaster", "llanowar"]):
        score["Tribal"] += 4
        score["Aggro"] += 1
        signals.append("tribal_creature_cluster")
    if has_any(["announcement", "raise the alarm", "march of the multitudes", "secure the wastes", "token"]):
        score["Tokens"] += 4
        signals.append("token_production_density")
    if has_any(["cultivate", "arboreal grazer", "nissa, who shakes the world", "ugin", "topiary"]):
        score["Ramp"] += 4
        score["Midrange"] += 1
        signals.append("mana_acceleration_package")
    if has_any(["blood artist", "zulaport", "cauldron familiar", "witch's oven", "priest of forgotten gods"]):
        score["Drain"] += 4
        score["Aristocrats"] += 4
        signals.append("sacrifice_drain_engine")
    if has_any(["delver", "sprite dragon", "brazen borrower", "unholy heat", "expressive iteration"]):
        score["Tempo"] += 4
        signals.append("cheap_threat_plus_interaction")
    if has_any(["fatal push", "go for the throat", "abrupt decay", "ossification", "brutal cathar"]):
        score["Removal-heavy"] += 3
        score["Midrange"] += 2
        signals.append("high_removal_density")
    if has_any(["reanimate", "return target creature card from your graveyard"]):
        score["Reanimator"] += 4
        signals.append("graveyard_recursion_package")

    # shape-based priors
    if land_count >= 25:
        score["Control"] += 1
        score["Ramp"] += 1
    if land_count <= 21:
        score["Aggro"] += 1
        score["Tempo"] += 1
    if creature_like / total_cards >= 0.35:
        score["Aggro"] += 1
        score["Midrange"] += 1
    if creature_like / total_cards <= 0.18:
        score["Control"] += 1

    if not score:
        score["Midrange"] = 1
        signals.append("fallback_midrange")

    ranked = score.most_common()
    primary, primary_score = ranked[0]
    secondary = ranked[1][0] if len(ranked) > 1 else primary
    confidence = round(primary_score / max(1, sum(score.values())), 3)
    return {
        "primary_archetype": primary,
        "secondary_archetype": secondary,
        "confidence": confidence,
        "scores": {k: int(v) for k, v in score.items()},
        "signals": signals,
        "land_count_estimate": int(land_count),
        "creature_density_estimate": round(creature_like / total_cards, 3),
    }
