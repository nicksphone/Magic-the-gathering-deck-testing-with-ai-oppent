from __future__ import annotations

from game_state.state import MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine


def test_cast_uses_available_alternate_cost_when_no_cost_choice_provided() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    engine = RulesEngine()
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.priority_player = 1
    p1 = state.players[1]

    spell_id = p1.hand[0]
    spell = state.cards[spell_id]
    spell.name = "Test Alt Spell"
    spell.types = ["Instant"]
    spell.mana_cost = "{3}{U}"
    spell.oracle_text = "You may pay {U} rather than pay this spell's mana cost."

    land_id = p1.library.pop()
    p1.battlefield.append(land_id)
    land = state.cards[land_id]
    land.zone = Zone.BATTLEFIELD
    land.types = ["Land"]
    land.name = "Island"
    land.tapped = False

    # No explicit cost_choice sent; backend should fallback to currently available option.
    engine.take_action(state, 1, {"type": "cast_spell", "card_id": spell_id})

    assert spell_id not in p1.hand
    assert spell.zone == Zone.STACK
