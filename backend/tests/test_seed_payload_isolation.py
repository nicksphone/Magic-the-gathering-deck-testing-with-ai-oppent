"""Caller-mutation isolation of real seed facts; no fabricated card-rule fixtures."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from card_data import seed_cards
from card_data.hydration import hydrate_deck_cards
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory


SEED = Path(__file__).resolve().parents[1] / "card_data/builtin_oracle_seed.json"
PRINTED = json.loads(SEED.read_text())["cards"]


@pytest.fixture(autouse=True)
def restore_catalog_after_faulty_baseline():
    # Baseline intentionally proves a shared-object mutation. Restore those same
    # dicts in place so normalized aliases and unrelated tests retain their facts.
    before = deepcopy(seed_cards.SEED_CARD_DATA)
    yield
    for name, original in before.items():
        payload = seed_cards.SEED_CARD_DATA[name]
        payload.clear()
        payload.update(original)


@pytest.mark.parametrize("requested,canonical", [
    ("Lightning Bolt", "Lightning Bolt"),
    ("  BRUTAL CATHAR  ", "Brutal Cathar"),
    ("Fable of the Mirror Breaker", "Fable of the Mirror-Breaker"),
    ("Delver of Secrets // Insectile Aberration", "Delver of Secrets"),
    # Historical lookup convenience only; this is not an admitted card/face.
    ("Delver of Secrets // Bogus Face", "Delver of Secrets"),
])
def test_clearing_returned_seed_does_not_change_later_alias_lookup(requested, canonical):
    first = seed_cards.seed_card_payload(requested)
    assert first == PRINTED[canonical]
    first.clear()  # Explicit caller edit; not a claim about altered card rules.
    assert seed_cards.seed_card_payload(canonical) == PRINTED[canonical]
    assert seed_cards.seed_card_payload(requested) == PRINTED[canonical]


@pytest.mark.parametrize("requested,canonical", [
    ("Brutal Cathar", "Brutal Cathar"),
    ("Delver of Secrets", "Delver of Secrets"),
    ("Imodane's Recruiter", "Imodane's Recruiter"),
    ("Delver of Secrets // Bogus Face", "Delver of Secrets"),
])
def test_nested_faces_and_colors_are_detached_from_other_seed_lookups(requested, canonical):
    first, second = seed_cards.seed_card_payload(requested), seed_cards.seed_card_payload(requested)
    first["card_faces"][1]["oracle_text"] = "CALLER_EDIT"
    first["card_faces"][1]["colors"].append("CALLER_EDIT")
    first["card_faces"].append({"caller": "edit"})
    assert second == PRINTED[canonical]
    assert seed_cards.seed_card_payload(requested) == PRINTED[canonical]
    assert seed_cards.SEED_CARD_DATA[canonical] == PRINTED[canonical]


def test_duplicate_hydrated_rows_and_later_calls_keep_independent_faces():
    deck = [{"card_name": "Brutal Cathar", "quantity": 4},
            {"card_name": "Brutal Cathar", "quantity": 4}]
    before = deepcopy(deck)
    first, second = hydrate_deck_cards(None, deck)
    first["card_faces"][0]["oracle_text"] = "CALLER_EDIT"
    first["card_faces"][0]["colors"].clear()
    assert second["card_faces"] == PRINTED["Brutal Cathar"]["card_faces"]
    assert hydrate_deck_cards(None, deck)[0]["card_faces"] == PRINTED["Brutal Cathar"]["card_faces"]
    assert deck == before


@pytest.mark.parametrize("seat", [1, 2])
def test_prior_hydration_edit_cannot_change_later_native_birth_or_restored_prints(seat):
    deck = [{"card_name": "Brutal Cathar", "quantity": 4},
            {"card_name": "Plains", "quantity": 56}]
    previous = hydrate_deck_cards(None, deck)
    previous[0]["card_faces"][1]["oracle_text"] = "CALLER_EDIT"
    previous[0]["card_faces"][1]["colors"].clear()
    facts = hydrate_deck_cards(None, deck)
    state = MatchFactory.from_decks(facts, facts, seed=2026110801)
    snapshot = serialize_match_snapshot(state)
    restored = deserialize_match_snapshot(snapshot)
    cards = [card for card in restored.cards.values()
             if card.owner == seat and card.name == "Brutal Cathar"]
    assert len(cards) == 4
    assert all(card.card_faces == PRINTED["Brutal Cathar"]["card_faces"] for card in cards)
    assert serialize_match_snapshot(restored) == snapshot


def test_missing_seed_name_still_returns_none():
    assert seed_cards.seed_card_payload("Caller isolation unknown card") is None
