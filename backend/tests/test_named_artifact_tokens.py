import pytest

from card_data.fallback_cards import fallback_card_payload
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine
from rules_engine.events import emit_event
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.state_based_actions import apply_state_based_actions


def _state():
    deck = [{"quantity": 60, "card_name": "Forest", "type_line": "Basic Land - Forest", "oracle_text": "{T}: Add {G}."}]
    state = MatchFactory.from_decks(deck, deck, seed=37)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = 1
    return state


def _put(state, name: str) -> str:
    cid = state.players[1].library.pop()
    card = state.cards[cid]
    card.name = name
    card.zone = Zone.BATTLEFIELD
    if name != "Forest":
        data = fallback_card_payload(name)
        card.oracle_text = data["oracle_text"]
        card.type_line = data["type_line"]
        card.types = [kind for kind in ("Artifact", "Creature") if kind in card.type_line]
        card.power = int(data["power"]) if str(data.get("power", "")).isdigit() else None
        card.toughness = int(data["toughness"]) if str(data.get("toughness", "")).isdigit() else None
    else:
        card.types = ["Land"]
        card.oracle_text = "{T}: Add {G}."
    state.players[1].battlefield.append(cid)
    return cid


@pytest.mark.parametrize("fodder_name,counters,expected_food", [
    ("Elvish Archdruid", 0, 1),
    ("Topiary Stomper", 0, 2),
    ("Elvish Archdruid", 2, 2),
])
def test_oven_uses_sacrificed_effective_toughness_and_food_can_gain_life(fodder_name, counters, expected_food) -> None:
    state = _state()
    oven_id = _put(state, "Witch's Oven")
    fodder_id = _put(state, fodder_name)
    if counters:
        state.cards[fodder_id].counters["+1/+1"] = counters
    for _ in range(2):
        _put(state, "Forest")
    rules = RulesEngine()
    oven_move = next(move for move in rules.legal_moves(state, 1) if move["type"] == "activate_ability" and move["card_id"] == oven_id)
    oven_action = {**oven_move, "targets": {"__sacrificed_toughness": 99}}
    rules.take_action(state, 1, oven_action, reject_invalid=True)
    assert fodder_id not in state.players[1].battlefield
    assert state.stack[-1].effect_key == "create_token"
    assert state.stack[-1].payload["amount"] == expected_food
    resolve_top_of_stack(state)
    food_ids = [cid for cid in state.players[1].battlefield if state.cards[cid].name == "Food"]
    assert len(food_ids) == expected_food
    assert all(state.cards[cid].types == ["Artifact", "Token"] for cid in food_ids)
    assert all(state.cards[cid].power is None and state.cards[cid].toughness is None for cid in food_ids)
    assert all("Sacrifice this token" in state.cards[cid].oracle_text for cid in food_ids)

    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    food_id = food_ids[0]
    food_move = next(move for move in rules.legal_moves(restored, 1) if move["type"] == "activate_ability" and move["card_id"] == food_id)
    before_life = restored.players[1].life
    rules.take_action(restored, 1, food_move, reject_invalid=True)
    assert restored.stack[-1].effect_key == "gain_life"
    assert food_id not in restored.players[1].battlefield
    resolve_top_of_stack(restored)
    assert restored.players[1].life == before_life + 3
    apply_state_based_actions(restored)
    assert restored.cards[food_id].zone == Zone.CEASED


def test_blood_creator_etb_and_token_activation_discard_then_draw() -> None:
    state = _state()
    harvester_id = _put(state, "Bloodtithe Harvester")
    _put(state, "Forest")
    before_hand = list(state.players[1].hand)
    emit_event(state, "enters_battlefield", {"card_id": harvester_id, "controller": 1})
    assert state.stack[-1].effect_key == "create_token"
    resolve_top_of_stack(state)
    blood_id = next(cid for cid in state.players[1].battlefield if state.cards[cid].name == "Blood")
    assert state.cards[blood_id].types == ["Artifact", "Token"]
    assert "Discard a card" in state.cards[blood_id].oracle_text
    rules = RulesEngine()
    blood_move = next(move for move in rules.legal_moves(state, 1) if move["type"] == "activate_ability" and move["card_id"] == blood_id)
    rules.take_action(state, 1, blood_move, reject_invalid=True)
    assert state.stack[-1].effect_key == "draw_cards"
    assert blood_id not in state.players[1].battlefield
    assert len(state.players[1].hand) == len(before_hand) - 1
    resolve_top_of_stack(state)
    assert len(state.players[1].hand) == len(before_hand)
    apply_state_based_actions(state)
    assert state.cards[blood_id].zone == Zone.CEASED
