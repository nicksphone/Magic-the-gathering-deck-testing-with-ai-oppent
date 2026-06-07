from __future__ import annotations

import json

from card_data.search import fuzzy_card_lookup
from persistence.models import CardCache
from persistence.repository import Repository


class CardService:
    def __init__(self, repo: Repository):
        self.repo = repo

    def list_cards(self) -> list[dict]:
        cards = self.repo.list_cards()
        return [
            {
                "id": card.id,
                "name": card.name,
                "mana_cost": card.mana_cost,
                "type_line": card.type_line,
                "oracle_text": card.oracle_text,
                "image_uri": card.image_uri,
                "colors": card.colors.split(",") if card.colors else [],
                "legalities": json.loads(card.legalities_json),
                "card_faces": json.loads(getattr(card, "card_faces_json", "[]") or "[]"),
            }
            for card in cards
        ]

    def suggest_name(self, raw_name: str) -> dict[str, str | int | None]:
        cards: list[CardCache] = self.repo.list_cards()
        suggestion, score = fuzzy_card_lookup(raw_name, cards)
        return {"input": raw_name, "suggestion": suggestion, "score": score}
