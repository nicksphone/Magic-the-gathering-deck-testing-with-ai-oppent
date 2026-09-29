"""A card returning to the battlefield is a new object, not its old permanent."""

from effects.handlers import destroy_permanent, put_green_creature_from_hand, return_creature_from_graveyard_to_battlefield, return_permanent_to_hand
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.continuous import effective_toughness
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack


def _state():
    deck = [{"quantity": 60, "card_name": "Forest", "type_line": "Basic Land - Forest"}]
    state = MatchFactory.from_decks(deck, deck, seed=418)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = 1
    state.step = Step.PRECOMBAT_MAIN
    return state


def test_bounced_creature_loses_old_counters_and_damage_on_reentry():
    state = _state()
    bear = CardInstance(
        id="bear", name="Grizzly Bears", owner=1, controller=1, zone=Zone.BATTLEFIELD,
        types=["Creature"], type_line="Creature - Bear", mana_cost="{1}{G}",
        power=2, toughness=2, counters={"+1/+1": 2, "__damage_marked": 1, "__eot_toughness": 1},
    )
    state.cards[bear.id] = bear
    state.players[1].battlefield.append(bear.id)
    return_permanent_to_hand(state, 2, {"target_card_id": bear.id})
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    put_green_creature_from_hand(state, 1, {})

    assert state.cards[bear.id].zone == Zone.BATTLEFIELD
    assert state.cards[bear.id].counters == {}
    assert effective_toughness(state, bear.id) == 2


def test_escape_enters_with_only_its_new_counter():
    state = _state()
    ox = CardInstance(
        id="ox", name="Ox of Agonas", owner=1, controller=1, zone=Zone.GRAVEYARD,
        types=["Creature"], mana_cost="{3}{R}{R}", power=4, toughness=2,
        oracle_text="Escape—{R}{R}, Exile eight other cards from your graveyard.\nThis creature escapes with a +1/+1 counter on it.",
        counters={"+1/+1": 2, "__damage_marked": 1},
    )
    state.cards[ox.id] = ox
    state.players[1].graveyard.append(ox.id)
    for index in range(8):
        card_id = f"fuel-{index}"
        state.cards[card_id] = CardInstance(card_id, "Mountain", 1, 1, Zone.GRAVEYARD, ["Land"])
        state.players[1].graveyard.append(card_id)
    state.players[1].mana_pool["R"] = 2
    move = next(move for move in RulesEngine().legal_moves(state, 1)
                if move.get("card_id") == ox.id and move["type"] == "cast_spell")
    RulesEngine().take_action(state, 1, move)
    assert resolve_top_of_stack(state)
    assert ox.zone == Zone.BATTLEFIELD
    assert ox.counters == {"+1/+1": 1}


def test_oracle_counter_persistence_except_hand_or_library():
    state = _state()
    skullbriar = CardInstance(
        id="skullbriar", name="Skullbriar, the Walking Grave", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Creature"], mana_cost="{B}{G}", power=1, toughness=1,
        oracle_text="Haste\nWhenever Skullbriar deals combat damage to a player, put a +1/+1 counter on it.\n"
                    "Counters remain on Skullbriar as it moves to any zone other than a player's hand or library.",
        counters={"+1/+1": 3, "__eot_toughness": 1},
    )
    state.cards[skullbriar.id] = skullbriar
    state.players[1].battlefield.append(skullbriar.id)
    destroy_permanent(state, 2, {"target_card_id": skullbriar.id})
    assert skullbriar.zone == Zone.GRAVEYARD
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    return_creature_from_graveyard_to_battlefield(state, 1, {"target_card_id": skullbriar.id})
    assert state.cards[skullbriar.id].counters == {"+1/+1": 3}

    return_permanent_to_hand(state, 2, {"target_card_id": skullbriar.id})
    assert state.cards[skullbriar.id].counters == {}
    put_green_creature_from_hand(state, 1, {})
    assert state.cards[skullbriar.id].counters == {}
    state.cards[skullbriar.id].counters["+1/+1"] = 2
    state.cards[skullbriar.id].move_to_zone(Zone.LIBRARY)
    assert state.cards[skullbriar.id].counters == {}
