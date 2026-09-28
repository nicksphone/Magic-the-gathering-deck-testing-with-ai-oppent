from effects.handlers import create_token, destroy_permanent
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Zone
from rules_engine.state_based_actions import apply_state_based_actions
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
