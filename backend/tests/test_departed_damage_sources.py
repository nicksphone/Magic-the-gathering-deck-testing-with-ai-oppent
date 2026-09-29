from game_state.state import CardInstance, MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from effects.handlers import destroy_permanent
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.stack_engine import add_to_stack


def _activated_pyromancer(targets=None):
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=457)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = 1
    state.step = Step.PRECOMBAT_MAIN
    source = CardInstance(
        id="pyromancer", name="Prodigal Pyromancer", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Creature"], mana_cost="{2}{R}",
        power=1, toughness=1, summoning_sick=False,
        oracle_text="{T}: Prodigal Pyromancer deals 1 damage to any target.",
    )
    state.cards[source.id] = source
    state.players[1].battlefield.append(source.id)
    if targets and targets.get("target_card_id") == "wall":
        wall = CardInstance(
            id="wall", name="Wall of Omens", owner=2, controller=2,
            zone=Zone.BATTLEFIELD, types=["Creature"], power=0, toughness=4,
        )
        state.cards[wall.id] = wall
        state.players[2].battlefield.append(wall.id)
    RulesEngine().take_action(state, 1, {
        "type": "activate_ability", "card_id": source.id,
        "ability_index": 0, "targets": targets or {"target_player": 2},
    }, reject_invalid=True)
    assert state.stack[-1].effect_key == "deal_damage"
    return state, source


def test_departed_source_uses_granted_lifelink_and_infect_after_snapshot():
    state, source = _activated_pyromancer()
    source.counters["__eot_keyword_lifelink"] = 1
    source.counters["__eot_keyword_infect"] = 1
    destroy_permanent(state, 2, {"target_card_id": source.id})
    assert source.zone == Zone.GRAVEYARD
    assert source.last_known_battlefield["colors"] == ["R"]
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert resolve_top_of_stack(state)
    assert state.players[1].life == 21
    assert state.players[2].life == 20
    assert state.players[2].poison == 1


def test_returned_new_incarnation_does_not_override_old_ability_source():
    state, source = _activated_pyromancer()
    source.counters["__eot_keyword_lifelink"] = 1
    destroy_permanent(state, 2, {"target_card_id": source.id})
    state.players[1].graveyard.remove(source.id)
    state.players[2].battlefield.append(source.id)
    source.move_to_zone(Zone.BATTLEFIELD)
    source.controller = 2
    assign_static_order_on_battlefield_entry(state, source.id)
    assert not source.last_known_battlefield
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert resolve_top_of_stack(state)
    assert state.players[1].life == 21
    assert state.players[2].life == 19


def test_live_source_losing_lifelink_before_resolution_does_not_gain_life():
    state, source = _activated_pyromancer()
    source.counters["__eot_keyword_lifelink"] = 1
    source.counters.clear()
    assert resolve_top_of_stack(state)
    assert state.players[1].life == 20
    assert state.players[2].life == 19


def test_live_source_gaining_lifelink_before_resolution_does_gain_life():
    state, source = _activated_pyromancer()
    source.counters["__eot_keyword_lifelink"] = 1
    assert resolve_top_of_stack(state)
    assert state.players[1].life == 21
    assert state.players[2].life == 19


def test_departed_source_uses_granted_wither_for_creature_damage():
    state, source = _activated_pyromancer({"target_card_id": "wall"})
    source.counters["__eot_keyword_wither"] = 1
    destroy_permanent(state, 2, {"target_card_id": source.id})
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert resolve_top_of_stack(state)
    assert state.cards["wall"].counters.get("-1/-1") == 1
    assert not state.cards["wall"].counters.get("__damage_marked")


def test_departed_source_color_does_not_follow_returned_incarnation():
    state, source = _activated_pyromancer({"target_card_id": "wall"})
    state.cards["wall"].keywords.append("protection from red")
    destroy_permanent(state, 2, {"target_card_id": source.id})
    state.players[1].graveyard.remove(source.id)
    state.players[1].battlefield.append(source.id)
    source.move_to_zone(Zone.BATTLEFIELD)
    assign_static_order_on_battlefield_entry(state, source.id)
    source.colors = ["U"]
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert resolve_top_of_stack(state)
    assert not state.cards["wall"].counters.get("__damage_marked")
    assert "does not resolve because its target is illegal" in state.log[-1]


def test_self_sacrifice_damage_ability_keeps_granted_lifelink():
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=458)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = 1
    state.step = Step.PRECOMBAT_MAIN
    source = CardInstance(
        id="firebrand", name="Fanatical Firebrand", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Creature"], mana_cost="{R}",
        power=1, toughness=1, summoning_sick=False,
        oracle_text="Haste\n{T}, Sacrifice this creature: It deals 1 damage to any target.",
    )
    source.counters["__eot_keyword_lifelink"] = 1
    state.cards[source.id] = source
    state.players[1].battlefield.append(source.id)
    RulesEngine().take_action(state, 1, {
        "type": "activate_ability", "card_id": source.id,
        "ability_index": 0, "targets": {"target_player": 2},
    }, reject_invalid=True)
    assert source.zone == Zone.GRAVEYARD
    assert state.stack[-1].effect_key == "deal_damage"
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert resolve_top_of_stack(state)
    assert state.players[1].life == 21
    assert state.players[2].life == 19


def test_departed_batch_source_uses_one_last_known_lifelink_gain():
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=460)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    source = CardInstance(
        id="rats", name="Crypt Rats", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Creature"], mana_cost="{2}{B}",
        power=1, toughness=1,
        oracle_text="{X}: Crypt Rats deals X damage to each creature and each player. Spend only black mana on X.",
    )
    source.counters["__eot_keyword_lifelink"] = 1
    state.cards[source.id] = source
    state.players[1].battlefield.append(source.id)
    add_to_stack(state, source.id, 1, "Crypt Rats ability", "damage_each_creature_and_player",
                 {"amount": 1}, is_spell=False)
    destroy_permanent(state, 2, {"target_card_id": source.id})
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert resolve_top_of_stack(state)
    assert state.players[1].life == 21
    assert state.players[2].life == 19
    assert len([entry for entry in state.log if "gains 2 life" in entry]) == 1
