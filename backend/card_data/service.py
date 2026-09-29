from __future__ import annotations

import json

from card_data.display import select_display_image_uri
from card_data.fallback_cards import fallback_card_payload
from card_data.search import fuzzy_card_lookup
from card_data.sync import ScryfallSyncService
from persistence.models import CardCache
from persistence.repository import Repository
from rules_engine.card_types import is_land_card
from rules_engine.coverage import known_unsupported_mechanics


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
        knowledge_names = self.repo.list_card_knowledge_names() if hasattr(self.repo, "list_card_knowledge_names") else []
        suggestion, score = fuzzy_card_lookup(raw_name, [*cards, *knowledge_names])
        return {"input": raw_name, "suggestion": suggestion, "score": score}

    def completeness_report(self, names: list[str]) -> dict:
        requested = [name.strip() for name in names if name and name.strip()]
        cached = self.repo.get_cached_cards_by_names(requested)
        knowledge = {
            row.name.casefold(): row for row in self.repo.list_card_knowledge(requested)
        } if hasattr(self.repo, "list_card_knowledge") else {}
        cards: list[dict] = []
        for name in requested:
            card = cached.get(name.lower())
            profile = ScryfallSyncService.canonical_local_profile(knowledge.get(name.casefold()), name)
            raw = profile["card_data"] if profile else {}
            fallback = fallback_card_payload(name) or {}
            cached_faces = json.loads(getattr(card, "card_faces_json", "[]") or "[]") if card else []
            faces = cached_faces or raw.get("card_faces") or []
            rulings = json.loads(getattr(card, "rulings_json", "[]") or "[]") if card else []
            type_line = str((getattr(card, "type_line", "") if card else "") or raw.get("type_line") or fallback.get("type_line") or "")
            oracle_text = str((getattr(card, "oracle_text", "") if card else "") or raw.get("oracle_text") or fallback.get("oracle_text") or "")
            if card and card.oracle_text:
                oracle_source = "cache"
            elif raw:
                oracle_source = "knowledge"
            elif fallback.get("oracle_text"):
                oracle_source = "fallback"
            else:
                oracle_source = "cache" if card and card.type_line else "missing"
            unsupported_mechanics = known_unsupported_mechanics(oracle_text, faces)
            image_source = card if card and card.image_uri else {
                "image_uri": ScryfallSyncService._extract_remote_image_uri(raw) if raw else None,
                "card_faces": faces,
            }
            image_uri = select_display_image_uri(
                image_source,
                name=name,
                type_line=type_line,
            )
            has_placeholder = "placeholder-" in image_uri or "generic-token" in image_uri
            cards.append(
                {
                    "name": name,
                    "cached": card is not None,
                    "oracle": bool(oracle_text or (oracle_source in {"cache", "knowledge"} and type_line)),
                    "oracle_source": oracle_source,
                    "unsupported_mechanics": unsupported_mechanics,
                    "rules_coverage": "known_unsupported" if unsupported_mechanics else "not_certified",
                    "mana_cost": bool((getattr(card, "mana_cost", "") if card else "") or raw.get("mana_cost") or fallback.get("mana_cost") or is_land_card({"name": name, "type_line": type_line})),
                    "type_line": bool(type_line),
                    "legalities": bool(json.loads(getattr(card, "legalities_json", "{}") or "{}")) or bool(raw.get("legalities")),
                    "rulings": bool(profile.get("rulings_verified") is True) if profile else bool(rulings),
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
        unsupported_count = sum(bool(card["unsupported_mechanics"]) for card in cards)
        return {"requested": len(requested), "complete": sum(1 for card in cards if card["oracle_source"] in {"cache", "knowledge"} and card["type_line"]), "missing": missing, "unsupported_count": unsupported_count, "cards": cards}
