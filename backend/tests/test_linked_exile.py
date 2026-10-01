from card_data.fallback_cards import fallback_card_payload
from effects.registry import resolve_effect
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from game_state.state import Step
from rules_engine.events import emit_event
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.state_based_actions import apply_state_based_actions
from rules_engine.linked_exile import flush_linked_exile_returns


def _state():
    deck = [{"quantity": 60, "card_name": "Plains"}]
    state = MatchFactory.from_decks(deck, deck, seed=621)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    printed = fallback_card_payload("Temporary Lockdown")
    assert printed is not None
    source = CardInstance(
        "lockdown", printed["name"], 1, 1, Zone.BATTLEFIELD, ["Enchantment"],
        mana_cost=printed["mana_cost"], oracle_text=printed["oracle_text"],
    )
    state.cards[source.id] = source
    state.players[1].battlefield.append(source.id)
    assign_static_order_on_battlefield_entry(state, source.id)
    return state, source


def _permanent(state, cid, owner, controller, types, cost, *, token=False):
    card = CardInstance(cid, cid, owner, controller, Zone.BATTLEFIELD, types,
                        mana_cost=cost, is_token=token, power=1 if "Creature" in types else None,
                        toughness=1 if "Creature" in types else None)
    state.cards[cid] = card
    state.players[controller].battlefield.append(cid)
    return card


def _resolve_entry(state, source):
    emit_event(state, "enters_battlefield", {"card_id": source.id, "controller": source.controller})
    assert state.stack[-1].effect_key == "exile_nonland_until_source_leaves"
    assert resolve_top_of_stack(state)


def test_temporary_lockdown_returns_owned_cards_after_source_is_destroyed() -> None:
    state, source = _state()
    _permanent(state, "own", 1, 1, ["Creature"], "{1}")
    _permanent(state, "stolen", 1, 2, ["Artifact", "Creature"], "{2}")
    _permanent(state, "opp", 2, 2, ["Enchantment"], "{1}{W}")
    _permanent(state, "big", 2, 2, ["Creature"], "{3}")
    _permanent(state, "land", 2, 2, ["Land"], "")
    _permanent(state, "token", 2, 2, ["Creature"], "", token=True)
    _resolve_entry(state, source)
    assert {"own", "stolen"} <= set(state.players[1].exile)
    assert 'opp' in state.players[2].exile
    assert 'token' not in state.players[2].exile
    assert state.cards['token'].zone == Zone.CEASED
    assert {"big", "land"} <= set(state.players[2].battlefield)
    assert len(state.linked_exiles) == 1
    assert set(state.linked_exiles[0]["card_ids"]) == {"own", "stolen", "opp"}

    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    resolve_effect(state, 2, "destroy_permanent", {"target_card_id": source.id})
    assert not state.linked_exiles
    assert {"own", "stolen"} <= set(state.players[1].battlefield)
    assert "opp" in state.players[2].battlefield
    assert state.cards["stolen"].controller == 1
    assert state.cards["token"].zone == Zone.CEASED
    apply_state_based_actions(state)
    assert state.cards["token"].zone == Zone.CEASED


def test_no_exile_if_source_leaves_before_trigger_resolves() -> None:
    state, source = _state()
    _permanent(state, "survivor", 2, 2, ["Creature"], "{1}")
    emit_event(state, "enters_battlefield", {"card_id": source.id, "controller": 1})
    assert state.stack[-1].effect_key == "exile_nonland_until_source_leaves"
    resolve_effect(state, 2, "exile", {"target_card_id": source.id})
    assert resolve_top_of_stack(state)
    assert "survivor" in state.players[2].battlefield
    assert not state.linked_exiles


def test_linked_exile_returns_after_bounce_and_ignores_new_source_incarnation() -> None:
    state, source = _state()
    _permanent(state, "held", 2, 2, ["Creature"], "{1}")
    _resolve_entry(state, source)
    old_timestamp = source.effect_timestamp
    resolve_effect(state, 2, "return_permanent_to_hand", {"target_card_id": source.id})
    assert state.cards["held"].zone == Zone.BATTLEFIELD
    assert source.zone == Zone.HAND
    state.players[1].hand.remove(source.id)
    state.players[1].battlefield.append(source.id)
    source.move_to_zone(Zone.BATTLEFIELD)
    assign_static_order_on_battlefield_entry(state, source.id)
    assert source.effect_timestamp != old_timestamp
    assert not state.linked_exiles


