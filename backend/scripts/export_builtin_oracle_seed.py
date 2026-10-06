from __future__ import annotations

try:  # pragma: no cover - direct CLI execution
    from . import _bootstrap  # noqa: F401
except ImportError:  # pragma: no cover
    import _bootstrap  # noqa: F401

import argparse
from copy import deepcopy
import gzip
import hashlib
import json
import os
import re
import sqlite3
import tempfile
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
CR_VERSION = "2026-09-25"
CR_SHA256 = "8d860e451f20f38865b725b42d82feb714c725373dd8f3b32b8652b3eeb070ca"
DERIVATION_VERSION = "proposal-1-basic-colored-symbols-reviewed-no-CDA"
DEFAULT_SEED = Path(__file__).resolve().parents[1] / "card_data" / "builtin_oracle_seed.json"


def _raw_hash(raw: dict) -> str:
    return hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def _verified_file(path: Path, expected_hash: str | None) -> None:
    if not expected_hash:
        raise ValueError(f"A pinned SHA256 is required for {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != expected_hash:
        raise ValueError(f"Source SHA256 mismatch: {path}")


def _bulk_cards(path: Path, expected_hash: str | None, ids: set[str]) -> dict:
    _verified_file(path, expected_hash)
    cards = {}
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            raw = json.loads(line)
            if raw.get("id") in ids:
                if raw["id"] in cards:
                    raise ValueError(f"Ambiguous canonical printing: {raw['id']}")
                cards[raw["id"]] = raw
    return cards


def _exact_card(conn: sqlite3.Connection, card: dict, bulk: dict | None, *, required: bool = True) -> dict | None:
    try:
        rows = conn.execute("SELECT * FROM cardknowledge WHERE scryfall_id = ?", (card["scryfall_id"],)).fetchall()
    except sqlite3.OperationalError:
        rows = []
    knowledge = [json.loads(row["profiles_json"] or "{}").get("card_data", {})
                 for row in rows if row["oracle_source"] == "scryfall"]
    if bulk is not None and card["scryfall_id"] in bulk:
        candidates = [bulk[card["scryfall_id"]]]
        if len(knowledge) > 1 or any(raw != candidates[0] for raw in knowledge):
            raise ValueError(f"Conflicting or ambiguous canonical sources: {card['name']}")
    elif bulk is not None and required:
        candidates = []
    else:
        candidates = knowledge
    if not candidates and not required:
        return None
    if len(candidates) != 1:
        raise ValueError(f"Missing or ambiguous exact canonical printing: {card['name']}")
    raw = candidates[0]
    if (raw.get("object") != "card" or raw.get("id") != card["scryfall_id"]
            or not raw.get("oracle_id") or raw.get("name") != card["name"]):
        raise ValueError(f"Canonical printing identity mismatch: {card['name']}")
    return raw


def _valid_colors(value) -> bool:
    return (isinstance(value, list) and all(isinstance(c, str) and c in "WUBRG" and len(c) == 1 for c in value)
            and len(value) == len(set(value)))


def _face_colors(raw: dict, index: int, admission: list) -> tuple[list, str, dict | None]:
    face = raw["card_faces"][index]
    if "colors" in face:
        if not _valid_colors(face["colors"]):
            raise ValueError("Invalid canonical face colors")
        return list(face["colors"]), "canonical_explicit", None
    # Source-hash admission is a reviewed corpus boundary, not Oracle inference.
    cost = face.get("mana_cost")
    if (face.get("object") != "card_face" or "color_indicator" in face
            or not isinstance(face.get("oracle_text"), str) or not isinstance(cost, str)
            or not re.fullmatch(r"(?:\{(?:[0-9]+|[WUBRG])\})+", cost)):
        raise ValueError("Unsupported missing-color face cost/indicator semantics")
    matches = [entry for entry in admission if entry.get("scryfall_id") == raw["id"]
               and entry.get("face_index") == index and entry.get("face_name") == face["name"]
               and entry.get("raw_sha256") == _raw_hash(raw)
               and entry.get("face_oracle_sha256") == hashlib.sha256(face["oracle_text"].encode()).hexdigest()]
    if len(matches) != 1:
        raise ValueError("Missing or ambiguous reviewed full-face color-semantic admission")
    entry = matches[0]
    proof = entry.get("derivation") or {}
    colors = [c for c in "WUBRG" if "{" + c + "}" in cost]
    if (entry.get("fact_kind") != "derived_rule_fact" or entry.get("raw_colors_present") is not False
            or proof.get("contract_version") != DERIVATION_VERSION
            or proof.get("official_cr_sha256") != CR_SHA256
            or proof.get("color_defining_ability_admission") != "reviewed_absent_in_complete_canonical_face_oracle"
            or proof.get("devoid_present") is not False or proof.get("unsupported_color_semantics") != []
            or not proof.get("reviewed_clauses") or entry.get("colors") != colors):
        raise ValueError("Unsupported or conflicting full-face color-semantic admission")
    return colors, "derived_rule_fact", deepcopy(proof)


def _enrich_card(card: dict, raw: dict, admission: list, ledger: list, provenance: dict) -> None:
    facts = []
    staged = deepcopy(card)
    faces = staged.get("card_faces") or []
    canonical = raw.get("card_faces") or []
    if len(faces) != len(canonical) or [f.get("name") for f in faces] != [f.get("name") for f in canonical]:
        raise ValueError(f"Canonical face ordering mismatch: {card['name']}")
    if not faces and any(raw.get(key) != value for key, value in staged.items()
                         if key in {"oracle_text", "type_line", "mana_cost", "power", "toughness"}):
        raise ValueError(f"Existing root fact conflicts with canonical printing: {card['name']}")
    for index, (face, source) in enumerate(zip(faces, canonical)):
        if any(source.get(key) != value for key, value in face.items() if key != "colors"):
            raise ValueError(f"Existing face fact conflicts with canonical printing: {face['name']}")
        colors, kind, derivation = _face_colors(raw, index, admission)
        if "colors" in face and face["colors"] != colors:
            raise ValueError(f"Existing face colors conflict: {face['name']}")
        face["colors"] = colors
        facts.append({**provenance, "scryfall_id": raw["id"], "oracle_id": raw["oracle_id"],
                      "raw_sha256": _raw_hash(raw), "face_index": index, "face_name": source["name"],
                      "fact_path": f"card_faces[{index}].colors", "colors": colors, "fact_kind": kind,
                      "face_mana_cost": source.get("mana_cost"),
                      "face_oracle_sha256": hashlib.sha256(source.get("oracle_text", "").encode()).hexdigest(),
                      "basis": "Scryfall.card_faces.colors" if kind == "canonical_explicit" else "CR face cost + reviewed no-CDA admission",
                      "raw_colors_present": "colors" in source, "derivation": derivation,
                      "runtime_effect_certificate": False})
    loyalty = raw.get("loyalty")
    if loyalty is not None:
        if not isinstance(loyalty, str) or not loyalty:
            raise ValueError("Invalid canonical printed loyalty")
        if "loyalty" in staged and staged["loyalty"] != loyalty:
            raise ValueError(f"Existing root loyalty conflicts: {card['name']}")
        if "loyalty" not in staged:
            staged["loyalty"] = loyalty
            facts.append({**provenance, "scryfall_id": raw["id"], "oracle_id": raw["oracle_id"],
                          "raw_sha256": _raw_hash(raw), "fact_path": "loyalty", "value": loyalty,
                          "fact_kind": "canonical_explicit", "runtime_effect_certificate": False})
    elif "loyalty" in staged:
        raise ValueError(f"Existing loyalty is absent from canonical printing: {card['name']}")
    card.clear()
    card.update(staged)
    ledger.extend(facts)


def _preserve_seed(payload: dict, original: dict) -> None:
    comparable = deepcopy(payload)
    if set(comparable.get("cards", {})) != set(original.get("cards", {})):
        raise ValueError("Seed inventory changed")
    for name, card in comparable["cards"].items():
        before = original["cards"][name]
        for index, face in enumerate(card.get("card_faces", [])):
            if index < len(before.get("card_faces", [])) and "colors" not in before["card_faces"][index]:
                face.pop("colors", None)
        if "loyalty" not in before:
            card.pop("loyalty", None)
    if comparable != original:
        raise ValueError("Existing seed facts changed outside authorized missing colors/loyalty")


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
        card["colors"] = colors
        if card["type_line"] and (card["oracle_text"] or "Land" in card["type_line"]):
            return card
    raise ValueError(f"No verified canonical cached or bulk card for {requested}")


def _preserved_card(projected: dict, before: dict, raw: dict | None, admission: list) -> dict:
    if raw is not None:
        if "object" in before:
            if before != {**raw, "scryfall_id": raw["id"]}:
                raise ValueError(f"Existing full canonical facts conflict: {before['name']}")
        else:
            front = (raw.get("card_faces") or [{}])[0]
            for key, value in before.items():
                if key == "scryfall_id":
                    actual = raw["id"]
                elif key == "card_faces":
                    canonical_faces = raw.get("card_faces") or []
                    if len(value) != len(canonical_faces):
                        raise ValueError(f"Canonical face ordering mismatch: {before['name']}")
                    for index, face in enumerate(value):
                        for field, fact in face.items():
                            actual = (_face_colors(raw, index, admission)[0] if field == "colors"
                                      else canonical_faces[index].get(field))
                            if actual != fact:
                                raise ValueError(f"Existing canonical face fact conflicts: {face['name']}")
                    continue
                elif key == "layout" and value == "" and raw.get("layout") == "normal" and not raw.get("card_faces"):
                    continue  # Legacy cache absence stays unknown, not a canonical update.
                elif key in {"oracle_text", "mana_cost", "type_line", "power", "toughness", "colors"}:
                    actual = front.get(key, raw.get(key))
                else:
                    actual = raw.get(key)
                if actual != value:
                    raise ValueError(f"Existing canonical fact conflicts: {before['name']}.{key}")
    known = {"scryfall_id", "name", "oracle_text", "mana_cost", "type_line", "layout",
             "power", "toughness", "loyalty", "colors", "card_faces"}
    if raw is None and set(before) - known:
        raise ValueError(f"Missing exact canonical facts for preserved fields: {before['name']}")
    result = deepcopy(before)
    for key, value in before.items():
        if key not in known:
            continue  # Full/unknown raw fields were verified above, never projected away.
        if key == "card_faces":
            faces = projected.get(key) or []
            if len(faces) != len(value):
                raise ValueError(f"Missing or conflicting projected faces: {before['name']}")
            for index, face in enumerate(value):
                if any(faces[index].get(field) != fact for field, fact in face.items()):
                    raise ValueError(f"Missing or conflicting projected face facts: {before['name']}")
                if "colors" not in face and "colors" in faces[index]:
                    result[key][index]["colors"] = deepcopy(faces[index]["colors"])
        elif projected.get(key) != value:
            raise ValueError(f"Missing or conflicting projected fact: {before['name']}.{key}")
    if "loyalty" not in before and "loyalty" in projected:
        result["loyalty"] = projected["loyalty"]
    return result


def _retained_ledger(prior: list, generated: list, cards: dict, conn: sqlite3.Connection,
                     bulk: dict | None, admission: list) -> list:
    by_id = {card["scryfall_id"]: card for card in cards.values()}
    retained = {}
    for entry in prior:
        if not isinstance(entry, dict):
            raise ValueError("Invalid preserved fact ledger")
        key = (entry.get("scryfall_id"), entry.get("fact_path"))
        if key in retained or key[0] not in by_id:
            raise ValueError("Duplicate or unknown preserved fact")
        card = by_id[key[0]]
        raw = _exact_card(conn, card, bulk)
        if (entry.get("oracle_id") != raw["oracle_id"] or entry.get("raw_sha256") != _raw_hash(raw)
                or entry.get("runtime_effect_certificate") is not False
                or entry.get("fact_schema_version") != 1):
            raise ValueError("Preserved fact canonical provenance conflicts")
        match = re.fullmatch(r"card_faces\[([0-9]+)\]\.colors", key[1] or "")
        if match:
            index = int(match[1])
            if index >= len(raw.get("card_faces") or []):
                raise ValueError("Invalid preserved face index")
            colors, kind, derivation = _face_colors(raw, index, admission)
            face = raw["card_faces"][index]
            if (entry.get("face_index") != index or entry.get("face_name") != face["name"]
                    or entry.get("colors") != colors or card["card_faces"][index].get("colors") != colors
                    or entry.get("fact_kind") != kind or entry.get("derivation") != derivation
                    or entry.get("face_mana_cost") != face.get("mana_cost")
                    or entry.get("face_oracle_sha256") != hashlib.sha256(face.get("oracle_text", "").encode()).hexdigest()
                    or entry.get("raw_colors_present") != ("colors" in face)
                    or entry.get("cr_sha256") != CR_SHA256):
                raise ValueError("Preserved face fact conflicts")
        elif key[1] == "loyalty":
            if (entry.get("value") != raw.get("loyalty") or card.get("loyalty") != raw.get("loyalty")
                    or entry.get("fact_kind") != "canonical_explicit"):
                raise ValueError("Preserved loyalty fact conflicts")
        else:
            raise ValueError("Unsupported preserved fact path")
        retained[key] = deepcopy(entry)
    for entry in generated:
        key = (entry["scryfall_id"], entry["fact_path"])
        if key not in retained:
            retained[key] = entry
    return list(retained.values())


def export_seed(database: Path, *, canonical_bulk: Path | None = None, bulk_sha256: str | None = None,
                semantic_admission: Path | None = None, admission_sha256: str | None = None,
                preservation_seed: Path = DEFAULT_SEED, fact_ledger: list | None = None,
                preservation_ledger: Path | None = None, preservation_ledger_sha256: str | None = None) -> dict:
    original = json.loads(preservation_seed.read_text(encoding="utf-8"))
    if set(original.get("cards", {})) != shipped_names():
        raise ValueError("Seed inventory changed")
    prior = []
    if preservation_ledger is not None:
        _verified_file(preservation_ledger, preservation_ledger_sha256)
        prior = json.loads(preservation_ledger.read_text(encoding="utf-8"))
        if not isinstance(prior, list):
            raise ValueError("Invalid preserved fact ledger")
    admission = []
    if semantic_admission is not None:
        _verified_file(semantic_admission, admission_sha256)
        admission = json.loads(semantic_admission.read_text(encoding="utf-8"))
        if not isinstance(admission, list) or any(not isinstance(entry, dict) for entry in admission):
            raise ValueError("Invalid semantic admission ledger")
    staged_ledger = []
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
            for key in ("power", "toughness", "loyalty"):
                value = front.get(key) if key in front else row[key] if key in row.keys() else None
                if value is not None:
                    card[key] = value
            if requested in VERIFIED_LOYALTY and "loyalty" not in card:
                card["loyalty"] = VERIFIED_LOYALTY[requested]
            if faces:
                card["card_faces"] = faces
            colors = front.get("colors") or [part for part in (row["colors"] or "").split(",") if part]
            card["colors"] = colors
            cards[requested] = card
        bulk = _bulk_cards(canonical_bulk, bulk_sha256, {card["scryfall_id"] for card in cards.values()}) if canonical_bulk else None
        provenance = {"canonical_source": "verified-local-scryfall-bulk" if bulk is not None else "scryfall-cardknowledge",
                      "fact_schema_version": 1,
                      "preservation_seed_sha256": hashlib.sha256(preservation_seed.read_bytes()).hexdigest(),
                      "bulk_sha256": bulk_sha256 if bulk is not None else None,
                      "semantic_admission_sha256": admission_sha256 if semantic_admission else None,
                      "cr_version": CR_VERSION, "cr_sha256": CR_SHA256}
        preserved = {}
        for requested, before in original["cards"].items():
            card = cards[requested]
            needs_raw = (card.get("card_faces") or "Planeswalker" in card["type_line"]
                         or "loyalty" in card or "object" in before)
            raw = _exact_card(conn, card, bulk, required=bool(needs_raw))
            if card.get("card_faces") or "Planeswalker" in card["type_line"] or "loyalty" in card:
                _enrich_card(card, raw, admission, staged_ledger, provenance)
            preserved[requested] = _preserved_card(card, before, raw, admission)
        staged_ledger = _retained_ledger(prior, staged_ledger, preserved, conn, bulk, admission)
    payload = {**deepcopy(original), "cards": preserved}
    _preserve_seed(payload, original)
    if fact_ledger is not None:
        fact_ledger.extend(staged_ledger)
    return payload


def _write_outputs(outputs: list[tuple[Path, str]]) -> None:
    if len({path.resolve() for path, _ in outputs}) != len(outputs):
        raise ValueError("Output and ledger must be distinct paths")
    staged = []
    try:
        # All validation/serialization and staging finish before any publication.
        for path, content in outputs:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
                staged.append((path, Path(stream.name)))
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        for path, temporary in staged:
            os.replace(temporary, path)
    finally:
        for _, temporary in staged:
            temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export verified built-in Oracle metadata from a synced local cache")
    parser.add_argument("--database", type=Path, default=Path(__file__).resolve().parents[1] / "mtg_lab.db")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "card_data" / "builtin_oracle_seed.json")
    parser.add_argument("--canonical-bulk", type=Path, help="Local full Scryfall JSONL or JSONL.gz; never downloaded")
    parser.add_argument("--bulk-sha256")
    parser.add_argument("--semantic-admission", type=Path, help="Pinned reviewed full-face color-semantic ledger")
    parser.add_argument("--admission-sha256")
    parser.add_argument("--preservation-seed", type=Path, default=DEFAULT_SEED)
    parser.add_argument("--preservation-ledger", type=Path, help="Prior admitted facts, retained only after exact canonical validation")
    parser.add_argument("--preservation-ledger-sha256")
    parser.add_argument("--fact-ledger", type=Path, required=True)
    args = parser.parse_args()
    protected = {path.resolve() for path in (args.database, args.canonical_bulk, args.semantic_admission) if path is not None}
    if args.output.resolve() in protected or args.fact_ledger.resolve() in protected:
        raise ValueError("Export destinations must not overwrite canonical inputs or database")
    ledger = []
    payload = export_seed(args.database, canonical_bulk=args.canonical_bulk, bulk_sha256=args.bulk_sha256,
                          semantic_admission=args.semantic_admission, admission_sha256=args.admission_sha256,
                          preservation_seed=args.preservation_seed, fact_ledger=ledger,
                          preservation_ledger=args.preservation_ledger,
                          preservation_ledger_sha256=args.preservation_ledger_sha256)
    _write_outputs([(args.output, json.dumps(payload, ensure_ascii=False, indent=2) + "\n"),
                    (args.fact_ledger, json.dumps(ledger, ensure_ascii=False, indent=2) + "\n")])
    print(f"Exported {len(payload['cards'])} verified cards to {args.output}")


if __name__ == "__main__":
    main()
