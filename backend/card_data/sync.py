from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from card_data.http_utils import get_with_backoff
from card_data.fallback_cards import fallback_card_payload
from card_data.placeholders import ensure_placeholder_image
from persistence.repository import Repository

SCRYFALL_NAMED_URL = "https://api.scryfall.com/cards/named"
CACHE_DIR = Path(__file__).resolve().parent / "image_cache"
CACHE_ROUTE_PREFIX = "/card-images"


class ScryfallSyncService:
    def __init__(self, repository: Repository):
        self.repository = repository
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _normalize_payload(self, raw: dict[str, Any], image_uri: str | None, rulings: list[dict[str, Any]] | None = None) -> dict[str, Any]:
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
            "card_faces_json": json.dumps(self._normalize_faces(raw.get("card_faces") or [])),
            "rulings_json": json.dumps(rulings or []),
        }

    def _normalize_faces(self, faces: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for face in faces:
            out.append(
                {
                    "name": face.get("name", ""),
                    "mana_cost": face.get("mana_cost"),
                    "type_line": face.get("type_line"),
                    "oracle_text": face.get("oracle_text"),
                    "power": face.get("power"),
                    "toughness": face.get("toughness"),
                    "image_uri": self._extract_face_image_uri(face),
                }
            )
        return out

    def _extract_face_image_uri(self, face: dict[str, Any]) -> str | None:
        preferred_sizes = ("normal", "large", "png", "small", "art_crop", "border_crop")
        face_uris = face.get("image_uris") or {}
        for key in preferred_sizes:
            uri = face_uris.get(key)
            if uri:
                return uri
        return None

    def sync_card_by_name(self, name: str, force: bool = False) -> dict[str, Any]:
        cached = self.repository.get_cached_card_by_name(name)
        if cached and not force and self._cached_image_available(cached.image_uri):
            return self._serialize_card(cached)

        try:
            with httpx.Client(timeout=20) as client:
                response = get_with_backoff(client, SCRYFALL_NAMED_URL, params={"fuzzy": name}, timeout=20)
                response.raise_for_status()
                raw = response.json()
                remote_image_uri = self._extract_remote_image_uri(raw)
                image_uri = self._cache_image(raw["id"], remote_image_uri, client) if remote_image_uri else None
                rulings = self._fetch_rulings(raw.get("rulings_uri"), client)
        except httpx.HTTPError:
            if cached is not None:
                return self._serialize_card(cached)
            raise
        payload = self._normalize_payload(raw, image_uri=image_uri or remote_image_uri, rulings=rulings)
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

    def _fetch_rulings(self, rulings_uri: str | None, client: httpx.Client) -> list[dict[str, Any]]:
        if not rulings_uri:
            return []
        try:
            response = get_with_backoff(client, rulings_uri, timeout=20)
            response.raise_for_status()
            payload = response.json()
            return [item for item in payload.get("data", []) if isinstance(item, dict)]
        except (httpx.HTTPError, ValueError, TypeError):
            # Rulings are supplemental; a failed lookup must not block gameplay.
            return []

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
        card_name = self._card_attr(card, "name", "")
        fallback = fallback_card_payload(card_name)
        return {
            "id": self._card_attr(card, "id"),
            "scryfall_id": self._card_attr(card, "scryfall_id"),
            "name": card_name,
            "oracle_text": self._card_attr(card, "oracle_text") or (fallback or {}).get("oracle_text", ""),
            "mana_cost": self._card_attr(card, "mana_cost") or (fallback or {}).get("mana_cost", ""),
            "type_line": self._card_attr(card, "type_line") or (fallback or {}).get("type_line", ""),
            "colors": self._parse_colors(self._card_attr(card, "colors")),
            "power": self._card_attr(card, "power") or (fallback or {}).get("power"),
            "toughness": self._card_attr(card, "toughness") or (fallback or {}).get("toughness"),
            "image_uri": self._card_attr(card, "image_uri"),
            "legalities": json.loads(self._card_attr(card, "legalities_json", "{}") or "{}"),
            "card_faces": json.loads(self._card_attr(card, "card_faces_json", "[]") or "[]"),
            "rulings": json.loads(self._card_attr(card, "rulings_json", "[]") or "[]"),
        }

    def _card_attr(self, card, name: str, default=None):  # noqa: ANN001
        if isinstance(card, dict):
            return card.get(name, default)
        return getattr(card, name, default)

    def _parse_colors(self, colors: Any) -> list[str]:
        if not colors:
            return []
        if isinstance(colors, list):
            return [str(color) for color in colors if color]
        if isinstance(colors, str):
            return [part for part in colors.split(",") if part]
        return [str(colors)]
