from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


_SEED_PATH = Path(__file__).with_name("builtin_oracle_seed.json")
FALLBACK_CARD_DATA: dict[str, dict[str, Any]] = json.loads(_SEED_PATH.read_text(encoding="utf-8"))["cards"]


def _normalize_card_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (name or "").strip().lower()).strip()


_NORMALIZED_FALLBACK_CARD_DATA = {
    _normalize_card_name(alias): payload
    for requested, payload in FALLBACK_CARD_DATA.items()
    for alias in (requested, str(payload["name"]))
}


def fallback_card_payload(name: str) -> dict[str, Any] | None:
    normalized = _normalize_card_name(name)
    payload = _NORMALIZED_FALLBACK_CARD_DATA.get(normalized)
    if payload is not None:
        return payload
    if "//" in name:
        return _NORMALIZED_FALLBACK_CARD_DATA.get(_normalize_card_name(name.split("//", 1)[0]))
    return None
