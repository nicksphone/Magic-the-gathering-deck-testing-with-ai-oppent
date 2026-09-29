from __future__ import annotations

import pytest

from effects.handlers import copy_spell
from effects.registry import resolve_effect
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, StackItem, Step, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.cast_choice import validate_cast_choice
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import search_card_matches
from rules_engine.stack_engine import resolve_top_of_stack


SEARCH_FOR_GLORY = (
    "Search your library for a snow permanent card, a legendary card, or a Saga card, "
    "reveal it, put it into your hand, then shuffle your library. "
    "You gain 1 life for each {S} spent to cast this spell."
)


def _search_state(snow_colors: dict[str, int]):
    deck = [{"quantity": 60, "card_name": "Swamp"}]
    state = MatchFactory.from_decks(deck, deck, seed=933)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = 1
    state.step = Step.PRECOMBAT_MAIN
    state.mechanic_choice_players = {1}
    state.players[1].mana_pool.update({"C": 2, "W": 1})
    state.players[1].snow_mana_pool.update(snow_colors)
    spell = state.cards[state.players[1].hand[0]]
    spell.name = "Search for Glory"
    spell.types, spell.type_line = ["Sorcery", "Snow"], "Snow Sorcery"
    spell.mana_cost, spell.oracle_text = "{2}{W}", SEARCH_FOR_GLORY
    candidates = state.players[1].library[-4:]
    for cid, name, types, type_line in zip(
        candidates,
        ["Snow-Covered Forest", "The Wandering Emperor", "Fable of the Mirror-Breaker", "Forest"],
        [["Land"], ["Legendary", "Planeswalker"], ["Enchantment"], ["Land"]],
        ["Basic Snow Land - Forest", "Legendary Planeswalker - Emperor", "Enchantment - Saga", "Basic Land - Forest"],
    ):
        card = state.cards[cid]
        card.name, card.types, card.type_line = name, types, type_line
    return state, spell.id, candidates


def test_search_for_glory_uses_snow_spent_on_generic_and_resumes_after_choice() -> None:
    state, spell_id, candidates = _search_state({"C": 2})
    assert all(search_card_matches(state.cards[cid], "snow_or_legendary_or_saga") for cid in candidates[:3])
    assert not search_card_matches(state.cards[candidates[3]], "snow_or_legendary_or_saga")
    cast = checked_action(state, RulesEngine(), 1, {"type": "cast_spell", "card_id": spell_id})
    assert cast.stack[-1].effect_key == "effect_sequence"
    assert cast.stack[-1].payload["snow_mana_spent"] == 2
    assert cast.stack[-1].payload["snow_mana_colors"] == {"C": 2}
    assert not resolve_top_of_stack(cast)
    assert set(cast.pending_mechanic_choice["options"]) == set(candidates[:3])
    restored = deserialize_match_snapshot(serialize_match_snapshot(cast))
    resolved = checked_action(restored, RulesEngine(), 1, {"type": "choose_mechanic", "card_ids": [candidates[1]]})
    assert candidates[1] in resolved.players[1].hand
    assert resolved.players[1].life == 22
    assert resolved.pending_mechanic_choice is None


def test_search_for_glory_counts_colored_snow_and_zero_snow() -> None:
    for snow_colors, expected in (({"W": 1}, 1), ({}, 0)):
        state, spell_id, _ = _search_state(snow_colors)
        cast = checked_action(state, RulesEngine(), 1, {"type": "cast_spell", "card_id": spell_id})
        assert cast.stack[-1].payload["snow_mana_spent"] == expected
        assert not resolve_top_of_stack(cast)
        resumed = checked_action(cast, RulesEngine(), 1, {"type": "choose_mechanic", "card_ids": []})
        assert resumed.players[1].life == 20 + expected


def test_cast_cannot_override_search_filter_count_or_mana_limit() -> None:
    state, spell_id, _ = _search_state({"C": 2})
    before = serialize_match_snapshot(state)
    for targets in ({"search_contains": "card"}, {"search_count": 53}, {"search_mv_max": 99}):
        with pytest.raises(ActionRejected, match="Library-search restrictions"):
            checked_action(state, RulesEngine(), 1, {
                "type": "cast_spell", "card_id": spell_id, "targets": targets,
            })
        assert serialize_match_snapshot(state) == before
    assert validate_cast_choice({}, {
        "mode_targets": {"Search": {"search_contains": "card"}},
    }) == (False, "Library-search restrictions come from the card, not the cast action.")


