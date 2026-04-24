from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from persistence.repository import Repository


@dataclass
class ParsedDeck:
    mainboard: list[dict[str, Any]]
    sideboard: list[dict[str, Any]]
    errors: list[str]
    suggestions: list[dict[str, Any]]


DECK_LINE = re.compile(r"^\s*(\d+)\s+(.+?)\s*$")


class DeckParser:
    def __init__(self, repo: Repository):
        self.repo = repo

    def parse(self, deck_text: str) -> ParsedDeck:
        section = "mainboard"
        mainboard: list[dict[str, Any]] = []
        sideboard: list[dict[str, Any]] = []
        errors: list[str] = []
        suggestions: list[dict[str, Any]] = []
        cards = self.repo.list_cards()
        known_names = {c.name.lower(): c.name for c in cards}

        for idx, raw in enumerate(deck_text.splitlines(), start=1):
            line = raw.strip()
            if not line:
                continue
            if line.lower().startswith("sideboard"):
                section = "sideboard"
                continue
            match = DECK_LINE.match(line)
            if not match:
                errors.append(f"Line {idx}: could not parse '{line}'")
                continue
            qty = int(match.group(1))
            name = match.group(2).strip()
            canonical = known_names.get(name.lower())
            if canonical is None:
                from card_data.search import fuzzy_card_lookup

                suggestion, score = fuzzy_card_lookup(name, cards)
                suggestions.append({"line": idx, "input": name, "suggestion": suggestion, "score": score})
                canonical = suggestion or name
            item = {"quantity": qty, "card_name": canonical}
            if section == "mainboard":
                mainboard.append(item)
            else:
                sideboard.append(item)

        total_cards = sum(c["quantity"] for c in mainboard)
        if total_cards < 60:
            errors.append(f"Mainboard has {total_cards} cards. Minimum is 60.")
        return ParsedDeck(mainboard=mainboard, sideboard=sideboard, errors=errors, suggestions=suggestions)
