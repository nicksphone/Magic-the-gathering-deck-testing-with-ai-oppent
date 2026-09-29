from __future__ import annotations

try:  # pragma: no cover - direct CLI execution
    from . import _bootstrap  # noqa: F401
except ImportError:  # pragma: no cover
    import _bootstrap  # noqa: F401

import argparse
import json
import re
import sqlite3
from pathlib import Path

from decks.builtin_decks import BUILTIN_DECKS
from decks.expansion_top_decks import EXPANSION_TOP_DECKS


EXTRA_NAMES = (
    "Farewell", "Hallowed Fountain", "March of Otherworldly Light",
    "Sacred Foundry", "Supreme Verdict", "Teferi, Hero of Dominaria", "The Wandering Emperor",
)
# Verified against Scryfall's exact-name API on 2026-09-28; CardCache omits loyalty.
VERIFIED_LOYALTY = {
    "The Wandering Emperor": "3",
    "Teferi, Hero of Dominaria": "4",
    "Nissa, Who Shakes the World": "5",
    "Ugin, the Spirit Dragon": "7",
}
FACE_FIELDS = ("name", "mana_cost", "type_line", "oracle_text", "power", "toughness", "loyalty", "colors")


def builtin_names() -> set[str]:
    names = set(EXTRA_NAMES)
    for deck in BUILTIN_DECKS.values():
        names.update(re.sub(r"^\d+\s+", "", line.strip()) for line in deck.splitlines() if line.strip())
    return names


def shipped_names() -> set[str]:
    names = builtin_names()
    for entry in EXPANSION_TOP_DECKS:
        for line in entry["deck_text"].splitlines():
            match = re.match(r"^\s*\d+\s*x?\s+(.+?)\s*$", line, re.IGNORECASE)
            if match:
                names.add(match.group(1))
    return names


def _canonical_knowledge_card(conn: sqlite3.Connection, requested: str) -> dict:
    rows = conn.execute(
        "SELECT * FROM cardknowledge WHERE lower(name) = lower(?) OR lower(name) LIKE lower(?) || ' // %'",
        (requested, requested),
    ).fetchall()
    for row in rows:
        if row["oracle_source"] != "scryfall":
            continue
        profile = json.loads(row["profiles_json"] or "{}")
        raw = profile.get("card_data") or {}
        if (raw.get("object") != "card" or raw.get("id") != row["scryfall_id"]
                or not raw.get("oracle_id") or raw.get("name", "").casefold() != row["name"].casefold()
                or raw.get("layout") in {"art_series", "token", "double_faced_token", "emblem"}):
            continue
        faces = raw.get("card_faces") or []
        front = faces[0] if faces else {}
        if raw["name"].casefold() != requested.casefold() and front.get("name", "").casefold() != requested.casefold():
            continue
        card = {
            "scryfall_id": raw["id"],
            "name": raw["name"],
            "oracle_text": front.get("oracle_text") or raw.get("oracle_text") or "",
            "mana_cost": front.get("mana_cost") if "mana_cost" in front else raw.get("mana_cost", ""),
            "type_line": front.get("type_line") or raw.get("type_line") or "",
            "layout": raw.get("layout") or "",
        }
        for key in ("power", "toughness", "loyalty"):
            value = front.get(key) if key in front else raw.get(key)
            if value is not None:
                card[key] = value
        if faces:
            card["card_faces"] = [
                {key: face[key] for key in FACE_FIELDS if face.get(key) is not None}
                for face in faces
            ]
        colors = front.get("colors") or raw.get("colors") or []
        if colors:
            card["colors"] = colors
        if card["type_line"] and (card["oracle_text"] or "Land" in card["type_line"]):
            return card
    raise ValueError(f"No verified canonical cached or bulk card for {requested}")


def export_seed(database: Path) -> dict:
    with sqlite3.connect(f"file:{database.resolve()}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM cardcache").fetchall()
        cards: dict[str, dict] = {}
        for requested in sorted(shipped_names(), key=str.casefold):
            matches = [row for row in rows if row["name"].casefold() == requested.casefold()
                       or row["name"].casefold().startswith(requested.casefold() + " // ")]
            if not matches:
                cards[requested] = _canonical_knowledge_card(conn, requested)
                continue
            row = max(matches, key=lambda item: (len(item["card_faces_json"] or ""), bool(item["oracle_text"])))
            if not row["scryfall_id"] or not row["oracle_text"] or not row["type_line"]:
                raise ValueError(f"Incomplete canonical cached card for {requested}")
            faces = json.loads(row["card_faces_json"] or "[]")
            if not isinstance(faces, list):
                raise ValueError(f"Invalid card faces for {requested}")
            faces = [{key: face.get(key) for key in FACE_FIELDS if face.get(key) is not None} for face in faces]
            front = faces[0] if faces else {}
            layout = row["layout"] or ""
            if len(faces) > 1 and not layout:
                layout = "adventure" if "Adventure" in str(faces[1].get("type_line") or "") else "transform"
            card = {
                "scryfall_id": row["scryfall_id"],
                "name": row["name"],
                "oracle_text": front.get("oracle_text") or row["oracle_text"],
                "mana_cost": front.get("mana_cost") if "mana_cost" in front else row["mana_cost"],
                "type_line": front.get("type_line") or row["type_line"],
                "layout": layout,
            }
            for key in ("power", "toughness"):
                value = front.get(key) if key in front else row[key]
                if value is not None:
                    card[key] = value
            if requested in VERIFIED_LOYALTY:
                card["loyalty"] = VERIFIED_LOYALTY[requested]
            if faces:
                card["card_faces"] = faces
            colors = front.get("colors") or [part for part in (row["colors"] or "").split(",") if part]
            if colors:
                card["colors"] = colors
            cards[requested] = card
    return {"source": "Scryfall card cache and canonical local Oracle bulk; starting loyalty verified via exact-name API on 2026-09-28", "cards": cards}


def main() -> None:
    parser = argparse.ArgumentParser(description="Export verified built-in Oracle metadata from a synced local cache")
    parser.add_argument("--database", type=Path, default=Path(__file__).resolve().parents[1] / "mtg_lab.db")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "card_data" / "builtin_oracle_seed.json")
    args = parser.parse_args()
    payload = export_seed(args.database)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Exported {len(payload['cards'])} verified cards to {args.output}")


if __name__ == "__main__":
    main()