def test_copied_snow_spend_spell_has_zero_snow_mana_spent() -> None:
    state, spell_id, _ = _search_state({"C": 2})
    spell = state.cards[spell_id]
    state.players[1].hand.remove(spell_id)
    spell.zone = Zone.STACK
    state.stack.append(StackItem(
        id="snow-spell", source_card_id=spell_id, controller=1, label=spell.name,
        effect_key="gain_life", payload={"amount_source": "snow_mana_spent", "snow_mana_spent": 2},
    ))
    copy_spell(state, 1, {"target_stack_id": "snow-spell"})
    assert len(state.stack) == 2
    assert state.players[1].life == 20
    assert resolve_top_of_stack(state)
    assert state.players[1].life == 20
    assert resolve_top_of_stack(state)
    assert state.players[1].life == 22


def test_copied_search_for_glory_uses_zero_snow_spent() -> None:
    state, spell_id, _ = _search_state({"C": 2})
    state.mechanic_choice_players = set()
    cast = checked_action(state, RulesEngine(), 1, {"type": "cast_spell", "card_id": spell_id})
    hand_before_copy = len(cast.players[1].hand)
    copy_spell(cast, 1, {"target_stack_id": cast.stack[-1].id})
    assert len(cast.stack) == 2
    assert cast.stack[-1].payload["snow_mana_spent"] == 0
    assert len(cast.players[1].hand) == hand_before_copy
    assert cast.players[1].life == 20
    assert resolve_top_of_stack(cast)
    assert len(cast.players[1].hand) == hand_before_copy + 1
    assert cast.players[1].life == 20
    assert resolve_top_of_stack(cast)
    assert cast.players[1].life == 22


def test_effect_sequence_resumes_after_two_human_library_choices() -> None:
    state, _, candidates = _search_state({})
    search = {"effect_key": "search_library", "payload": {
        "contains": "card", "count": 1, "destination": "hand", "shuffle": True,
    }}
    resolve_effect(state, 1, "effect_sequence", {"effects": [
        search, search, {"effect_key": "gain_life", "payload": {"amount": 2}},
    ]})
    assert state.pending_mechanic_choice["kind"] == "search_library"
    first = checked_action(state, RulesEngine(), 1, {"type": "choose_mechanic", "card_ids": [candidates[0]]})
    assert first.pending_mechanic_choice["kind"] == "search_library"
    assert first.players[1].life == 20
    restored = deserialize_match_snapshot(serialize_match_snapshot(first))
    second = checked_action(restored, RulesEngine(), 1, {"type": "choose_mechanic", "card_ids": [candidates[1]]})
    assert second.pending_mechanic_choice is None
    assert second.players[1].life == 22
    assert candidates[0] in second.players[1].hand and candidates[1] in second.players[1].hand


def test_http_search_choice_resumes_snow_life_gain() -> None:
    from fastapi.testclient import TestClient
    from main import ACTIVE_MATCHES, MatchController, app

    state, spell_id, candidates = _search_state({"C": 2})
    state = checked_action(state, RulesEngine(), 1, {"type": "cast_spell", "card_id": spell_id})
    assert not resolve_top_of_stack(state)
    deck = [{"quantity": 60, "card_name": "Swamp"}]
    match = MatchController(
        state=state, rules=RulesEngine(), controllers={1: "human", 2: "ai"}, ai={},
        mode="player_vs_ai", deck_ids=(None, None), mainboards={1: deck, 2: deck},
        sideboards={1: [], 2: []}, game_number=1, current_game_recorded=False,
        match_complete=False, best_of=3,
    )
    with TestClient(app) as client:
        ACTIVE_MATCHES[state.id] = match
        try:
            response = client.post(f"/matches/{state.id}/action", json={
                "player_id": 1, "action": {"type": "choose_mechanic", "card_ids": [candidates[0]]},
            })
            assert response.status_code == 200
            body = response.json()
            assert body["players"]["1"]["life"] == 22
            assert any(card["id"] == candidates[0] for card in body["players"]["1"]["hand"])
            assert body["pending_mechanic_choice"] is None
        finally:
            ACTIVE_MATCHES.pop(state.id, None)
