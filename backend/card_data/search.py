from __future__ import annotations

from rapidfuzz import fuzz

from persistence.models import CardCache


def fuzzy_card_lookup(name: str, cards: list[CardCache], threshold: int = 72) -> tuple[str | None, int]:
    best_score = 0
    best_name = None
    for card in cards:
        score = fuzz.ratio(name.lower(), card.name.lower())
        if score > best_score:
            best_score = score
            best_name = card.name
    if best_score < threshold:
        return None, best_score
    return best_name, best_score