def test_normal_cast_puts_linked_exile_on_etb_stack_only() -> None:
    state, source = _state()
    state.players[1].battlefield.remove(source.id)
    state.players[1].hand.append(source.id)
    source.move_to_zone(Zone.HAND)
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = 1
    state.players[1].mana_pool["W"] = 3
    _permanent(state, "target", 2, 2, ["Creature"], "{1}")
    rules = RulesEngine()
    state = checked_action(state, rules, 1, {"type": "cast_spell", "card_id": source.id})
    assert state.cards["target"].zone == Zone.BATTLEFIELD
    rules.take_action(state, 1, {"type": "pass_priority"})
    rules.take_action(state, 2, {"type": "pass_priority"})
    assert source.id in state.players[1].battlefield
    assert state.stack[-1].effect_key == "exile_nonland_until_source_leaves"
    rules.take_action(state, 1, {"type": "pass_priority"})
    rules.take_action(state, 2, {"type": "pass_priority"})
    assert state.cards["target"].zone == Zone.EXILE


def test_animated_source_dies_to_state_based_damage_and_returns_cards() -> None:
    state, source = _state()
    _permanent(state, "held", 2, 2, ["Creature"], "{1}")
    _resolve_entry(state, source)
    source.types.append("Creature")
    source.power = source.toughness = 1
    source.counters["__damage_marked"] = 1
    apply_state_based_actions(state)
    assert source.zone == Zone.GRAVEYARD
    assert state.cards["held"].zone == Zone.BATTLEFIELD


def test_two_sources_leaving_together_return_both_sets() -> None:
    state, first = _state()
    _permanent(state, "first-held", 2, 2, ["Creature"], "{1}")
    _resolve_entry(state, first)
    second = CardInstance(
        "second-lockdown", first.name, 2, 2, Zone.BATTLEFIELD, ["Enchantment"],
        mana_cost=first.mana_cost, oracle_text=first.oracle_text,
    )
    state.cards[second.id] = second
    state.players[2].battlefield.append(second.id)
    assign_static_order_on_battlefield_entry(state, second.id)
    _permanent(state, "second-held", 1, 1, ["Creature"], "{1}")
    _resolve_entry(state, second)
    assert len(state.linked_exiles) == 2
    resolve_effect(state, 1, "destroy_all_enchantments", {})
    assert state.cards["first-held"].zone == Zone.BATTLEFIELD
    assert state.cards["second-held"].zone == Zone.BATTLEFIELD
    assert not state.linked_exiles


def test_moved_exile_card_is_not_returned_from_an_old_link() -> None:
    state, source = _state()
    _permanent(state, "moved", 2, 2, ["Creature"], "{1}")
    _resolve_entry(state, source)
    card = state.cards["moved"]
    state.players[2].exile.remove(card.id)
    state.players[2].hand.append(card.id)
    card.move_to_zone(Zone.HAND)
    flush_linked_exile_returns(state)
    assert not state.linked_exiles
    state.players[2].hand.remove(card.id)
    state.players[2].battlefield.append(card.id)
    card.move_to_zone(Zone.BATTLEFIELD)
    assign_static_order_on_battlefield_entry(state, card.id)
    resolve_effect(state, 1, "exile", {"target_card_id": card.id})
    resolve_effect(state, 2, "destroy_permanent", {"target_card_id": source.id})
    assert card.zone == Zone.EXILE
    assert card.id in state.players[2].exile


def test_source_reentry_before_old_trigger_resolves_does_not_exile() -> None:
    state, source = _state()
    _permanent(state, "survivor", 2, 2, ["Creature"], "{1}")
    emit_event(state, "enters_battlefield", {"card_id": source.id, "controller": 1})
    old_timestamp = source.effect_timestamp
    resolve_effect(state, 2, "return_permanent_to_hand", {"target_card_id": source.id})
    state.players[1].hand.remove(source.id)
    state.players[1].battlefield.append(source.id)
    source.move_to_zone(Zone.BATTLEFIELD)
    assign_static_order_on_battlefield_entry(state, source.id)
    assert source.effect_timestamp != old_timestamp
    assert resolve_top_of_stack(state)
    assert state.cards["survivor"].zone == Zone.BATTLEFIELD
    assert not state.linked_exiles


def test_linked_return_occurs_between_sequential_effect_clauses() -> None:
    state, source = _state()
    _permanent(state, "held", 2, 2, ["Creature"], "{1}")
    _resolve_entry(state, source)
    resolve_effect(state, 1, "effect_sequence", {"effects": [
        {"effect_key": "destroy_permanent", "payload": {"target_card_id": source.id}},
        {"effect_key": "destroy_all_creatures", "payload": {}},
    ]})
    assert state.cards["held"].zone == Zone.GRAVEYARD
