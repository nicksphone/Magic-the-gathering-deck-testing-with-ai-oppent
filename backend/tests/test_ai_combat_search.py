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
    state.players[2].life = 4
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


def test_master_block_search_avoids_safe_life_chump_block() -> None:
    state = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Forest"}],
        [{"quantity": 60, "card_name": "Forest"}],
        seed=661,
    )
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.DECLARE_BLOCKERS
    state.active_player = 1
    state.priority_player = 2
    state.players[2].life = 20
    attacker = CardInstance("attacker-safe", "Hill Giant", 1, 1, Zone.BATTLEFIELD, ["Creature"], power=4, toughness=4)
    blocker = CardInstance("blocker-token", "Soldier", 2, 2, Zone.BATTLEFIELD, ["Creature"], power=1, toughness=1)
    state.cards[attacker.id] = attacker
    state.cards[blocker.id] = blocker
    state.players[1].battlefield.append(attacker.id)
    state.players[2].battlefield.append(blocker.id)
    state.attackers = [attacker.id]

    action = AIAgent(difficulty="master", archetype="Tokens")._choose_blocks(
        state,
        [{"id": attacker.id, "name": attacker.name}],
        [{"id": blocker.id, "name": blocker.name}],
    )

    assert action == {}


def test_master_block_search_uses_effective_anthem_stats() -> None:
    state = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Forest"}],
        [{"quantity": 60, "card_name": "Forest"}],
        seed=662,
    )
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.DECLARE_BLOCKERS
    state.active_player = 1
    state.priority_player = 2
    state.players[2].life = 2
    attacker = CardInstance("attacker-anthem", "Bear", 1, 1, Zone.BATTLEFIELD, ["Creature"], power=2, toughness=2)
    blocker = CardInstance("blocker-anthem", "Soldier", 2, 2, Zone.BATTLEFIELD, ["Creature"], power=1, toughness=1)
    anthem = CardInstance(
        "anthem", "Field Anthem", 2, 2, Zone.BATTLEFIELD, ["Enchantment"],
        oracle_text="Creatures you control get +1/+1.",
    )
    state.cards.update({attacker.id: attacker, blocker.id: blocker, anthem.id: anthem})
    state.players[1].battlefield.append(attacker.id)
    state.players[2].battlefield.extend([blocker.id, anthem.id])
    state.attackers = [attacker.id]

    action = AIAgent(difficulty="master", archetype="Control")._choose_blocks(
        state,
        [{"id": attacker.id, "name": attacker.name}],
        [{"id": blocker.id, "name": blocker.name}],
    )

    assert action == {attacker.id: blocker.id}


def test_block_search_uses_blocker_controller_when_attacker_has_priority() -> None:
    state = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Forest"}],
        [{"quantity": 60, "card_name": "Forest"}],
        seed=663,
    )
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.DECLARE_BLOCKERS
    state.active_player = 1
    state.priority_player = 1
    state.players[1].life = 20
    state.players[2].life = 2
    attacker = CardInstance("attacker-priority", "Bear", 1, 1, Zone.BATTLEFIELD, ["Creature"], power=2, toughness=2)
    blocker = CardInstance("blocker-priority", "Bear", 2, 2, Zone.BATTLEFIELD, ["Creature"], power=2, toughness=2)
    state.cards.update({attacker.id: attacker, blocker.id: blocker})
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


def test_ai_materializes_graveyard_spell_target_for_recursion() -> None:
    state = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Forest"}],
        [{"quantity": 60, "card_name": "Forest"}],
        seed=68,
    )
    state.pregame_pending = False
    spell_id = "impulse"
    state.cards[spell_id] = CardInstance(
        spell_id,
        "Impulse",
        1,
        1,
        Zone.GRAVEYARD,
        ["Instant"],
        mana_cost="{2}{U}",
    )
    state.players[1].graveyard.append(spell_id)
    move = {
        "type": "cast_spell",
        "card_id": state.players[1].hand[0],
        "card_name": "Torrential Gearhulk",
        "target_hints": {
            "graveyard_spell_targets": [{"id": spell_id, "name": "Impulse"}],
        },
    }
    materialized = AIAgent(difficulty="master", archetype="Control")._materialize_action(state, move, 1)
    assert materialized["targets"]["target_card_id"] == spell_id


def test_master_attack_search_avoids_throwing_small_creature_into_large_blocker() -> None:
    state = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Forest"}],
        [{"quantity": 60, "card_name": "Forest"}],
        seed=69,
    )
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.DECLARE_ATTACKERS
    state.turn = 5
    state.active_player = 1
    state.priority_player = 1
    attacker_large = CardInstance("attacker-large", "Large", 1, 1, Zone.BATTLEFIELD, ["Creature"], power=3, toughness=3)
    attacker_small = CardInstance("attacker-small", "Small", 1, 1, Zone.BATTLEFIELD, ["Creature"], power=1, toughness=1)
    blocker_large = CardInstance("blocker-large", "Blocker", 2, 2, Zone.BATTLEFIELD, ["Creature"], power=4, toughness=4)
    state.cards.update({c.id: c for c in [attacker_large, attacker_small, blocker_large]})
    state.players[1].battlefield.extend([attacker_large.id, attacker_small.id])
    state.players[2].battlefield.append(blocker_large.id)
    for card in [attacker_large, attacker_small, blocker_large]:
        card.entered_turn = 0
    chosen = AIAgent(difficulty="master", archetype="Midrange")._choose_attackers(
        state, [attacker_large.id, attacker_small.id], 1
    )
    assert attacker_small.id not in chosen
