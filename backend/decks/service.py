from __future__ import annotations

from ai.deck_analysis import guess_archetype
from decks.builtin_decks import BUILTIN_DECKS
from decks.expansion_top_decks import EXPANSION_TOP_DECKS, EXPANSION_TOP_DECKS_BY_CODE
from decks.parser import DeckParser
from persistence.repository import Repository


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
        return self.import_deck_text(
            name=item["deck_name"],
            deck_text=item["deck_text"],
            source=f"expansion_top:{item['code']}",
        )

    def import_all_expansion_top_decks(self) -> list[dict]:
        results: list[dict] = []
        for item in EXPANSION_TOP_DECKS:
            results.append(self.import_expansion_top_deck(item["code"]))
        return results

    def import_deck_text(self, name: str, deck_text: str, source: str = "user") -> dict:
        parsed = self.parser.parse(deck_text)
        archetype = guess_archetype(parsed.mainboard)
        if not parsed.errors:
            record = self.repo.save_deck(name=name, source=source, mainboard=parsed.mainboard, sideboard=parsed.sideboard, archetype_guess=archetype)
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
            "mana_curve": self._compute_curve(parsed.mainboard),
            "color_profile": self._color_profile(parsed.mainboard),
        }

    def _compute_curve(self, mainboard: list[dict]) -> dict[str, int]:
        # Placeholder curve that remains stable without full mana cost DB hydration.
        buckets = {"1": 0, "2": 0, "3": 0, "4": 0, "5+": 0}
        for item in mainboard:
            name = item["card_name"].lower()
            qty = item["quantity"]
            if any(k in name for k in ["bolt", "spike", "shock", "push"]):
                buckets["1"] += qty
            elif any(k in name for k in ["counterspell", "growth", "mage", "guide"]):
                buckets["2"] += qty
            elif any(k in name for k in ["fable", "adeline", "deluge"]):
                buckets["3"] += qty
            elif any(k in name for k in ["sheoldred", "teferi", "festival"]):
                buckets["4"] += qty
            else:
                buckets["5+"] += qty
        return buckets

    def _color_profile(self, mainboard: list[dict]) -> dict[str, int]:
        color_map = {"W": 0, "U": 0, "B": 0, "R": 0, "G": 0}
        for item in mainboard:
            n = item["card_name"].lower()
            qty = item["quantity"]
            if "plains" in n or "white" in n:
                color_map["W"] += qty
            if "island" in n or "blue" in n:
                color_map["U"] += qty
            if "swamp" in n or "black" in n:
                color_map["B"] += qty
            if "mountain" in n or "red" in n or "bolt" in n:
                color_map["R"] += qty
            if "forest" in n or "green" in n or "elves" in n:
                color_map["G"] += qty
        return color_map
