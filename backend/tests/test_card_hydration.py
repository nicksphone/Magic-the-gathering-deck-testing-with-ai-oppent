from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from card_data.hydration import hydrate_deck_cards
from card_data.sync import ScryfallSyncService
from game_state.serializers import deserialize_match_snapshot, serialize_card_view, serialize_match_snapshot
from game_state.state import MatchFactory
from rules_engine.colors import card_color_names


def _canonical_raw(name: str) -> dict:
    fixtures = Path(__file__).parent / "fixtures"
    if name == "Skewer the Critics":
        return next(json.loads(line) for line in
                    (fixtures / "knowledge_profiles/seed155-scryfall.jsonl").read_text().splitlines()
                    if json.loads(line)["name"] == name)
    filename = {
        "Figure of Destiny": "figure-of-destiny",
        "Valki, God of Lies // Tibalt, Cosmic Impostor": "valki",
        "Ruination Guide": "ruination-guide",
    }[name] + "-scryfall-raw.json"
    return json.loads((fixtures / "canonical_hydration" / filename).read_bytes())


def _cached_canonical(name: str) -> SimpleNamespace:
    # Display-only override; no image download or placeholder write in the mapper.
    return SimpleNamespace(**ScryfallSyncService._normalize_payload(
        _canonical_raw(name), "/card-images/canonical-hydration-fixture.svg"))


class _Repo:
    def __init__(self, rows: list[object]) -> None:
        self.rows = {str(row.name).lower(): row for row in rows}

    def get_cached_cards_by_names(self, names: list[str]) -> dict[str, object]:
        return {name.lower(): self.rows[name.lower()] for name in names if name.lower() in self.rows}


def test_hydration_preserves_cached_noncreature_type_before_match_factory() -> None:
    row = _cached_canonical("Skewer the Critics")
    deck = [{"quantity": 1, "card_name": "Skewer the Critics"}]

    hydrated = hydrate_deck_cards(_Repo([row]), deck)
    state = MatchFactory.from_decks(hydrated + [{"quantity": 59, "card_name": "Mountain", "type_line": "Basic Land — Mountain"}], hydrated)
    skewer = next(card for card in state.cards.values() if card.name == "Skewer the Critics")

    assert hydrated[0]["type_line"] == "Sorcery"
    assert skewer.types == ["Sorcery"]
    assert skewer.power is None
    assert skewer.toughness is None


def test_match_factory_does_not_invent_stats_for_unknown_cards() -> None:
    deck = [{"quantity": 1, "card_name": "Unknown Card", "type_line": "Enchantment"}]

    state = MatchFactory.from_decks(deck, deck)
    unknown = next(card for card in state.cards.values() if card.name == "Unknown Card")

    assert unknown.types == ["Enchantment"]
    assert unknown.power is None
    assert unknown.toughness is None


def test_cached_hybrid_colors_survive_live_hydration_and_snapshot() -> None:
    row = _cached_canonical("Figure of Destiny")
    hydrated = hydrate_deck_cards(_Repo([row]), [{"quantity": 1, "card_name": "Figure of Destiny"}])
    state = MatchFactory.from_decks(hydrated, hydrated, seed=7)
    figure = next(card for card in state.cards.values() if card.name == "Figure of Destiny")

    assert hydrated[0]["colors"] == ["R", "W"]
    assert card_color_names(figure) == {"red", "white"}
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert serialize_card_view(state, figure.id)["colors"] == ["R", "W"]


def test_missing_color_metadata_uses_hybrid_cost_but_devoid_is_colorless() -> None:
    figure_raw = _canonical_raw("Figure of Destiny")
    guide_raw = _canonical_raw("Ruination Guide")
    # Deliberate missing-metadata protocol: Figure also omits Oracle; Guide is
    # a newly chosen canonical example, not an identification of the old stub.
    figure = SimpleNamespace(mana_cost=figure_raw["mana_cost"], oracle_text="", colors=None, card_faces=[])
    guide = SimpleNamespace(mana_cost=guide_raw["mana_cost"], oracle_text=guide_raw["oracle_text"], colors=None, card_faces=[])

    assert card_color_names(figure) == {"red", "white"}
    assert card_color_names(guide) == set()


def test_selected_modal_face_uses_its_own_canonical_colors() -> None:
    card = SimpleNamespace(**_canonical_raw("Valki, God of Lies // Tibalt, Cosmic Impostor"))
    card.selected_face_index = 0

    assert card_color_names(card) == {"black"}
    card.selected_face_index = 1
    assert card_color_names(card) == {"black", "red"}
