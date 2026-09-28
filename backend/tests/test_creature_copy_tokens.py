import pytest

from card_data.fallback_cards import fallback_card_payload
from game_state.state import MatchFactory, Step, Zone
from rules_engine.action_validation import ActionRejected
from rules_engine.engine import RulesEngine
from rules_engine.events import emit_event
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.state_based_actions import apply_state_based_actions


def _state():
    deck = [{"quantity": 60, "card_name": "Forest", "type_line": "Basic Land - Forest", "oracle_text": "{T}: Add {G}."}]
    state = MatchFactory.from_decks(deck, deck, seed=49)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = 1
    return state


def _put(state, player_id: int, name: str) -> str:
    cid = state.players[player_id].library.pop()
    card = state.cards[cid]
    data = fallback_card_payload(name) or {}
    if name == "Reflection of Kiki-Jiki":
        data = fallback_card_payload("Fable of the Mirror-Breaker")["card_faces"][1]
    card.name = name
    card.zone = Zone.BATTLEFIELD
    card.oracle_text = data.get("oracle_text", "{T}: Add {G}.")
    card.type_line = data.get("type_line", "Basic Land - Forest")
    card.types = [kind for kind in ("Legendary", "Artifact", "Enchantment", "Creature", "Land") if kind in card.type_line]
    card.mana_cost = data.get("mana_cost", "")
    card.power = int(data["power"]) if str(data.get("power", "")).isdigit() else None
    card.toughness = int(data["toughness"]) if str(data.get("toughness", "")).isdigit() else None
    state.players[player_id].battlefield.append(cid)
    return cid


def _ability_moves(state, source_id):
    return [move for move in RulesEngine().legal_moves(state, 1) if move["type"] == "activate_ability" and move["card_id"] == source_id]


def test_copy_token_uses_base_characteristics_haste_and_next_opponent_end_step() -> None:
    state = _state()
    source_id = _put(state, 1, "Reflection of Kiki-Jiki")
    target_id = _put(state, 1, "Bloodtithe Harvester")
    legendary_id = _put(state, 1, "Sheoldred, the Apocalypse")
    opponent_id = _put(state, 2, "Topiary Stomper")
    _put(state, 1, "Forest")
    state.cards[target_id].counters["+1/+1"] = 1
    move = _ability_moves(state, source_id)[0]
    assert {item["id"] for item in move["target_hints"]["creature_targets"]} == {target_id}
    assert source_id not in {item["id"] for item in move["target_hints"]["creature_targets"]}
    assert legendary_id not in {item["id"] for item in move["target_hints"]["creature_targets"]}
    assert opponent_id not in {item["id"] for item in move["target_hints"]["creature_targets"]}

    RulesEngine().take_action(state, 1, {**move, "targets": {"target_card_id": target_id}}, reject_invalid=True)
    assert state.stack[-1].effect_key == "create_token_copy"
    resolve_top_of_stack(state)
    copied = [cid for cid in state.players[1].battlefield if state.cards[cid].is_token and state.cards[cid].name == "Bloodtithe Harvester"]
    assert len(copied) == 1
    copy_id = copied[0]
    token = state.cards[copy_id]
    assert (token.power, token.toughness) == (3, 2)
    assert token.counters.get("+1/+1", 0) == 0
    assert "haste" in token.keywords
    assert token.oracle_text == state.cards[target_id].oracle_text
    assert token.counters["__sac_next_end_step"] == 1

    state.active_player = 2
    state.step = Step.END_STEP
    emit_event(state, "begin_step", {"step": "end_step", "active_player": 2})
    assert any(item.effect_key == "sacrifice" and item.payload.get("target_card_id") == copy_id for item in state.stack)
    resolve_top_of_stack(state)
    apply_state_based_actions(state)
    assert token.zone == Zone.CEASED


def test_copy_activation_requires_another_nonlegendary_friendly_creature() -> None:
    state = _state()
    source_id = _put(state, 1, "Reflection of Kiki-Jiki")
    legendary_id = _put(state, 1, "Sheoldred, the Apocalypse")
    opponent_id = _put(state, 2, "Topiary Stomper")
    _put(state, 1, "Forest")
    assert _ability_moves(state, source_id) == []
    with pytest.raises(ActionRejected):
        RulesEngine().take_action(state, 1, {
            "type": "activate_ability", "card_id": source_id, "ability_index": 0,
            "targets": {"target_card_id": legendary_id},
        }, reject_invalid=True)
    assert not state.cards[source_id].tapped
    target_id = _put(state, 1, "Bloodtithe Harvester")
    move = _ability_moves(state, source_id)[0]
    with pytest.raises(ActionRejected):
        RulesEngine().take_action(state, 1, {**move, "targets": {"target_card_id": opponent_id}}, reject_invalid=True)
    RulesEngine().take_action(state, 1, {**move, "targets": {"target_card_id": target_id}}, reject_invalid=True)
    state.cards[target_id].type_line = "Legendary Creature - Vampire"
    resolve_top_of_stack(state)
    assert not any(state.cards[cid].is_token for cid in state.players[1].battlefield)
