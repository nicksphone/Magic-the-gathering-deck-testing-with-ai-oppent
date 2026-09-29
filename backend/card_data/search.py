from __future__ import annotations

import re

from rapidfuzz import fuzz

from persistence.models import CardCache


_DECKLIST_ANNOTATION_RE = re.compile(r"\s*[\[(]\s*[A-Za-z0-9]{2,8}\s*[\])]$", re.IGNORECASE)


def normalize_card_lookup_name(name: str) -> str:
    text = (name or "").strip()
    text = re.sub(r"^\s*[\[(]\s*[A-Za-z0-9]{2,8}\s*[\])]\s*", "", text)
    text = _DECKLIST_ANNOTATION_RE.sub("", text)
    text = re.sub(r"\s+", " ", text)
    return text


def fuzzy_card_lookup(name: str, cards: list[CardCache | str], threshold: int = 72) -> tuple[str | None, int]:
    normalized_name = normalize_card_lookup_name(name).lower()
    best_score = 0
    best_name = None
    for card in cards:
        candidate = card if isinstance(card, str) else card.name
        score = fuzz.ratio(normalized_name, normalize_card_lookup_name(candidate).lower())
        if score > best_score:
            best_score = score
            best_name = candidate
    if best_score < threshold:
        return None, best_score
    return best_name, best_score
