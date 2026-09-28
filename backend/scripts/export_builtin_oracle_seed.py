from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path

from decks.builtin_decks import BUILTIN_DECKS


EXTRA_NAMES = (
    "Farewell", "Hallowed Fountain", "March of Otherworldly Light",
    "Supreme Verdict", "Teferi, Hero of Dominaria", "The Wandering Emperor",
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


def export_seed(database: Path) -> dict:
    with sqlite3.connect(f"file:{database.resolve()}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM cardcache").fetchall()
    cards: dict[str, dict] = {}
    for requested in sorted(builtin_names(), key=str.casefold):
        matches = [row for row in rows if row["name"].casefold() == requested.casefold()
                   or row["name"].casefold().startswith(requested.casefold() + " // ")]
        if not matches:
            raise ValueError(f"No canonical cached card for {requested}")
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
    return {"source": "Scryfall card cache; starting loyalty verified via exact-name API on 2026-09-28", "cards": cards}


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
