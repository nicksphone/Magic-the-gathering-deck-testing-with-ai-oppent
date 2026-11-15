"""A cached/canonical Battle keeps its printed defense into a new match."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from card_data.hydration import hydrate_deck_cards, ready_for_match
from card_data.sync import ScryfallSyncService
from game_state.state import MatchFactory
from tests.test_builtin_metadata_refresh import repo


PRINTING = Path(__file__).parent / "fixtures/battle_full_printing/invasion-of-zendikar-mom-194.json"


@pytest.mark.parametrize("seat", [1, 2])
@pytest.mark.parametrize("source", ["cache", "knowledge"])
def test_battle_defense_survives_normalization_hydration_and_factory(repo, seat, source):
    raw = json.loads(PRINTING.read_text())
    original = deepcopy(raw)
    if source == "cache":
        repo.upsert_card(ScryfallSyncService._normalize_payload(raw, "unused:test"))
    else:
        repo.upsert_card_knowledge({
            "name": raw["name"], "scryfall_id": raw["id"], "oracle_source": "scryfall",
            "profiles": {"schema_version": 1, "card_data": raw,
                         "rulings_verified": False, "rulings": []},
        })
    facts = hydrate_deck_cards(repo, [
        {"card_name": raw["name"], "quantity": 1},
        {"card_name": "Forest", "quantity": 59},
    ])
    assert ready_for_match(facts[0])
    assert facts[0]["card_faces"][0].get("defense") == raw["card_faces"][0]["defense"] == "3"
    assert "defense" not in facts[0]["card_faces"][1]
    state = MatchFactory.from_decks(facts, facts, seed=71203)
    battle = next(card for card in state.cards.values()
                  if card.owner == seat and "Battle" in card.types)
    assert battle.printed_defense == "3"
    assert battle.card_faces[0]["defense"] == "3"
    assert battle.battle_protector is None  # Chosen on battlefield entry, not imported.
    assert raw == original


def test_normalized_nonbattle_face_keeps_its_existing_shape():
    face = {"name": "Front", "mana_cost": "{1}", "type_line": "Creature",
            "oracle_text": "", "power": "1", "toughness": "1"}
    assert ScryfallSyncService._normalize_faces([face]) == [{
        **face, "loyalty": None, "colors": None, "image_uri": None,
    }]


def test_normalizing_battle_faces_does_not_mutate_the_printing():
    raw = json.loads(PRINTING.read_text())
    original = deepcopy(raw)
    faces = ScryfallSyncService._normalize_faces(raw["card_faces"])
    faces[0]["name"] = "caller-owned normalized face"
    assert raw == original
