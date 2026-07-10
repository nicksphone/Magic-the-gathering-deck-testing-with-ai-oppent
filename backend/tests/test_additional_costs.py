from __future__ import annotations

from game_state.state import CardInstance, MatchFactory, Step, Zone
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


def test_sacrifice_additional_cost_respects_die_replacement() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = 1
    state.priority_player = 1
    engine = RulesEngine()

    p1 = state.players[1]
    replacement = CardInstance(
        id="rep",
        name="Rest in Peace",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="If a creature you control would die, exile it instead.",
    )
    state.cards[replacement.id] = replacement
    p1.battlefield.append(replacement.id)

    land_id = p1.hand[0]
    p1.hand.remove(land_id)
    p1.battlefield.append(land_id)
    state.cards[land_id].zone = Zone.BATTLEFIELD
    state.cards[land_id].types = ["Land"]

    creature_id = p1.hand[0]
    state.cards[creature_id].name = "Test Creature"
    state.cards[creature_id].types = ["Creature"]
    state.cards[creature_id].zone = Zone.BATTLEFIELD
    p1.battlefield.append(creature_id)
    p1.hand.remove(creature_id)

    spell_id = p1.hand[0]
    state.cards[spell_id].name = "Test Additional Cost Spell"
    state.cards[spell_id].types = ["Sorcery"]
    state.cards[spell_id].mana_cost = "{U}"
    state.cards[spell_id].oracle_text = "As an additional cost to cast this spell, sacrifice a creature. Draw a card."

    engine.take_action(state, 1, {"type": "cast_spell", "card_id": spell_id})

    assert state.cards[creature_id].zone == Zone.EXILE
    assert creature_id in p1.exile
    assert creature_id not in p1.graveyard
