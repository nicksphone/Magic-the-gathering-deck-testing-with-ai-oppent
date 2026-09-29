from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from ai.agent import AIAgent
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone
from main import ACTIVE_MATCHES, MatchController, app
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack


def _state():
    deck = [{"quantity": 60, "card_name": "Swamp"}]
    state = MatchFactory.from_decks(deck, deck, seed=919)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = 1
    state.step = Step.PRECOMBAT_MAIN
    state.mechanic_choice_players = {1, 2}
    state.players[1].mana_pool = {"B": 1, "C": 2}
    spell_id = state.players[1].hand[0]
    card = state.cards[spell_id]
    card.name = "Coercion"
    card.mana_cost = "{2}{B}"
    card.types = ["Sorcery"]
    card.type_line = "Sorcery"
    card.oracle_text = "Target opponent reveals their hand. You choose a card from it. That player discards that card."
    return state, spell_id


def test_coercion_caster_chooses_from_opponents_revealed_hand():
    state, spell_id = _state()
    move = next(move for move in RulesEngine().legal_moves(state, 1)
                if move.get("type") == "cast_spell" and move.get("card_id") == spell_id)
    assert [target["id"] for target in move["target_hints"]["player_targets"]] == [2]
    for targets in ({}, {"target_player": 1}):
        with pytest.raises(ActionRejected):
            checked_action(state, RulesEngine(), 1, {"type": "cast_spell", "card_id": spell_id, "targets": targets})
    state = checked_action(state, RulesEngine(), 1, {
        "type": "cast_spell", "card_id": spell_id, "targets": {"target_player": 2},
    })
    assert state.stack[-1].effect_key == "choose_revealed_discard"
    assert not resolve_top_of_stack(state)
    pending = state.pending_mechanic_choice
    assert pending["player_id"] == 1 and pending["target_player"] == 2
    assert pending["options"] == state.players[2].hand
    selected = pending["options"][-1]
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 2, {"type": "choose_mechanic", "card_ids": [selected]})
    state = checked_action(state, RulesEngine(), 1, {"type": "choose_mechanic", "card_ids": [selected]})
    assert selected in state.players[2].graveyard
    assert selected not in state.players[2].hand
    assert state.cards[spell_id].zone == Zone.GRAVEYARD
    assert state.pending_mechanic_choice is None and not state.stack


def test_ai_chooses_one_revealed_opponent_card():
    state, spell_id = _state()
    state = checked_action(state, RulesEngine(), 1, {
        "type": "cast_spell", "card_id": spell_id, "targets": {"target_player": 2},
    })
    resolve_top_of_stack(state)
    options = RulesEngine().legal_moves(state, 1)
    choice = AIAgent(difficulty="master", archetype="Control").choose_action(state, options, 1)
    assert choice.action["card_ids"][0] in state.players[2].hand
    state = checked_action(state, RulesEngine(), 1, choice.action)
    assert len(state.players[2].graveyard) == 1


def test_coercion_reveals_options_only_during_casters_choice():
    state, spell_id = _state()
    deck = [{"quantity": 60, "card_name": "Swamp"}]
    controller = MatchController(
        state=state, rules=RulesEngine(), controllers={1: "human", 2: "ai"}, ai={},
        mode="player_vs_ai", deck_ids=(None, None), mainboards={1: deck, 2: deck},
        sideboards={1: [], 2: []}, game_number=1, current_game_recorded=False,
        match_complete=False, best_of=3,
    )
    with TestClient(app) as client:
        ACTIVE_MATCHES[state.id] = controller
        try:
            initial = client.get(f"/matches/{state.id}").json()
            assert initial["players"]["2"]["hand"] == []
            controller.state = checked_action(state, RulesEngine(), 1, {
                "type": "cast_spell", "card_id": spell_id, "targets": {"target_player": 2},
            })
            resolve_top_of_stack(controller.state)
            public = client.get(f"/matches/{state.id}").json()
            assert public["players"]["2"]["hand"] == []
            move = client.get(f"/matches/{state.id}/legal-moves?player_id=1").json()["moves"][0]
            assert move["kind"] == "choose_revealed_discard"
            assert move["options"] == controller.state.players[2].hand
            assert all(move["option_labels"][cid] == controller.state.cards[cid].name for cid in move["options"])
            assert client.get(f"/matches/{state.id}/legal-moves?player_id=2").status_code == 403
        finally:
            ACTIVE_MATCHES.pop(state.id, None)
