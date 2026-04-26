from __future__ import annotations

from game_state.state import MatchFactory, Step
from rules_engine.engine import RulesEngine


def test_discard_additional_cost_is_paid() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = 1
    state.priority_player = 1
    engine = RulesEngine()

    # Ensure at least one land in battlefield for payment and two cards in hand.
    p1 = state.players[1]
    lid = p1.library.pop()
    p1.battlefield.append(lid)
    state.cards[lid].types = ["Land"]
    state.cards[lid].name = "Island"

    spell_id = p1.hand[0]
    state.cards[spell_id].name = "Test Additional Cost Spell"
    state.cards[spell_id].types = ["Sorcery"]
    state.cards[spell_id].mana_cost = "{U}"
    state.cards[spell_id].oracle_text = "As an additional cost to cast this spell, discard a card. Draw a card."

    hand_before = len(p1.hand)
    engine.take_action(state, 1, {"type": "cast_spell", "card_id": spell_id})
    assert len(p1.hand) == hand_before - 2  # spell cast + one discarded
    assert len(state.stack) == 1
