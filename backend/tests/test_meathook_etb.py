from card_data.fallback_cards import fallback_card_payload
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.action_validation import checked_action
from rules_engine.continuous import effective_toughness
from rules_engine.engine import RulesEngine


def test_printed_meathook_etb_uses_announced_x_not_other_abilities() -> None:
    deck = [{"quantity": 60, "card_name": "Swamp"}]
    state = MatchFactory.from_decks(deck, deck, seed=209)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = 1
    state.players[1].mana_pool["B"] = 4
    oracle = fallback_card_payload("The Meathook Massacre")
    assert oracle is not None
    hook = CardInstance(
        "meathook", oracle["name"], 1, 1, Zone.HAND, ["Enchantment"],
        mana_cost=oracle["mana_cost"], type_line=oracle["type_line"],
        oracle_text=oracle["oracle_text"],
    )
    state.cards[hook.id] = hook
    state.players[1].hand.append(hook.id)
    for cid, owner, toughness in (("own-small", 1, 1), ("small", 2, 1), ("large", 2, 3)):
        creature = CardInstance(cid, cid, owner, owner, Zone.BATTLEFIELD, ["Creature"], power=toughness, toughness=toughness)
        state.cards[cid] = creature
        state.players[owner].battlefield.append(cid)

    rules = RulesEngine()
    state = checked_action(state, rules, 1, {"type": "cast_spell", "card_id": hook.id, "targets": {"x_value": 2}})
    rules.take_action(state, 1, {"type": "pass_priority"})
    rules.take_action(state, 2, {"type": "pass_priority"})
    assert hook.id in state.players[1].battlefield
    assert state.stack[-1].effect_key == "temporary_pt_buff_all"
    assert state.stack[-1].payload["toughness"] == -2

    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    rules.take_action(state, 1, {"type": "pass_priority"})
    rules.take_action(state, 2, {"type": "pass_priority"})
    assert state.cards["small"].zone == Zone.GRAVEYARD
    assert state.cards["own-small"].zone == Zone.GRAVEYARD
    assert state.cards["large"].zone == Zone.BATTLEFIELD
    assert effective_toughness(state, "large") == 1
    assert {item.effect_key for item in state.stack} == {"gain_life", "lose_life"}
    while state.stack:
        rules.take_action(state, state.priority_player, {"type": "pass_priority"})
    assert state.players[1].life == 21
    assert state.players[2].life == 19
    assert any("All creatures get -2/-2" in line for line in state.log)
