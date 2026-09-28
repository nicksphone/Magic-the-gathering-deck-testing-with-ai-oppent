from effects.handlers import (
    create_token, destroy_permanent, exile_all_graveyards,
    return_creature_from_graveyard_to_battlefield,
    return_from_graveyard, return_permanent_from_graveyard_to_battlefield,
    return_permanent_to_hand,
    put_land_from_hand,
)
from game_state.serializers import deserialize_match_snapshot, serialize_card_view, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.state_based_actions import apply_state_based_actions
from rules_engine.alternative_casts import validate_escape_exiles
from rules_engine.zone_actions import discard_selected
from rules_engine.card_types import is_token_card
from rules_engine.costs import activated_cost_available, apply_activated_costs
from rules_engine.move_generator import legal_moves
from tests.test_death_replacement_canonical import REST_IN_PEACE_ORACLE


def _state(with_replacement: bool):
    deck = [{"quantity": 60, "card_name": "Plains"}]
    state = MatchFactory.from_decks(deck, deck, seed=43)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    if with_replacement:
        state.cards["rip"] = CardInstance(
            id="rip", name="Rest in Peace", owner=1, controller=1,
            zone=Zone.BATTLEFIELD, types=["Enchantment"], type_line="Enchantment",
            oracle_text=REST_IN_PEACE_ORACLE,
        )
        state.players[1].battlefield.append("rip")
    create_token(state, 2, {"name": "Soldier", "power": 1, "toughness": 1})
    token_id = state.players[2].battlefield[-1]
    return state, token_id


def test_token_in_graveyard_ceases_to_exist_at_next_state_based_check():
    state, token_id = _state(False)
    state.cards["bastion"] = CardInstance(
        id="bastion", name="Bastion of Remembrance", owner=2, controller=2,
        zone=Zone.BATTLEFIELD, types=["Enchantment"], type_line="Enchantment",
        oracle_text=(
            "When this enchantment enters, create a 1/1 white Human Soldier creature token.\n"
            "Whenever a creature you control dies, each opponent loses 1 life and you gain 1 life."
        ),
    )
    state.players[2].battlefield.append("bastion")
    destroy_permanent(state, 1, {"target_card_id": token_id})
    assert state.cards[token_id].zone == Zone.GRAVEYARD

    apply_state_based_actions(state)

    assert state.cards[token_id].zone == Zone.CEASED
    assert token_id not in state.players[2].graveyard
    assert any(item.source_card_id == "bastion" for item in state.stack)
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert restored.cards[token_id].zone == Zone.CEASED
    assert token_id not in restored.players[2].graveyard


def test_replaced_token_in_exile_also_ceases_to_exist():
    state, token_id = _state(True)
    destroy_permanent(state, 1, {"target_card_id": token_id})
    assert state.cards[token_id].zone == Zone.EXILE

    apply_state_based_actions(state)

    assert state.cards[token_id].zone == Zone.CEASED
    assert token_id not in state.players[2].exile


def test_departed_token_cannot_move_again_before_state_based_check():
    state, token_id = _state(False)
    normal_id = state.players[2].hand.pop()
    state.players[2].graveyard.append(normal_id)
    state.cards[normal_id].zone = Zone.GRAVEYARD
    destroy_permanent(state, 1, {"target_card_id": token_id})
    assert state.players[2].graveyard[-1] == token_id

    return_creature_from_graveyard_to_battlefield(state, 2, {"target_card_id": token_id})
    return_permanent_from_graveyard_to_battlefield(state, 2, {"target_card_id": token_id})
    return_from_graveyard(state, 2, {})
    assert state.cards[normal_id].zone == Zone.HAND
    assert state.cards[token_id].zone == Zone.GRAVEYARD
    assert token_id in state.players[2].graveyard
    assert validate_escape_exiles(state, 2, "spell", 1, [token_id]) is None

    exile_all_graveyards(state, 1, {})
    assert state.cards[token_id].zone == Zone.GRAVEYARD
    assert token_id not in state.players[2].exile
    apply_state_based_actions(state)
    assert state.cards[token_id].zone == Zone.CEASED


def test_bounced_token_cannot_be_discarded_before_state_based_check():
    state, token_id = _state(False)
    return_permanent_to_hand(state, 1, {"target_card_id": token_id})
    assert state.cards[token_id].zone == Zone.HAND
    assert not discard_selected(state, 2, [token_id])
    assert state.cards[token_id].zone == Zone.HAND
    apply_state_based_actions(state)
    assert state.cards[token_id].zone == Zone.CEASED
    assert token_id not in state.players[2].hand


def test_token_identity_survives_type_changes_and_legacy_snapshots():
    state, token_id = _state(False)
    legacy = serialize_match_snapshot(state)
    legacy["cards"][token_id].pop("is_token")
    assert deserialize_match_snapshot(legacy).cards[token_id].is_token

    token = state.cards[token_id]
    assert token.is_token
    token.types = ["Creature"]
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert is_token_card(restored.cards[token_id])
    assert serialize_card_view(restored, token_id)["is_token"] is True
    restored.cards["haruspex"] = CardInstance(
        id="haruspex", name="Grim Haruspex", owner=2, controller=2,
        zone=Zone.BATTLEFIELD, types=["Creature"], power=3, toughness=2,
        oracle_text="Morph {B}\nWhenever another nontoken creature you control dies, draw a card.",
    )
    restored.players[2].battlefield.append("haruspex")
    destroy_permanent(restored, 1, {"target_card_id": token_id})
    apply_state_based_actions(restored)
    assert restored.cards[token_id].zone == Zone.CEASED
    assert not any(item.source_card_id == "haruspex" for item in restored.stack)


def test_bounced_token_cannot_pay_discard_cost_or_be_put_into_play():
    state, token_id = _state(False)
    for cid in list(state.players[2].hand):
        state.players[2].hand.remove(cid)
        state.players[2].library.append(cid)
        state.cards[cid].zone = Zone.LIBRARY
    state.cards[token_id].types = ["Land", "Token"]
    return_permanent_to_hand(state, 1, {"target_card_id": token_id})
    assert state.players[2].hand == [token_id]

    state.cards["imp"] = CardInstance(
        id="imp", name="Putrid Imp", owner=2, controller=2,
        zone=Zone.BATTLEFIELD, types=["Creature"], power=1, toughness=1,
        oracle_text="Discard a card: This creature gains flying until end of turn.",
    )
    state.players[2].battlefield.append("imp")
    assert not activated_cost_available(state, 2, "imp", "Discard a card")
    assert not apply_activated_costs(state, 2, "imp", "Discard a card")

    state.active_player = 2
    state.priority_player = 2
    state.step = Step.PRECOMBAT_MAIN
    assert not any(move.get("card_id") == token_id for move in legal_moves(state, 2))
    put_land_from_hand(state, 2, {})
    assert state.cards[token_id].zone == Zone.HAND
    assert token_id in state.players[2].hand
