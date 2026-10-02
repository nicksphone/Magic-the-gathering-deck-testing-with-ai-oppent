from __future__ import annotations

import json
import re
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


def needs_split_color_sync(card) -> bool:
    """Older cache writers mistook absent Scryfall face colors for colorless."""
    if (card.get('layout') if isinstance(card, dict) else getattr(card, "layout", "")) != "split":
        return False
    try:
        faces = card.get('card_faces') if isinstance(card, dict) else json.loads(getattr(card, "card_faces_json", "[]") or "[]")
    except (TypeError, ValueError):
        return False
    return isinstance(faces, list) and any(
        isinstance(face, dict) and face.get("colors") == []
        and re.search(r"\{[^}]*[WUBRG][^}]*\}", str(face.get("mana_cost") or ""), re.IGNORECASE)
        and not re.search(r"\bdevoid\b|\bis colorless\b", str(face.get("oracle_text") or ""), re.IGNORECASE)
        for face in faces
    )


class ScryfallSyncService:
    def __init__(self, repository: Repository):
        self.repository = repository
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def _normalize_payload(cls, raw: dict[str, Any], image_uri: str | None, rulings: list[dict[str, Any]] | None = None) -> dict[str, Any]:
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
            "layout": raw.get("layout", ""),
            "colors": ",".join(raw.get("colors") or (face.get("colors", []) if face else [])),
            "power": raw.get("power") or (face.get("power") if face else None),
            "toughness": raw.get("toughness") or (face.get("toughness") if face else None),
            'loyalty': raw.get('loyalty') if raw.get('loyalty') is not None else (face.get('loyalty') if face else None),
            "image_uri": image_uri,
            "legalities_json": json.dumps(raw.get("legalities", {})),
            "card_faces_json": json.dumps(cls._normalize_faces(raw.get("card_faces") or [])),
            "rulings_json": json.dumps(rulings or []),
        }

    @classmethod
    def _normalize_faces(cls, faces: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
                    "loyalty": face.get("loyalty"),
                    "colors": face.get("colors"),
                    "image_uri": cls._extract_face_image_uri(face),
                }
            )
        return out

    @staticmethod
    def _extract_face_image_uri(face: dict[str, Any]) -> str | None:
        preferred_sizes = ("normal", "large", "png", "small", "art_crop", "border_crop")
        face_uris = face.get("image_uris") or {}
        for key in preferred_sizes:
            uri = face_uris.get(key)
            if uri:
                return uri
        return None

    def sync_card_from_local_knowledge(self, name: str) -> bool:
        """Materialize a canonical bulk card without making a network request."""
        profile = self.canonical_local_profile(self.repository.get_card_knowledge(name), name)
        if profile is None:
            return False
        raw = profile["card_data"]
        cached = self.repository.get_cached_card_by_name(name)
        local_image = cached.image_uri if cached and cached.scryfall_id == raw["id"] and self._cached_image_available(cached.image_uri) else None
        rulings = profile.get("rulings") if profile.get("rulings_verified") is True else []
        if not isinstance(rulings, list):
            rulings = []
        payload = self._normalize_payload(raw, local_image or self._extract_remote_image_uri(raw), rulings)
        self.repository.upsert_card(payload)
        return True

    @staticmethod
    def canonical_local_profile(row: Any, name: str) -> dict[str, Any] | None:
        if row is None or row.oracle_source != "scryfall":
            return None
        try:
            profile = json.loads(row.profiles_json)
        except (TypeError, ValueError):
            return None
        raw = profile.get("card_data") if isinstance(profile, dict) else None
        if not isinstance(raw, dict) or raw.get("object") != "card":
            return None
        faces = raw.get('card_faces')
        if faces is not None and (not isinstance(faces, list) or any(not isinstance(face, dict) for face in faces)):
            return None
        if not raw.get("id") or raw["id"] != row.scryfall_id or (not raw.get("type_line") and not raw.get("card_faces")):
            return None
        canonical_name = str(raw.get('name', '')).casefold()
        if canonical_name != row.name.casefold():
            return None
        aliases = {canonical_name}
        if raw.get('layout') != 'art_series' and raw.get('type_line') != 'Card':
            aliases.update(str(face.get('name') or '').casefold() for face in (faces or []))
        if name.strip().casefold() not in aliases:
            return None
        return profile

    def sync_card_by_name(self, name: str, force: bool = False) -> dict[str, Any]:
        cached = self.repository.get_cached_card_by_name(name)
        if cached and not force and self._cached_image_available(cached.image_uri):
            from card_data.hydration import ready_for_match
            metadata = self._serialize_card(cached)
            if ready_for_match(metadata):
                return metadata

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

    @staticmethod
    def _extract_remote_image_uri(raw: dict[str, Any]) -> str | None:
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
            'loyalty': self._card_attr(card, 'loyalty') if self._card_attr(card, 'loyalty') is not None else (fallback or {}).get('loyalty'),
            "image_uri": self._card_attr(card, "image_uri"),
            "legalities": json.loads(self._card_attr(card, "legalities_json", "{}") or "{}"),
            "card_faces": json.loads(self._card_attr(card, "card_faces_json", "[]") or "[]"),
            "layout": self._card_attr(card, "layout", ""),
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
