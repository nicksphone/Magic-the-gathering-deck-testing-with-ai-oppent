from __future__ import annotations

import re


_UNSUPPORTED_PATTERNS = (
    ("bands with other", re.compile(r"\bbands with other\b", re.IGNORECASE)),
    ("morph", re.compile(r"\bmorph\b", re.IGNORECASE)),
    ("manifest", re.compile(r"\bmanifest(?:ed|ing)?\b", re.IGNORECASE)),
    ("suspend", re.compile(r"\bsuspend(?:ed|ing)?\b", re.IGNORECASE)),
    ("mutate", re.compile(r"\bmutat(?:e|ed|ing)\b", re.IGNORECASE)),
    ("craft", re.compile(r"\bcraft\b", re.IGNORECASE)),
    ("discover", re.compile(r"\bdiscover\b", re.IGNORECASE)),
)


def known_unsupported_mechanics(oracle_text: str, card_faces: list[dict] | None = None) -> list[str]:
    """Known gaps only; an empty result is not rules certification."""
    texts = [oracle_text or "", *(str(face.get("oracle_text") or "") for face in card_faces or [] if isinstance(face, dict))]
    return [name for name, pattern in _UNSUPPORTED_PATTERNS if any(pattern.search(value) for value in texts)]


def deck_pair_coverage(deck_a: list[dict], deck_b: list[dict]) -> dict:
    """Report known gaps without implying certification for the remaining cards."""
    return {
        "status": "exploratory",
        "known_unsupported_cards": [
            {"deck": label, "card_name": item.get("card_name", ""), "mechanics": mechanics}
            for label, deck in (("A", deck_a), ("B", deck_b))
            for item in deck
            if (mechanics := known_unsupported_mechanics(str(item.get("oracle_text") or ""), item.get("card_faces")))
        ],
    }
