from __future__ import annotations

from game_state.state import CardInstance, MatchFactory, Step, Zone
from effects.handlers import sacrifice
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


def test_artifact_or_creature_additional_cost_can_sacrifice_an_artifact() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = 1
    state.priority_player = 1
    engine = RulesEngine()
    p1 = state.players[1]

    land_id = p1.library.pop()
    p1.battlefield.append(land_id)
    state.cards[land_id].zone = Zone.BATTLEFIELD
    state.cards[land_id].types = ["Land"]
    state.cards[land_id].name = "Island"

    artifact_id = p1.library.pop()
    p1.battlefield.append(artifact_id)
    state.cards[artifact_id].zone = Zone.BATTLEFIELD
    state.cards[artifact_id].types = ["Artifact"]
    state.cards[artifact_id].name = "Treasure Artifact"

    spell_id = p1.hand[0]
    state.cards[spell_id].name = "Artifact Sacrifice Spell"
    state.cards[spell_id].types = ["Instant"]
    state.cards[spell_id].mana_cost = "{U}"
    state.cards[spell_id].oracle_text = "As an additional cost to cast this spell, sacrifice an artifact or creature. Draw a card."

    engine.take_action(state, 1, {"type": "cast_spell", "card_id": spell_id})
    assert artifact_id not in p1.battlefield
    assert artifact_id in p1.graveyard
    assert state.stack


def test_sacrifice_handler_puts_stolen_creature_into_its_owners_graveyard() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}

    p2 = state.players[2]
    stolen_id = state.players[1].hand[0]
    state.players[1].hand.remove(stolen_id)
    p2.battlefield.append(stolen_id)
    card = state.cards[stolen_id]
    card.owner = 1
    card.controller = 2
    card.zone = Zone.BATTLEFIELD
    card.types = ["Creature"]

    sacrifice(state, 2, {"target_card_id": stolen_id})

    assert card.zone == Zone.GRAVEYARD
    assert stolen_id not in p2.battlefield
    assert stolen_id in state.players[1].graveyard
    assert stolen_id not in p2.graveyard


def test_sacrifice_additional_cost_puts_stolen_creature_into_its_owners_graveyard() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = 2
    state.priority_player = 2
    engine = RulesEngine()

    p2 = state.players[2]
    land_id = p2.library.pop()
    p2.battlefield.append(land_id)
    state.cards[land_id].zone = Zone.BATTLEFIELD
    state.cards[land_id].types = ["Land"]
    state.cards[land_id].name = "Island"
    stolen = state.players[1].hand[0]
    state.players[1].hand.remove(stolen)
    p2.battlefield.append(stolen)
    card = state.cards[stolen]
    card.owner = 1
    card.controller = 2
    card.zone = Zone.BATTLEFIELD
    card.types = ["Creature"]

    spell_id = p2.hand[0]
    state.cards[spell_id].name = "Test Additional Cost Spell"
    state.cards[spell_id].types = ["Sorcery"]
    state.cards[spell_id].mana_cost = "{U}"
    state.cards[spell_id].oracle_text = "As an additional cost to cast this spell, sacrifice a creature. Draw a card."

    engine.take_action(state, 2, {"type": "cast_spell", "card_id": spell_id})

    assert card.zone == Zone.GRAVEYARD
    assert stolen not in p2.battlefield
    assert stolen in state.players[1].graveyard
    assert stolen not in p2.graveyard
