from __future__ import annotations

from collections import Counter
import re

from card_data.tactical import tactical_tags
from rules_engine.mana import mana_value, parse_mana_cost
from rules_engine.card_types import is_land_card, creature_subtype_candidates

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
        name, type_line, oracle_text, mana_cost, face_stats = _summarize_card_metadata(meta, item)
        for _ in range(quantity):
            expanded_cards.append(
                {
                    "name": name,
                    "type_line": type_line,
                    "oracle_text": oracle_text,
                    "mana_cost": mana_cost,
                    "face_stats": face_stats,
                    "role_faces": meta.get("card_faces") or item.get("card_faces") or [],
                }
            )
    texts = " ".join(card["oracle_text"].lower() for card in expanded_cards)
    for card in expanded_cards:
        faces = card["role_faces"]
        if isinstance(faces, list) and faces:
            card["tags"] = set().union(*(tactical_tags(face.get("oracle_text", ""), face.get("type_line", ""))
                                        for face in faces if isinstance(face, dict) and not is_land_card(face)))
        else:
            card["tags"] = tactical_tags(card["oracle_text"], card["type_line"])
    total_cards = max(1, len(expanded_cards))
    known_cards = sum(bool(card["type_line"]) for card in expanded_cards)
    land_count = sum(1 for card in expanded_cards if is_land_card(card))
    creatures = [card for card in expanded_cards if "creature" in card["type_line"].split("//", 1)[0].lower()]
    creature_like = len(creatures)
    avg_cmc = sum(_cmc(card["mana_cost"]) for card in expanded_cards) / total_cards
    cheap_spells = sum(1 for card in expanded_cards if card["type_line"] and _cmc(card["mana_cost"]) <= 2 and not is_land_card(card))
    expensive_spells = sum(1 for card in expanded_cards if _cmc(card["mana_cost"]) >= 5)
    def tagged(*tags):
        return sum(bool(card["tags"].intersection(tags)) for card in expanded_cards if not is_land_card(card))
    burn_cards = tagged("burn")
    draw_cards = tagged("draw") + sum(_card_text_matches(card, ["scry", "surveil"]) and "draw" not in card["tags"] for card in expanded_cards)
    counter_cards = tagged("counter")
    removal_cards = tagged("removal", "sweeper")
    ramp_cards = tagged("ramp")
    token_cards = tagged("token")
    graveyard_cards = tagged("recursion", "reanimate", "mill", "discard")
    reanimate_cards = tagged("reanimate")
    drain_cards = tagged("drain")
    sacrifice_cards = tagged("sacrifice")
    cheap_creatures = sum(_cmc(card["mana_cost"]) <= 2 for card in creatures)
    subtypes = Counter()
    for card in creatures:
        front = re.split(r"—| - ", card["type_line"].split("//", 1)[0], maxsplit=1)
        if len(front) > 1:
            subtypes.update(set(front[1].lower().split()))
    tribal_references = re.findall(r"\b([a-z]+)(?: creatures)? you control\b", texts)
    rule_words = set().union(*(creature_subtype_candidates(word) for word in tribal_references)) if tribal_references else set()
    tribal_cluster = any(count >= max(8, total_cards // 5) and subtype in rule_words for subtype, count in subtypes.items())
    face_card_count = sum(1 for card in expanded_cards if card.get("face_stats", {}).get("face_count", 0) > 1)
    split_card_count = sum(1 for card in expanded_cards if card.get("face_stats", {}).get("split_like", False))
    score = Counter()
    signals: list[str] = []

    if burn_cards >= max(8, total_cards // 5):
        score["Burn"] += 4
        score["Aggro"] += 2
        signals.append("direct_damage_package")
    if counter_cards >= 4:
        score["Control"] += 4
        score["Counter-heavy"] += 3
        signals.append("stack_interaction_package")
    if tribal_cluster:
        score["Tribal"] += 6
        score["Aggro"] += 1
        signals.append("tribal_creature_cluster")
    if token_cards >= 4:
        score["Tokens"] += 4
        signals.append("token_production_density")
    if ramp_cards >= 4:
        score["Ramp"] += 4
        score["Midrange"] += 1
        signals.append("mana_acceleration_package")
    if drain_cards >= max(4, total_cards // 8) and (sacrifice_cards >= 3 or tagged("death") >= 3):
        score["Drain"] += 6
        score["Aristocrats"] += 6
        signals.append("sacrifice_drain_engine")
    if cheap_creatures >= max(6, total_cards // 10) and counter_cards >= 4:
        score["Tempo"] += 7
        signals.append("cheap_threat_plus_interaction")
    if removal_cards >= 4:
        score["Removal-heavy"] += 3
        score["Midrange"] += 2
        signals.append("high_removal_density")
    if reanimate_cards >= 4:
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
    if split_card_count >= max(2, total_cards // 10):
        score["Tempo"] += 1
        score["Control"] += 1
    if face_card_count >= max(3, total_cards // 8):
        score["Midrange"] += 1
        score["Control"] += 1
    if cheap_spells >= max(8, total_cards // 3) and creature_like >= total_cards * 0.25:
        score["Aggro"] += 1
        score["Burn"] += 1
    if 2.2 <= avg_cmc <= 3.8 and creature_like >= total_cards * 0.25 and draw_cards + removal_cards >= 6:
        score["Midrange"] += 2
    if token_cards >= 6 and tagged("anthem"):
        score["Tokens"] += 1
    if tribal_cluster and creature_like >= total_cards * 0.3:
        score["Tribal"] += 2

    if not score:
        score["Midrange"] = 1
        signals.append("fallback_midrange")

    if not known_cards:
        score = Counter({"Midrange": 1})
        signals = ["missing_card_metadata", "fallback_midrange"]
    elif known_cards < len(expanded_cards):
        signals.append("partial_card_metadata")

    ranked = score.most_common()
    primary, primary_score = ranked[0]
    secondary = ranked[1][0] if len(ranked) > 1 else primary
    confidence = round(primary_score / max(1, sum(score.values())) * known_cards / total_cards, 3)
    return {
        "primary_archetype": primary,
        "secondary_archetype": secondary,
        "confidence": confidence,
        "scores": {k: int(v) for k, v in score.items()},
        "signals": signals,
        "land_count_estimate": int(land_count),
        "creature_density_estimate": round(creature_like / total_cards, 3),
        "avg_cmc_estimate": round(avg_cmc, 3),
        "face_card_count_estimate": int(face_card_count),
        "split_card_count_estimate": int(split_card_count),
        "type_metadata_coverage": round(known_cards / total_cards, 3),
    }


def _cmc(mana_cost: str) -> int:
    return int(mana_value(mana_cost or ""))


def _card_text_matches(card: dict, keys: list[str]) -> bool:
    text = str(card.get("oracle_text", "")).lower()
    return any(key in text for key in keys)


def _summarize_card_metadata(meta: dict, item: dict) -> tuple[str, str, str, str, dict]:
    name = str(meta.get("name") or item.get("card_name") or "").strip()
    type_line = str(meta.get("type_line") or item.get("type_line") or "").strip()
    oracle_text = str(meta.get("oracle_text") or item.get("oracle_text") or "").strip()
    mana_cost = str(meta.get("mana_cost") or item.get("mana_cost") or "").strip()
    faces = meta.get("card_faces") or item.get("card_faces") or []
    face_names: list[str] = []
    face_types: list[str] = []
    face_oracles: list[str] = []
    face_mana_costs: list[str] = []
    split_like = False
    for face in faces if isinstance(faces, list) else []:
        if not isinstance(face, dict):
            continue
        face_name = str(face.get("name") or "").strip()
        face_type = str(face.get("type_line") or "").strip()
        face_oracle = str(face.get("oracle_text") or "").strip()
        face_mana = str(face.get("mana_cost") or "").strip()
        if face_name:
            face_names.append(face_name)
        if face_type:
            face_types.append(face_type)
        if face_oracle:
            face_oracles.append(face_oracle)
        if face_mana:
            face_mana_costs.append(face_mana)
    if len(face_names) > 1:
        layout = str(meta.get("layout") or item.get("layout") or "").lower()
        split_like = layout == "split" or (not layout and " // " in name)
    if face_types:
        type_line = " // ".join([part for part in [type_line, " | ".join(face_types)] if part]).strip()
    if face_oracles:
        oracle_text = " ".join([part for part in [oracle_text, " ".join(face_oracles)] if part]).strip()
    if not mana_cost and face_mana_costs:
        mana_cost = _derive_face_based_mana_cost(face_mana_costs, split_like)
    if not name and face_names:
        name = " // ".join(face_names)
    face_stats = {
        "face_count": len(face_names) or (1 if oracle_text or type_line or mana_cost else 0),
        "split_like": split_like,
    }
    return name, type_line, oracle_text, mana_cost, face_stats


def _derive_face_based_mana_cost(face_mana_costs: list[str], split_like: bool) -> str:
    costs = [cost.strip() for cost in face_mana_costs if cost.strip()]
    if not costs:
        return ""
    if split_like:
        return " ".join(costs).strip()
    return costs[0]
