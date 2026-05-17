from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from card_data.placeholders import ensure_placeholder_image
from persistence.repository import Repository

SCRYFALL_NAMED_URL = "https://api.scryfall.com/cards/named"
CACHE_DIR = Path(__file__).resolve().parent / "image_cache"
CACHE_ROUTE_PREFIX = "/card-images"


class ScryfallSyncService:
    def __init__(self, repository: Repository):
        self.repository = repository
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _normalize_payload(self, raw: dict[str, Any], image_uri: str | None) -> dict[str, Any]:
        face = None
        if raw.get("card_faces"):
            face = raw["card_faces"][0]
        type_line = raw.get("type_line") or (face.get("type_line") if face else "") or ""
        if not image_uri:
            image_uri = ensure_placeholder_image(name=raw.get("name", "Card"), type_line=type_line, token=False)
        return {
            "scryfall_id": raw["id"],
            "name": raw["name"],
            "oracle_text": raw.get("oracle_text") or (face.get("oracle_text") if face else "") or "",
            "mana_cost": raw.get("mana_cost") or (face.get("mana_cost") if face else "") or "",
            "type_line": type_line,
            "colors": ",".join(raw.get("colors", [])),
            "power": raw.get("power") or (face.get("power") if face else None),
            "toughness": raw.get("toughness") or (face.get("toughness") if face else None),
            "image_uri": image_uri,
            "legalities_json": json.dumps(raw.get("legalities", {})),
        }

    def sync_card_by_name(self, name: str, force: bool = False) -> dict[str, Any]:
        cached = self.repository.get_cached_card_by_name(name)
        if cached and not force and self._cached_image_available(cached.image_uri):
            return self._serialize_card(cached)

        with httpx.Client(timeout=20) as client:
            response = client.get(SCRYFALL_NAMED_URL, params={"fuzzy": name})
            response.raise_for_status()
            raw = response.json()
            remote_image_uri = self._extract_remote_image_uri(raw)
            image_uri = self._cache_image(raw["id"], remote_image_uri, client) if remote_image_uri else None
        payload = self._normalize_payload(raw, image_uri=image_uri or remote_image_uri)
        card = self.repository.upsert_card(payload)
        return self._serialize_card(card)

    def _extract_remote_image_uri(self, raw: dict[str, Any]) -> str | None:
        # Prefer stable "normal", then gracefully fall back through other known Scryfall sizes.
        preferred_sizes = ("normal", "large", "png", "small", "art_crop", "border_crop")
        image_uris = raw.get("image_uris") or {}
        for key in preferred_sizes:
            uri = image_uris.get(key)
            if uri:
                return uri
        for face in raw.get("card_faces") or []:
            face_uris = face.get("image_uris") or {}
            for key in preferred_sizes:
                uri = face_uris.get(key)
                if uri:
                    return uri
        return None

    def _cache_image(self, scryfall_id: str, remote_uri: str, client: httpx.Client) -> str | None:
        ext = Path(urlparse(remote_uri).path).suffix or ".jpg"
        target = CACHE_DIR / f"{scryfall_id}{ext}"
        if target.exists():
            return f"{CACHE_ROUTE_PREFIX}/{target.name}"
        try:
            res = client.get(remote_uri)
            res.raise_for_status()
            target.write_bytes(res.content)
            return f"{CACHE_ROUTE_PREFIX}/{target.name}"
        except Exception:
            return None

    def _cached_image_available(self, image_uri: str | None) -> bool:
        if not image_uri:
            return False
        if image_uri.startswith("http://") or image_uri.startswith("https://"):
            return False
        if not image_uri.startswith(f"{CACHE_ROUTE_PREFIX}/"):
            return False
        image_name = image_uri.split("/", 2)[-1]
        return (CACHE_DIR / image_name).exists()

    def _serialize_card(self, card) -> dict[str, Any]:
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
