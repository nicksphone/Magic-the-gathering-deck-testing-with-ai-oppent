from __future__ import annotations

import hashlib
import json

from fastapi import HTTPException

from ai.deck_analysis import analyze_deck
from card_data.display import select_display_image_uri
from card_data.hydration import hydrate_deck_cards, is_playable_deck_card, ready_for_match
from card_data.sync import ScryfallSyncService
from decks.builtin_decks import BUILTIN_DECKS
from decks.expansion_top_decks import EXPANSION_TOP_DECKS, EXPANSION_TOP_DECKS_BY_CODE
from decks.parser import DeckParser
from persistence.repository import Repository
from rules_engine.mana import mana_value


class DeckService:
    def __init__(self, repo: Repository):
        self.repo = repo
        self.parser = DeckParser(repo)

    def list_builtins(self) -> list[str]:
        return sorted(BUILTIN_DECKS.keys())

    def get_builtin_text(self, name: str) -> str:
        return BUILTIN_DECKS[name]

    def list_expansion_top_decks(self) -> list[dict]:
        out: list[dict] = []
        for item in EXPANSION_TOP_DECKS:
            out.append(
                {
                    "code": item["code"],
                    "expansion": item["expansion"],
                    "release_year": item["release_year"],
                    "deck_name": item["deck_name"],
                    "archetype": item["archetype"],
                    "kind": item["kind"],
                    "format": item["format"],
                    "event_name": item["event_name"],
                    "player_name": item["player_name"],
                    "finish": item["finish"],
                    "decklist_source_url": item["decklist_source_url"],
                    "event_source_url": item["event_source_url"],
                }
            )
        return out

    def get_expansion_top_deck(self, code: str) -> dict:
        key = (code or "").strip().upper()
        if key not in EXPANSION_TOP_DECKS_BY_CODE:
            raise KeyError(key)
        return EXPANSION_TOP_DECKS_BY_CODE[key]

    def import_expansion_top_deck(self, code: str) -> dict:
        item = self.get_expansion_top_deck(code)
        canonical_source = f"expansion_top:{item['code'].lower()}"
        # list_decks is newest-first; reuse the exact source without rekeying history.
        source = next((row.source for row in self.repo.list_decks()
                       if (row.source or "").strip().lower() == canonical_source), canonical_source)
        return self.import_deck_text(
            name=item["deck_name"],
            deck_text=item["deck_text"],
            source=source,
            _official_catalog=True,
        )

    def import_all_expansion_top_decks(self) -> list[dict]:
        results: list[dict] = []
        for item in EXPANSION_TOP_DECKS:
            results.append(self.import_expansion_top_deck(item["code"]))
        return results

    def import_deck_text(self, name: str, deck_text: str, source: str = "user", *, _official_catalog: bool = False) -> dict:
        parsed = self.parser.parse(deck_text)
        sideboard_count = sum(card["quantity"] for card in parsed.sideboard)
        # MatchStart supports at most 15 sideboard cards. Reject before cache or deck writes.
        if sideboard_count > 15:
            raise HTTPException(status_code=422, detail={
                "code": "sideboard_limit_exceeded", "maximum": 15, "actual": sideboard_count,
            })
        resolved_mainboard = self._resolve_card_metadata(parsed.mainboard, materialize=not parsed.errors)
        resolved_sideboard = self._resolve_card_metadata(parsed.sideboard, materialize=not parsed.errors)
        # Cache-shaped display metadata stays compatible; classification uses canonical facts.
        canonical_mainboard = hydrate_deck_cards(self.repo, parsed.mainboard)
        analysis = analyze_deck(canonical_mainboard)
        admitted = (bool(canonical_mainboard)
                    and all(card.get("card_data_sources") and ready_for_match(card) for card in canonical_mainboard)
                    and analysis["type_metadata_coverage"] == 1 and analysis["confidence"] > 0
                    and not {"missing_card_metadata", "partial_card_metadata", "fallback_midrange"}
                    .intersection(analysis["signals"]))
        archetype = analysis["primary_archetype"] if admitted else "unknown"
        for item in resolved_mainboard + resolved_sideboard:
            metadata = item.get("card_metadata")
            if metadata is not None and not is_playable_deck_card(metadata):
                parsed.errors.append(f"{item['card_name']} is not a playable deck card.")
        if not parsed.errors:
            save = self.repo.save_catalog_deck if _official_catalog or source.lower().startswith("expansion_top:") else self.repo.save_deck
            record = save(name=name, source=source, mainboard=parsed.mainboard, sideboard=parsed.sideboard, archetype_guess=archetype)
            deck_id = record.id
        else:
            deck_id = None
        return {
            "deck_id": deck_id,
            "name": name,
            "archetype_guess": archetype,
            "errors": parsed.errors,
            "suggestions": parsed.suggestions,
            "mainboard": parsed.mainboard,
            "sideboard": parsed.sideboard,
            "resolved_mainboard_cards": resolved_mainboard,
            "resolved_sideboard_cards": resolved_sideboard,
            "mana_curve": self._compute_curve(resolved_mainboard),
            "color_profile": self._color_profile(resolved_mainboard),
            "analysis": analysis,
            "classification_status": "resolved" if admitted else "unknown",
            "classification_provenance": {
                "method": "ai.deck_analysis.analyze_deck",
                "facts_method": "card_data.hydration.hydrate_deck_cards",
                "admission": "complete-local-canonical-v1",
                "sources": sorted({source for card in canonical_mainboard for source in card.get("card_data_sources", [])}),
                "resolved_board_sha256": hashlib.sha256(json.dumps(canonical_mainboard, sort_keys=True,
                    separators=(",", ":"), allow_nan=False).encode()).hexdigest(),
                "cards": [{"card_name": card["card_name"], "sources": card["card_data_sources"],
                           "ready_for_match": bool(ready_for_match(card))} for card in canonical_mainboard],
            },
        }

    def _compute_curve(self, mainboard: list[dict]) -> dict[str, int]:
        buckets = {"0": 0, "1": 0, "2": 0, "3": 0, "4": 0, "5+": 0, "lands": 0, "unknown": 0}
        for item in mainboard:
            qty = item["quantity"]
            meta = item.get("card_metadata") or {}
            if not meta:
                buckets["unknown"] += qty
                continue
            faces = meta.get("card_faces") or []
            front = faces[0] if faces and isinstance(faces[0], dict) else {}
            type_line = str(meta.get("type_line") or front.get("type_line") or "")
            if "Land" in type_line.split(" // ")[0].split(" - ")[0].split():
                buckets["lands"] += qty
                continue
            cost = str(meta.get("mana_cost") or "")
            if meta.get("layout") in {"modal_dfc", "transform", "reversible_card", "adventure"}:
                cost = str(front.get("mana_cost") or cost)
            elif not cost and faces:
                cost = " ".join(str(face.get("mana_cost") or "") for face in faces if isinstance(face, dict))
            if not cost and not type_line:
                buckets["unknown"] += qty
                continue
            value = mana_value(cost)
            buckets[str(value) if value < 5 else "5+"] += qty
        return buckets

    def _color_profile(self, mainboard: list[dict]) -> dict[str, int]:
        color_map = {"W": 0, "U": 0, "B": 0, "R": 0, "G": 0}
        for item in mainboard:
            meta = item.get("card_metadata") or {}
            # Profile printed spell colors, not inferred land production or color identity.
            faces = meta.get("card_faces") or []
            front = faces[0] if faces and isinstance(faces[0], dict) else {}
            type_line = str(meta.get("type_line") or front.get("type_line") or "")
            if "Land" in type_line.split(" // ")[0].split(" - ")[0].split():
                continue
            for color in set(meta.get("colors") or []):
                if color in color_map:
                    color_map[color] += item["quantity"]
        return color_map

    def _resolve_card_metadata(self, items: list[dict], *, materialize: bool = True) -> list[dict]:
        from card_data.hydration import cached_json

        # Keep the keyword compatible; metadata projection never materializes cache rows.
        names = [item["card_name"] for item in items]
        cache = self.repo.get_cached_cards_by_names(names)
        missing = [item for item in items if item["card_name"].lower() not in cache]
        local = {card["card_name"].lower(): card for card in hydrate_deck_cards(self.repo, missing)} if missing else {}
        resolved: list[dict] = []
        for item in items:
            card = cache.get(item["card_name"].lower())
            metadata = None
            if card is not None:
                metadata = self._serialize_cached_card(card)
                metadata["loyalty"] = getattr(card, "loyalty", None)
                metadata["card_data_sources"] = ["cache"]
                metadata["match_ready"] = ready_for_match(metadata)
            else:
                hydrated = local.get(item["card_name"].lower(), {})
                if hydrated.get("card_data_sources") and ready_for_match(hydrated):
                    metadata = {key: hydrated[key] for key in (
                        "scryfall_id", "name", "oracle_text", "mana_cost", "type_line", "layout",
                        "colors", "power", "toughness", "loyalty", "image_uri", "card_faces",
                        "card_data_sources",
                    ) if key in hydrated}
                    metadata.setdefault("name", item["card_name"])
                    metadata["legalities"] = cached_json(hydrated.get("legalities_json"), dict)
                    metadata["rulings"] = cached_json(hydrated.get("rulings_json"), list)
                    metadata["match_ready"] = True
            resolved.append(
                {
                    "quantity": item["quantity"],
                    "card_name": item["card_name"],
                    "card_metadata": metadata,
                }
            )
        return resolved

    def _serialize_cached_card(self, card) -> dict:
        return {
            "id": card.id,
            "scryfall_id": card.scryfall_id,
            "name": card.name,
            "oracle_text": card.oracle_text,
            "mana_cost": card.mana_cost,
            "type_line": card.type_line,
            "layout": getattr(card, "layout", ""),
            "colors": card.colors.split(",") if card.colors else [],
            "power": card.power,
            "toughness": card.toughness,
            "image_uri": select_display_image_uri(card, name=card.name, type_line=card.type_line or ""),
            "legalities": json.loads(card.legalities_json),
            "card_faces": json.loads(getattr(card, "card_faces_json", "[]") or "[]"),
            "rulings": json.loads(getattr(card, "rulings_json", "[]") or "[]"),
        }
