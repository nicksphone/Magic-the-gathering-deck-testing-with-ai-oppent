from __future__ import annotations

import json

from decks.service import DeckService


class _FakeCard:
    def __init__(self, name: str, image_uri: str | None = None):
        self.id = f"card:{name.lower()}"
        self.scryfall_id = f"scry:{name.lower()}"
        self.name = name
        self.oracle_text = "Copy target spell."
        self.mana_cost = "{1}{U}"
        self.type_line = "Instant"
        self.colors = "U"
        self.power = None
        self.toughness = None
        self.image_uri = image_uri
        self.legalities_json = json.dumps({"modern": "legal"})
        self.card_faces_json = json.dumps(
            [
                {"name": name, "mana_cost": "{1}{U}", "type_line": "Instant", "oracle_text": "Copy target spell.", "image_uri": image_uri},
            ]
        )


class _FakeRecord:
    def __init__(self) -> None:
        self.id = 7


class _FakeRepo:
    def __init__(self) -> None:
        self._cards = {
            "fire // ice": _FakeCard("Fire // Ice", "/card-images/fire-ice.png"),
            "island": _FakeCard("Island", "/card-images/island.png"),
        }

    def list_cards(self):
        return list(self._cards.values())

    def get_cached_cards_by_names(self, names: list[str]):
        out = {}
        for name in names:
            hit = self._cards.get(name.lower())
            if hit:
                out[name.lower()] = hit
        return out

    def save_deck(self, **kwargs):
        return _FakeRecord()


def test_import_deck_text_exposes_resolved_card_metadata() -> None:
    service = DeckService(_FakeRepo())
    out = service.import_deck_text("Modal Test", "4 Fire // Ice\n56 Island", source="user")
    assert out["deck_id"] == 7
    assert out["resolved_mainboard_cards"][0]["card_metadata"]["card_faces"][0]["name"] == "Fire // Ice"
    assert out["resolved_mainboard_cards"][0]["card_metadata"]["image_uri"] == "/card-images/fire-ice.png"
    assert out["resolved_mainboard_cards"][1]["card_metadata"]["name"] == "Island"
