"""Adversarial label changes are tests, not new gameplay card definitions."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai.agent import AIAgent, _card_for_move, _has_counter_spell_text, _oracle_text
from ai.deck_analysis import analyze_deck
from ai.heuristics import _noncreature_value
from card_data.hydration import hydrate_deck_cards
from decks.builtin_decks import BUILTIN_DECKS
from game_state.state import MatchFactory


FIXTURES = {row["name"]: row for row in json.loads(
    (Path(__file__).parent / "fixtures" / "ai_oracle_semantics.json").read_text())}


def card(name):
    raw = FIXTURES[name]
    return SimpleNamespace(**deepcopy(raw), types=raw["type_line"].split(" — ")[0].split())


@pytest.mark.parametrize("name", list(BUILTIN_DECKS))
def test_all_builtin_deck_analysis_uses_metadata_not_display_labels(name):
    entries = [{"quantity": int(q), "card_name": c} for q, c in
               (line.split(" ", 1) for line in BUILTIN_DECKS[name].strip().splitlines())]
    original = hydrate_deck_cards(None, entries)
    changed = deepcopy(original)
    for index, entry in enumerate(changed):
        entry["card_name"] = f"Display label {index}"
        entry["name"] = entry["card_name"]
        if entry.get("card_metadata"):
            entry["card_metadata"]["name"] = entry["card_name"]
    assert analyze_deck(changed) == analyze_deck(original)


@pytest.mark.parametrize("name,damage", [("Lightning Bolt", 3), ("Lightning Strike", 3),
                                        ("Boros Charm", 4), ("Spike Weaver", 0), ("Bolt Bend", 0)])
def test_fixed_player_damage_is_printed_not_guessed_from_names(name, damage):
    ai = AIAgent(archetype="Burn")
    source = card(name)
    assert ai._burn_damage_estimate(_oracle_text(source)) == damage
    source.name = "Counterspell"
    assert ai._burn_damage_estimate(_oracle_text(source)) == damage
    source.oracle_text = ""
    assert ai._burn_damage_estimate(_oracle_text(source)) == 0


def test_unknown_deck_metadata_is_explicit_not_a_name_guessed_archetype():
    result = analyze_deck([{"quantity": 60, "card_name": "Lightning Bolt"}])
    assert result["primary_archetype"] == "Midrange"
    assert result["confidence"] == result["type_metadata_coverage"] == 0
    assert "missing_card_metadata" in result["signals"]


def test_counter_recognition_and_color_demand_include_nonblue_counters():
    source = card("Withering Boon")
    ai = AIAgent(archetype="Control")
    assert ai._is_counter_card(source)
    state = SimpleNamespace(cards={"boon": source}, players={1: SimpleNamespace(hand=["boon"])})
    demand = ai._color_demand(state, 1)
    assert demand["B"] > 0 and demand["U"] == 0
    source.name = "Lightning Bolt"
    assert ai._is_counter_card(source)
    source.oracle_text = ""
    assert not ai._is_counter_card(source)
    assert not _has_counter_spell_text("Counterspell")


def test_board_and_closure_values_ignore_display_names_but_keep_real_draw_text():
    ai = AIAgent(archetype="Control")
    source = card("Shark Typhoon")
    before = _noncreature_value(source), ai._closure_spell_score(source, _oracle_text(source))
    source.name = "Memory Deluge"
    assert (_noncreature_value(source), ai._closure_spell_score(source, _oracle_text(source))) == before
    assert ai._closure_spell_score(card("Memory Deluge"), _oracle_text(card("Memory Deluge"))) > 0


def test_rank_and_rollout_burn_roles_do_not_come_from_move_labels():
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=111)
    state.cards["bend"] = card("Bolt Bend")
    state.cards["strike"] = card("Lightning Strike")
    moves = [{"type": "cast_spell", "card_id": "bend", "card_name": "Bolt Bend"},
             {"type": "cast_spell", "card_id": "strike", "card_name": "Lightning Strike"}]
    ai = AIAgent(archetype="Burn", difficulty="casual")
    assert ai._rank_moves(state, moves, 1, shallow=True)[0]["card_id"] == "strike"
    assert ai._pick_rollout_move(state, moves, 1)["card_id"] == "strike"
    moves[0]["card_name"] = "Lightning Bolt"
    moves[1]["card_name"] = "Counterspell"
    assert ai._rank_moves(state, moves, 1, shallow=True)[0]["card_id"] == "strike"


def test_cast_surface_uses_announced_face_not_aggregate_or_front_only_roles():
    source = card("Jwari Disruption // Jwari Ruins")
    state = SimpleNamespace(cards={"face-test": source})
    assert "counter" in AIAgent()._spell_tags(_card_for_move(state, {"type": "cast_spell", "card_id": "face-test", "selected_face_index": 0}))
    back = _card_for_move(state, {"type": "cast_spell", "card_id": "face-test", "selected_face_index": 1})
    assert "counter" not in AIAgent()._spell_tags(back)
    assert "Land" in back.types
    assert _card_for_move(state, {"type": "activate_ability", "card_id": "face-test"}) is source


def test_flat_and_nested_canonical_face_metadata_have_identical_analysis():
    raw = deepcopy(FIXTURES["Jwari Disruption // Jwari Ruins"])
    flat = {"quantity": 4, "card_name": raw["name"], **raw}
    nested = {"quantity": 4, "card_name": raw["name"], "card_metadata": raw}
    assert analyze_deck([flat]) == analyze_deck([nested])
    assert "mana_acceleration_package" not in analyze_deck([{**flat, "quantity": 60}])["signals"]
