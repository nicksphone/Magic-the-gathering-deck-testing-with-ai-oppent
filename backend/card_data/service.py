from __future__ import annotations

import json

from card_data.display import select_display_image_uri
from card_data.fallback_cards import fallback_card_payload
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
                "mana_cost": card.mana_cost or (fallback_card_payload(card.name) or {}).get("mana_cost", ""),
                "type_line": card.type_line or (fallback_card_payload(card.name) or {}).get("type_line", ""),
                "oracle_text": card.oracle_text or (fallback_card_payload(card.name) or {}).get("oracle_text", ""),
                "image_uri": select_display_image_uri(card, name=card.name, type_line=card.type_line or ""),
                "colors": card.colors.split(",") if card.colors else [],
                "legalities": json.loads(card.legalities_json),
                "card_faces": json.loads(getattr(card, "card_faces_json", "[]") or "[]"),
                "rulings": json.loads(getattr(card, "rulings_json", "[]") or "[]"),
            }
            for card in cards
        ]

    def suggest_name(self, raw_name: str) -> dict[str, str | int | None]:
        cards: list[CardCache] = self.repo.list_cards()
        suggestion, score = fuzzy_card_lookup(raw_name, cards)
        return {"input": raw_name, "suggestion": suggestion, "score": score}

    def completeness_report(self, names: list[str]) -> dict:
        requested = [name.strip() for name in names if name and name.strip()]
        cached = self.repo.get_cached_cards_by_names(requested)
        cards: list[dict] = []
        for name in requested:
            card = cached.get(name.lower())
            fallback = fallback_card_payload(name) or {}
            faces = json.loads(getattr(card, "card_faces_json", "[]") or "[]") if card else []
            rulings = json.loads(getattr(card, "rulings_json", "[]") or "[]") if card else []
            oracle_source = "cache" if card and card.oracle_text else ("fallback" if fallback.get("oracle_text") else "missing")
            image_uri = select_display_image_uri(
                card,
                name=name,
                type_line=getattr(card, "type_line", "") if card else fallback.get("type_line", ""),
            )
            has_placeholder = "placeholder-" in image_uri or "generic-token" in image_uri
            cards.append(
                {
                    "name": name,
                    "cached": card is not None,
                    "oracle": bool((getattr(card, "oracle_text", "") if card else "") or fallback.get("oracle_text")),
                    "oracle_source": oracle_source,
                    "mana_cost": bool((getattr(card, "mana_cost", "") if card else "") or fallback.get("mana_cost")),
                    "type_line": bool((getattr(card, "type_line", "") if card else "") or fallback.get("type_line")),
                    "legalities": bool(json.loads(getattr(card, "legalities_json", "{}") or "{}")) if card else False,
                    "rulings": bool(rulings),
                    "faces": faces,
                    "faces_complete": all(face.get("name") and face.get("type_line") for face in faces) if faces else True,
                    "image_uri": image_uri,
                    "placeholder_image": has_placeholder,
                }
            )
        missing = {
            field: sum(1 for card in cards if not card[field])
            for field in ("cached", "oracle", "mana_cost", "type_line", "legalities", "rulings", "faces_complete")
        }
        missing["real_image"] = sum(1 for card in cards if card["placeholder_image"])
        return {"requested": len(requested), "complete": len(cards) - sum(1 for card in cards if card["oracle_source"] == "missing" or not card["cached"]), "missing": missing, "cards": cards}
