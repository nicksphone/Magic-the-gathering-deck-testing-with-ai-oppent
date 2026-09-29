from __future__ import annotations

import pytest

from ai.agent import AIAgent
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone
from main import MatchController, _serialize_match_controller
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack


def _state():
    deck = [{"quantity": 60, "card_name": "Swamp"}]
    state = MatchFactory.from_decks(deck, deck, seed=818)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = 1
    state.step = Step.PRECOMBAT_MAIN
    state.mechanic_choice_players = {1, 2}
    spell_id = state.players[1].hand[0]
    spell = state.cards[spell_id]
    spell.name = "Delirium Skeins"
    spell.mana_cost = "{2}{B}"
    spell.type_line = "Sorcery"
    spell.types = ["Sorcery"]
    spell.oracle_text = "Each player discards three cards."
    state.players[1].mana_pool = {"B": 1, "C": 2}
    return state, deck, spell_id


def _controller(state, deck):
    return MatchController(
        state=state, rules=RulesEngine(), controllers={1: "human", 2: "human"}, ai={},
        mode="human_vs_human", deck_ids=(None, None), mainboards={1: deck, 2: deck},
        sideboards={1: [], 2: []}, game_number=1, current_game_recorded=False,
        match_complete=False, best_of=3,
    )


def test_each_player_discards_after_both_private_choices_and_snapshot():
    state, deck, spell_id = _state()
    state = checked_action(state, RulesEngine(), 1, {"type": "cast_spell", "card_id": spell_id})
    assert state.stack[-1].effect_key == "each_player_discard"
    assert not resolve_top_of_stack(state)
    assert state.pending_mechanic_choice["player_id"] == 1
    first = state.players[1].hand[:3]
    second = state.players[2].hand[-3:]
    assert len(first) == 3
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 2, {"type": "choose_mechanic", "card_ids": second})
    assert state.pending_mechanic_choice["player_id"] == 1
    state = checked_action(state, RulesEngine(), 1, {"type": "choose_mechanic", "card_ids": first})
    assert state.pending_mechanic_choice["player_id"] == 2
    assert all(cid in state.players[1].hand for cid in first)
    assert not any(cid in state.players[1].graveyard for cid in first)
    assert all(cid in state.players[2].hand for cid in second)

    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = restored
    public = _serialize_match_controller(_controller(state, deck))
    assert public["pending_mechanic_choice"] == {
        "kind": "each_player_discard", "player_id": 2, "count": 3,
        "label": "Choose cards to discard",
    }
    assert not any(cid in str(public["pending_mechanic_choice"]) for cid in first)
    move = RulesEngine().legal_moves(state, 2)[0]
    assert "effect_payload" not in move and "resolving_item" not in move
    assert move["options"] == state.players[2].hand
    state = checked_action(state, RulesEngine(), 2, {"type": "choose_mechanic", "card_ids": second})
    assert state.pending_mechanic_choice is None
    assert state.stack == []
    assert state.cards[spell_id].zone == Zone.GRAVEYARD
    assert all(cid in state.players[1].graveyard for cid in first)
    assert all(cid in state.players[2].graveyard for cid in second)
    assert len(state.players[1].hand) == 3
    assert len(state.players[2].hand) == 4


def test_ai_can_make_both_discard_choices():
    state, _, spell_id = _state()
    state = checked_action(state, RulesEngine(), 1, {"type": "cast_spell", "card_id": spell_id})
    resolve_top_of_stack(state)
    for player_id in (1, 2):
        moves = RulesEngine().legal_moves(state, player_id)
        decision = AIAgent(difficulty="master", archetype="Control").choose_action(state, moves, player_id)
        state = checked_action(state, RulesEngine(), player_id, decision.action)
    assert state.pending_mechanic_choice is None
    assert len(state.players[1].hand) == 3
    assert len(state.players[2].hand) == 4


def test_random_each_player_discard_never_opens_a_choice():
    from effects.handlers import each_player_discard

    state, _, _ = _state()
    before = {pid: set(state.players[pid].hand) for pid in (1, 2)}
    each_player_discard(state, 1, {"amount": 2, "random": True})
    assert state.pending_mechanic_choice is None
    for pid in (1, 2):
        assert len(before[pid] - set(state.players[pid].hand)) == 2
        assert len(state.players[pid].graveyard) == 2
