from __future__ import annotations

from game_state.state import MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine


def test_invalid_x_target_choice_does_not_spend_mana() -> None:
    deck = [{"quantity": 60, "card_name": "Plains"}]
    state = MatchFactory.from_decks(deck, deck)
    engine = RulesEngine()
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.priority_player = 1
    p1 = state.players[1]

    spell_id = p1.hand[0]
    state.cards[spell_id].name = "March of Otherworldly Light"
    state.cards[spell_id].types = ["Instant"]
    state.cards[spell_id].mana_cost = "{X}{W}"
    state.cards[spell_id].oracle_text = "Exile target creature."

    land_id = p1.library.pop()
    p1.battlefield.append(land_id)
    state.cards[land_id].zone = Zone.BATTLEFIELD
    state.cards[land_id].types = ["Land"]
    state.cards[land_id].name = "Plains"
    state.cards[land_id].tapped = False

    enemy_id = state.players[2].library.pop()
    state.players[2].battlefield.append(enemy_id)
    state.cards[enemy_id].zone = Zone.BATTLEFIELD
    state.cards[enemy_id].types = ["Creature"]
    state.cards[enemy_id].name = "Enemy Creature"
    state.cards[enemy_id].power = 2
    state.cards[enemy_id].toughness = 2

    engine.take_action(
        state,
        1,
        {
            "type": "cast_spell",
            "card_id": spell_id,
            "targets": {"target_card_id": enemy_id},  # missing x_value
        },
    )

    assert state.cards[land_id].tapped is False
    assert spell_id in p1.hand


def test_land_named_card_cannot_be_cast_as_spell() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    engine = RulesEngine()
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = 1
    state.priority_player = 1
    p1 = state.players[1]

    cid = p1.hand[0]
    state.cards[cid].name = "Forest"
    state.cards[cid].types = ["Sorcery"]  # simulate incorrect type hydration
    state.cards[cid].type_line = ""

    engine.take_action(state, 1, {"type": "cast_spell", "card_id": cid})

    assert cid in p1.hand
    assert state.stack == []
    assert any("cannot cast land card Forest as a spell" in line for line in state.log)


def test_cannot_target_creature_with_protection_from_source_color() -> None:
    deck = [{"quantity": 60, "card_name": "Mountain"}]
    state = MatchFactory.from_decks(deck, deck)
    engine = RulesEngine()
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.priority_player = 1
    p1 = state.players[1]

    spell_id = p1.hand[0]
    state.cards[spell_id].name = "Lightning Bolt"
    state.cards[spell_id].types = ["Instant"]
    state.cards[spell_id].mana_cost = "{R}"
    state.cards[spell_id].oracle_text = "Lightning Bolt deals 3 damage to any target."

    # Give player one a land for casting.
    land_id = p1.library.pop()
    p1.battlefield.append(land_id)
    state.cards[land_id].zone = Zone.BATTLEFIELD
    state.cards[land_id].types = ["Land"]
    state.cards[land_id].name = "Mountain"
    state.cards[land_id].type_line = "Basic Land — Mountain"
    state.cards[land_id].tapped = False

    target = state.players[2].library.pop()
    state.players[2].battlefield.append(target)
    state.cards[target].zone = Zone.BATTLEFIELD
    state.cards[target].types = ["Creature"]
    state.cards[target].name = "Silver Knight"
    state.cards[target].power = 2
    state.cards[target].toughness = 2
    state.cards[target].keywords = ["protection from red"]

    engine.take_action(
        state,
        1,
        {
            "type": "cast_spell",
            "card_id": spell_id,
            "targets": {"target_card_id": target},
        },
    )
    assert spell_id in p1.hand
    assert state.stack == []
    assert any("protection from red" in line.lower() for line in state.log)
