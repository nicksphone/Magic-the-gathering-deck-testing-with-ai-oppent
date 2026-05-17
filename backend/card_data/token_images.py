from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from card_data.placeholders import ensure_placeholder_image
from card_data.sync import CACHE_DIR, CACHE_ROUTE_PREFIX

SCRYFALL_SEARCH_URL = "https://api.scryfall.com/cards/search"
_TOKEN_IMAGE_CACHE: dict[tuple[str, int, int], str] = {}
_COLOR_WORDS = {"white", "blue", "black", "red", "green", "colorless"}


def resolve_token_image_uri(name: str, power: int, toughness: int) -> str:
    key = ((name or "token").strip().lower(), int(power), int(toughness))
    cached = _TOKEN_IMAGE_CACHE.get(key)
    if cached:
        return cached

    image = _search_scryfall_token_image(name, power, toughness)
    if image:
        _TOKEN_IMAGE_CACHE[key] = image
        return image

    fallback = ensure_placeholder_image(name=name, type_line="Token Creature", token=True)
    _TOKEN_IMAGE_CACHE[key] = fallback
    return fallback


def _search_scryfall_token_image(name: str, power: int, toughness: int) -> str | None:
    token_name = (name or "Token").strip()
    simplified = " ".join(
        part for part in token_name.split() if part.strip().lower() not in _COLOR_WORDS and part.strip().lower() != "token"
    ).strip()
    queries = [
        f't:token "{token_name}" pow={int(power)} tou={int(toughness)}',
        f't:token "{simplified}" pow={int(power)} tou={int(toughness)}' if simplified else "",
        f't:token "{simplified}"' if simplified else "",
        "t:token game:paper",
    ]
    queries = [q for q in queries if q]
    try:
        with httpx.Client(timeout=8) as client:
            for q in queries:
                res = client.get(SCRYFALL_SEARCH_URL, params={"q": q, "order": "released", "dir": "desc"})
                if res.status_code != 200:
                    continue
                data = (res.json() or {}).get("data") or []
                for row in data:
                    uri = _extract_image_uri(row)
                    if uri:
                        cached = _cache_remote_token_image(row, uri, client)
                        return cached or uri
    except Exception:
        return None
    return None


def _extract_image_uri(raw: dict[str, Any]) -> str | None:
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


def _cache_remote_token_image(raw: dict[str, Any], remote_uri: str, client: httpx.Client) -> str | None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    sid = str(raw.get("id") or "").strip()
    if not sid:
        return None
    ext = Path(urlparse(remote_uri).path).suffix or ".jpg"
    target = CACHE_DIR / f"token-{sid}{ext}"
    if target.exists():
        return f"{CACHE_ROUTE_PREFIX}/{target.name}"
    try:
        res = client.get(remote_uri, timeout=12)
        res.raise_for_status()
        target.write_bytes(res.content)
        return f"{CACHE_ROUTE_PREFIX}/{target.name}"
    except Exception:
        return None
