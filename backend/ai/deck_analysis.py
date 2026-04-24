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
    names = " ".join(item["card_name"].lower() for item in mainboard for _ in range(item["quantity"]))
    score = Counter()
    if any(k in names for k in ["bolt", "spike", "skullcrack", "burn"]):
        score["Burn"] += 3
        score["Aggro"] += 2
    if any(k in names for k in ["counterspell", "deluge", "teferi", "verdict"]):
        score["Control"] += 3
        score["Counter-heavy"] += 2
    if any(k in names for k in ["elves", "tribal", "archdruid"]):
        score["Tribal"] += 3
    if any(k in names for k in ["token", "announcement", "alarm", "march"]):
        score["Tokens"] += 3
    if any(k in names for k in ["cultivate", "ramp", "topiary"]):
        score["Ramp"] += 3
    if any(k in names for k in ["blood artist", "zulaport", "familiar", "oven"]):
        score["Drain"] += 3
        score["Aristocrats"] += 2
    if any(k in names for k in ["delver", "sprite", "borrower"]):
        score["Tempo"] += 3
    if any(k in names for k in ["push", "go for the throat", "decay"]):
        score["Removal-heavy"] += 2
        score["Midrange"] += 2
    if not score:
        return "Midrange"
    return score.most_common(1)[0][0]
