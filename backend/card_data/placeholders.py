from __future__ import annotations

import html
import re
from pathlib import Path

CACHE_DIR = Path(__file__).resolve().parent / "image_cache"
CACHE_ROUTE_PREFIX = "/card-images"


def ensure_placeholder_image(name: str, type_line: str = "", token: bool = False) -> str:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    family = _family(type_line=type_line, token=token)
    slug = _slug(name, type_line if token else type_line or family)
    filename = f"placeholder-{family}-{slug}.svg"
    path = CACHE_DIR / filename
    if not path.exists():
        path.write_text(_svg_for(family, name=name, type_line=type_line, token=token), encoding="utf-8")
    return f"{CACHE_ROUTE_PREFIX}/{filename}"


def _family(type_line: str, token: bool) -> str:
    if token:
        return "token"
    low = (type_line or "").lower()
    if "land" in low:
        return "land"
    if "creature" in low:
        return "creature"
    if "enchantment" in low:
        return "enchantment"
    if "artifact" in low:
        return "artifact"
    if "instant" in low or "sorcery" in low:
        return "spell"
    if "planeswalker" in low:
        return "planeswalker"
    return "card"


def _slug(*parts: str) -> str:
    text = "-".join(part.strip().lower() for part in parts if part and part.strip())
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text[:80] or "card"


def _svg_for(family: str, *, name: str, type_line: str, token: bool) -> str:
    palette = {
        "token": ("#1f2937", "#111827", "Token"),
        "land": ("#31403b", "#1f2a28", "Land"),
        "creature": ("#3f2f25", "#2a2019", "Creature"),
        "enchantment": ("#28334a", "#1a2234", "Enchantment"),
        "artifact": ("#3d3f45", "#2a2c31", "Artifact"),
        "spell": ("#3a2f4a", "#271f34", "Spell"),
        "planeswalker": ("#4a3524", "#302214", "Planeswalker"),
        "card": ("#25303d", "#18202a", "Card"),
    }
    c1, c2, label = palette.get(family, palette["card"])
    title = html.escape((name or label).strip()[:48])
    subtitle = html.escape((type_line or ("Token" if token else "")).strip()[:72])
    return (
        "<svg xmlns='http://www.w3.org/2000/svg' width='488' height='680' viewBox='0 0 488 680'>"
        "<defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>"
        f"<stop offset='0%' stop-color='{c1}'/><stop offset='100%' stop-color='{c2}'/>"
        "</linearGradient></defs>"
        "<rect width='488' height='680' fill='url(#g)'/>"
        "<rect x='20' y='20' width='448' height='640' rx='22' fill='none' stroke='#9ca3af' stroke-width='4'/>"
        f"<text x='244' y='300' font-family='Georgia,serif' font-size='38' fill='#e5e7eb' text-anchor='middle'>{title}</text>"
        f"<text x='244' y='350' font-family='Georgia,serif' font-size='22' fill='#d1d5db' text-anchor='middle'>{subtitle or label}</text>"
        "<text x='244' y='396' font-family='Georgia,serif' font-size='18' fill='#9ca3af' text-anchor='middle'>Local placeholder art</text>"
        "</svg>"
    )
