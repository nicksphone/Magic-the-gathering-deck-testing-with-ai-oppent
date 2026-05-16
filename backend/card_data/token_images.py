from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

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

    fallback = _ensure_generic_token_svg()
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
                        return uri
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


def _ensure_generic_token_svg() -> str:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / "generic-token-creature.svg"
    if not path.exists():
        path.write_text(
            (
                "<svg xmlns='http://www.w3.org/2000/svg' width='488' height='680' viewBox='0 0 488 680'>"
                "<defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>"
                "<stop offset='0%' stop-color='#1f2937'/><stop offset='100%' stop-color='#111827'/>"
                "</linearGradient></defs>"
                "<rect width='488' height='680' fill='url(#g)'/>"
                "<rect x='24' y='24' width='440' height='632' rx='22' fill='none' stroke='#9ca3af' stroke-width='4'/>"
                "<text x='244' y='320' font-family='Georgia,serif' font-size='42' fill='#e5e7eb' text-anchor='middle'>"
                "Creature Token</text>"
                "<text x='244' y='372' font-family='Georgia,serif' font-size='24' fill='#9ca3af' text-anchor='middle'>"
                "Generic Art</text>"
                "</svg>"
            ),
            encoding="utf-8",
        )
    return f"{CACHE_ROUTE_PREFIX}/{path.name}"

