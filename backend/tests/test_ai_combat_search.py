from ai.agent import AIAgent
from game_state.state import CardInstance, MatchFactory, Step, Zone


def test_master_block_search_prevents_lethal_damage_when_trade_is_available() -> None:
    state = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Forest"}],
        [{"quantity": 60, "card_name": "Forest"}],
        seed=66,
    )
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.DECLARE_BLOCKERS
    state.active_player = 1
    state.priority_player = 2
    attacker = CardInstance("attacker", "Hill Giant", 1, 1, Zone.BATTLEFIELD, ["Creature"], power=5, toughness=5)
    blocker = CardInstance("blocker", "Bear", 2, 2, Zone.BATTLEFIELD, ["Creature"], power=2, toughness=2)
    state.cards[attacker.id] = attacker
    state.cards[blocker.id] = blocker
    state.players[1].battlefield.append(attacker.id)
    state.players[2].battlefield.append(blocker.id)
    state.attackers = [attacker.id]

    action = AIAgent(difficulty="master", archetype="Control")._choose_blocks(
        state,
        [{"id": attacker.id, "name": attacker.name}],
        [{"id": blocker.id, "name": blocker.name}],
    )

    assert action == {attacker.id: blocker.id}


def test_ai_materializes_required_library_search_choice() -> None:
    state = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Forest"}],
        [{"quantity": 60, "card_name": "Forest"}],
        seed=67,
    )
    state.pregame_pending = False
    move = {
        "type": "cast_spell",
        "card_id": state.players[1].hand[0],
        "card_name": "Cultivate",
        "target_hints": {
            "library_search": {
                "max_count": 2,
                "allow_zero": True,
                "candidates": [
                    {"id": state.players[1].library[0], "name": "Forest"},
                    {"id": state.players[1].library[1], "name": "Forest"},
                ],
            }
        },
    }
    materialized = AIAgent(difficulty="master", archetype="Ramp")._materialize_action(state, move, 1)
    assert materialized["targets"]["search_card_ids"] == [state.players[1].library[0], state.players[1].library[1]]
