from __future__ import annotations

import re


def without_reminder_text(oracle_text: str) -> str:
    """Exclude parenthetical reminder text from executable Oracle clauses."""
    text = oracle_text or ""
    previous = None
    while text != previous:
        previous = text
        text = re.sub(r"\([^()]*\)", "", text)
    return text
