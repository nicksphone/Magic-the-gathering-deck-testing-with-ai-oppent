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


def test_import_curve_and_colors_use_cached_oracle_metadata() -> None:
    repo = _FakeRepo()

    def card(name: str, cost: str, type_line: str, colors: str, layout: str = "normal", faces: list[dict] | None = None):
        row = _FakeCard(name)
        row.mana_cost = cost
        row.type_line = type_line
        row.colors = colors
        row.layout = layout
        row.card_faces_json = json.dumps(faces or [])
        repo._cards[name.lower()] = row

    card("Fire // Ice", "{1}{R} // {1}{U}", "Instant // Instant", "R,U", "split")
    card("Secure the Wastes", "{X}{W}", "Instant", "W")
    card("Memnite", "{0}", "Artifact Creature - Construct", "")
    card("Kazandu Mammoth // Kazandu Valley", "", "Creature - Elephant // Land", "G", "modal_dfc", [
        {"name": "Kazandu Mammoth", "mana_cost": "{1}{G}{G}", "type_line": "Creature - Elephant"},
        {"name": "Kazandu Valley", "mana_cost": "", "type_line": "Land"},
    ])
    card("Mountain", "", "Basic Land - Mountain", "")
    card("Island", "", "Basic Land - Island", "")
    card("Dryad Arbor", "", "Land Creature - Forest Dryad", "G")
    out = DeckService(repo).import_deck_text(
        "Metadata curve",
        "4 Fire // Ice\n4 Secure the Wastes\n4 Memnite\n4 Kazandu Mammoth // Kazandu Valley\n20 Mountain\n20 Island\n4 Dryad Arbor",
    )
    assert out["errors"] == []
    assert out["mana_curve"] == {"0": 4, "1": 4, "2": 0, "3": 4, "4": 4, "5+": 0, "lands": 44, "unknown": 0}
    assert out["color_profile"] == {"W": 4, "U": 4, "B": 0, "R": 4, "G": 4}


def test_import_curve_does_not_invent_cost_for_missing_metadata() -> None:
    repo = _FakeRepo()
    repo._cards["island"].type_line = "Basic Land - Island"
    repo._cards["island"].mana_cost = ""
    out = DeckService(repo).import_deck_text("Uncached", "4 Missing Oracle Card\n56 Island")
    assert out["mana_curve"]["unknown"] == 4
    assert out["mana_curve"]["lands"] == 56
