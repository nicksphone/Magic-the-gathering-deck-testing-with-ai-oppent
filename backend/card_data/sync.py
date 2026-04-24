from __future__ import annotations

import json
from typing import Any

import httpx

from persistence.repository import Repository

SCRYFALL_NAMED_URL = "https://api.scryfall.com/cards/named"


class ScryfallSyncService:
    def __init__(self, repository: Repository):
        self.repository = repository

    def _normalize_payload(self, raw: dict[str, Any]) -> dict[str, Any]:
        face = None
        if raw.get("card_faces"):
            face = raw["card_faces"][0]
        image_uri = raw.get("image_uris", {}).get("normal")
        if image_uri is None and face:
            image_uri = face.get("image_uris", {}).get("normal")
        return {
            "scryfall_id": raw["id"],
            "name": raw["name"],
            "oracle_text": raw.get("oracle_text") or (face.get("oracle_text") if face else "") or "",
            "mana_cost": raw.get("mana_cost") or (face.get("mana_cost") if face else "") or "",
            "type_line": raw.get("type_line") or (face.get("type_line") if face else "") or "",
            "colors": ",".join(raw.get("colors", [])),
            "power": raw.get("power") or (face.get("power") if face else None),
            "toughness": raw.get("toughness") or (face.get("toughness") if face else None),
            "image_uri": image_uri,
            "legalities_json": json.dumps(raw.get("legalities", {})),
        }

    def sync_card_by_name(self, name: str) -> dict[str, Any]:
        with httpx.Client(timeout=20) as client:
            response = client.get(SCRYFALL_NAMED_URL, params={"fuzzy": name})
            response.raise_for_status()
            raw = response.json()
        payload = self._normalize_payload(raw)
        card = self.repository.upsert_card(payload)
        return {
            "id": card.id,
            "scryfall_id": card.scryfall_id,
            "name": card.name,
            "oracle_text": card.oracle_text,
            "mana_cost": card.mana_cost,
            "type_line": card.type_line,
            "colors": card.colors.split(",") if card.colors else [],
            "power": card.power,
            "toughness": card.toughness,
            "image_uri": card.image_uri,
            "legalities": json.loads(card.legalities_json),
        }
