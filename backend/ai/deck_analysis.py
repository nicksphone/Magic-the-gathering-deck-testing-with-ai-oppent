from __future__ import annotations

from collections import Counter

from rules_engine.mana import parse_mana_cost

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
    expanded_cards = []
    for item in mainboard:
        quantity = max(0, int(item.get("quantity", 0) or 0))
        meta = item.get("card_metadata") or {}
        name = str(meta.get("name") or item.get("card_name") or "").strip()
        type_line = str(meta.get("type_line") or item.get("type_line") or "").strip()
        oracle_text = str(meta.get("oracle_text") or item.get("oracle_text") or "").strip()
        mana_cost = str(meta.get("mana_cost") or item.get("mana_cost") or "").strip()
        for _ in range(quantity):
            expanded_cards.append(
                {
                    "name": name,
                    "type_line": type_line,
                    "oracle_text": oracle_text,
                    "mana_cost": mana_cost,
                }
            )
    names = " ".join(card["name"].lower() for card in expanded_cards)
    texts = " ".join(f"{card['name']} {card['type_line']} {card['oracle_text']}".lower() for card in expanded_cards)
    total_cards = max(1, len(expanded_cards))
    land_count = sum(1 for card in expanded_cards if _looks_like_land(card["name"], card["type_line"], card["oracle_text"]))
    creature_like = sum(1 for card in expanded_cards if "creature" in card["type_line"].lower() or _looks_like_creature_name(card["name"]))
    avg_cmc = sum(_cmc(card["mana_cost"]) for card in expanded_cards) / total_cards
    cheap_spells = sum(1 for card in expanded_cards if _cmc(card["mana_cost"]) <= 2 and "land" not in card["type_line"].lower())
    expensive_spells = sum(1 for card in expanded_cards if _cmc(card["mana_cost"]) >= 5)
    draw_cards = sum(1 for card in expanded_cards if _card_text_matches(card, ["draw", "scry", "impulse", "consider", "memory deluge"]))
    counter_cards = sum(1 for card in expanded_cards if _card_text_matches(card, ["counter target", "counterspell", "drown in the loch"]))
    removal_cards = sum(1 for card in expanded_cards if _card_text_matches(card, ["destroy target", "exile target", "deal", "damage to any target", "go for the throat", "fatal push"]))
    ramp_cards = sum(1 for card in expanded_cards if _card_text_matches(card, ["add ", "cultivate", "ramp", "search your library for a land", "treasure"]))
    token_cards = sum(1 for card in expanded_cards if _card_text_matches(card, ["create a", "create two", "token", "warrior", "soldier", "human token"]))
    graveyard_cards = sum(1 for card in expanded_cards if _card_text_matches(card, ["graveyard", "reanimate", "return target creature card", "mill", "discard"]))
    score = Counter()
    signals: list[str] = []

    def has_any(keys: list[str]) -> bool:
        return any(k in texts for k in keys)

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
    if avg_cmc <= 2.4:
        score["Aggro"] += 1
        score["Tempo"] += 1
        if cheap_spells >= total_cards * 0.35:
            score["Burn"] += 1
    if avg_cmc >= 3.4:
        score["Control"] += 1
        score["Ramp"] += 1
    if draw_cards + counter_cards + removal_cards >= max(6, total_cards // 4):
        score["Control"] += 2
        if counter_cards >= removal_cards:
            score["Counter-heavy"] += 2
    if removal_cards >= max(4, total_cards // 5):
        score["Removal-heavy"] += 2
    if token_cards >= max(4, total_cards // 6):
        score["Tokens"] += 2
    if ramp_cards >= max(3, total_cards // 8):
        score["Ramp"] += 2
    if graveyard_cards >= max(3, total_cards // 8):
        score["Reanimator"] += 2
        score["Drain"] += 1
    if cheap_spells >= max(8, total_cards // 3) and creature_like >= total_cards * 0.25:
        score["Aggro"] += 1
        score["Burn"] += 1
    if 2.2 <= avg_cmc <= 3.8 and creature_like >= total_cards * 0.25 and draw_cards + removal_cards >= 6:
        score["Midrange"] += 2
    if token_cards >= 6 and any(k in texts for k in ["anthem", "+1/+1", "adeline", "wedding announcement"]):
        score["Tokens"] += 1
    if any(k in texts for k in ["elves", "goblins", "humans", "spirits", "soldiers", "zombie"]) and creature_like >= total_cards * 0.3:
        score["Tribal"] += 2

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
        "avg_cmc_estimate": round(avg_cmc, 3),
    }


def _cmc(mana_cost: str) -> int:
    cost = parse_mana_cost(mana_cost or "")
    return int(cost["generic"] + sum(cost[c] for c in ["W", "U", "B", "R", "G"]))


def _looks_like_land(name: str, type_line: str, oracle_text: str) -> bool:
    text = f"{name} {type_line} {oracle_text}".lower()
    if "land" in text:
        return True
    return any(k in text for k in ["{t}: add", "add one mana", "add {w}", "add {u}", "add {b}", "add {r}", "add {g}"])


def _looks_like_creature_name(name: str) -> bool:
    n = (name or "").lower()
    return any(k in n for k in ["elf", "goblin", "guide", "adeline", "sheoldred", "dragon", "cathar", "spirit", "delver", "soldier", "human", "wizard", "zombie"])


def _card_text_matches(card: dict, keys: list[str]) -> bool:
    text = f"{card.get('name', '')} {card.get('type_line', '')} {card.get('oracle_text', '')}".lower()
    return any(key in text for key in keys)
