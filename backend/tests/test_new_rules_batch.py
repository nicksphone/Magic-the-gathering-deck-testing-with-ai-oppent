from __future__ import annotations

from effects.registry import resolve_effect
from game_state.state import MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import add_to_stack, resolve_top_of_stack


def test_ward_tax_blocks_underpaid_targeted_spell() -> None:
    state = MatchFactory.from_decks([{"quantity": 60, "card_name": "Island"}], [{"quantity": 60, "card_name": "Island"}])
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.priority_player = 1
    state.step = Step.PRECOMBAT_MAIN
    engine = RulesEngine()

    # Create a warded target for player 2.
    target_id = state.players[2].hand[0]
    state.players[2].hand.remove(target_id)
    state.players[2].battlefield.append(target_id)
    target = state.cards[target_id]
    target.zone = Zone.BATTLEFIELD
    target.types = ["Creature"]
    target.oracle_text = "Ward {2}"

    # Cast a 1-mana targeted spell with only 1 mana source available.
    spell_id = state.players[1].hand[0]
    spell = state.cards[spell_id]
    spell.name = "Needle Ray"
    spell.types = ["Instant"]
    spell.type_line = "Instant"
    spell.mana_cost = "{U}"
    spell.oracle_text = "Destroy target creature."
    land_id = state.players[1].hand[1]
    state.players[1].battlefield.append(land_id)
    land = state.cards[land_id]
    state.players[1].hand.remove(land_id)
    land.zone = Zone.BATTLEFIELD
    land.types = ["Land"]
    land.name = "Island"

    engine.take_action(
        state,
        1,
        {
            "type": "cast_spell",
            "card_id": spell_id,
            "targets": {"target_card_id": target_id},
        },
    )
    assert any("ward tax" in line.lower() for line in state.log)


def test_aura_without_target_goes_to_graveyard() -> None:
    state = MatchFactory.from_decks([{"quantity": 60, "card_name": "Island"}], [{"quantity": 60, "card_name": "Island"}])
    aura_id = state.players[1].hand[0]
    aura = state.cards[aura_id]
    aura.types = ["Enchantment"]
    aura.type_line = "Enchantment — Aura"
    aura.oracle_text = "Enchant creature"
    aura.zone = Zone.STACK
    add_to_stack(state, aura_id, 1, aura.name, "gain_life", {"amount": 0})
    resolve_top_of_stack(state)
    assert aura.zone == Zone.GRAVEYARD


def test_replacement_gain_life_to_draw_cards() -> None:
    state = MatchFactory.from_decks([{"quantity": 60, "card_name": "Island"}], [{"quantity": 60, "card_name": "Island"}])
    repl_id = state.players[1].hand[0]
    state.players[1].hand.remove(repl_id)
    state.players[1].battlefield.append(repl_id)
    repl = state.cards[repl_id]
    repl.zone = Zone.BATTLEFIELD
    repl.types = ["Enchantment"]
    repl.oracle_text = "If you would gain life, draw that many cards instead."
    before = len(state.players[1].hand)
    resolve_effect(state, 1, "gain_life", {"amount": 2})
    assert len(state.players[1].hand) == before + 2


def test_timing_restriction_first_main_phase_only() -> None:
    state = MatchFactory.from_decks([{"quantity": 60, "card_name": "Island"}], [{"quantity": 60, "card_name": "Island"}])
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.priority_player = 1
    state.step = Step.POSTCOMBAT_MAIN
    engine = RulesEngine()

    cid = state.players[1].hand[0]
    card = state.cards[cid]
    card.name = "First Main Only"
    card.types = ["Instant"]
    card.type_line = "Instant"
    card.mana_cost = "{U}"
    card.oracle_text = "Cast this spell only during your first main phase."
    # Ensure mana availability so move generation reaches timing gate.
    lid = state.players[1].hand[1]
    state.players[1].hand.remove(lid)
    state.players[1].battlefield.append(lid)
    land = state.cards[lid]
    land.zone = Zone.BATTLEFIELD
    land.types = ["Land"]
    land.name = "Island"
    moves = engine.legal_moves(state, 1)
    restricted = [m for m in moves if m.get("type") == "cast_spell_restricted" and m.get("card_id") == cid]
    assert len(restricted) == 1
