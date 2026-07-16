from __future__ import annotations

import json
from collections.abc import Callable


_ARCHETYPE_PRIORITY = [
    "Aggro",
    "Burn",
    "Midrange",
    "Control",
    "Tempo",
    "Ramp",
    "Drain",
    "Aristocrats",
    "Reanimator",
    "Tokens",
    "Tribal",
    "Combo-lite",
    "Counter-heavy",
    "Removal-heavy",
    "unknown",
]


def select_representative_decks(
    rows,
    max_decks: int,
    *,
    guess_archetype_fn: Callable[[list[dict]], str],
) -> list[dict]:
    max_decks = max(2, int(max_decks or 0))
    annotated: list[dict] = []
    for row in rows:
        row_name = _row_get(row, "name", "")
        row_mainboard_json = _row_get(row, "mainboard_json", "[]")
        row_archetype = (_row_get(row, "archetype_guess", "") or "").strip()
        mainboard = json.loads(row_mainboard_json)
        archetype = row_archetype
        if not archetype or archetype.lower() == "unknown":
            archetype = guess_archetype_fn(mainboard)
        annotated.append(
            {
                "name": row_name,
                "mainboard": mainboard,
                "archetype": archetype,
            }
        )

    ordered_archetypes: list[str] = []
    for arch in _ARCHETYPE_PRIORITY:
        if any(item["archetype"] == arch for item in annotated):
            ordered_archetypes.append(arch)
    for item in annotated:
        if item["archetype"] not in ordered_archetypes:
            ordered_archetypes.append(item["archetype"])

    selected: list[dict] = []
    seen_names: set[str] = set()
    for archetype in ordered_archetypes:
        for item in annotated:
            if item["archetype"] != archetype or item["name"] in seen_names:
                continue
            selected.append(item)
            seen_names.add(item["name"])
            break
        if len(selected) >= max_decks:
            return selected[:max_decks]

    if len(selected) < max_decks:
        for item in annotated:
            if item["name"] in seen_names:
                continue
            selected.append(item)
            seen_names.add(item["name"])
            if len(selected) >= max_decks:
                break

    return selected[:max_decks]


def _row_get(row, key: str, default):
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)
