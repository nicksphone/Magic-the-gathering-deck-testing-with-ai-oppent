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
