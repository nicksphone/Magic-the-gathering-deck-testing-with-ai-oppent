from __future__ import annotations

from ai.agent import AIAgent
from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine
from rules_engine.mana import can_pay_with_pool_and_lands, mana_value
from rules_engine.move_generator import legal_moves


LEYLINE_ORACLE = (
    "Flash\n"
    "Domain — This spell costs {1} less to cast for each basic land type among lands you control.\n"
    "When this enchantment enters, exile target nonland permanent an opponent controls "
    "until this enchantment leaves the battlefield."
)


def _state_with_leyline():
    state = MatchFactory.from_decks([{"quantity": 60, "card_name": "Plains"}], [{"quantity": 60, "card_name": "Island"}])
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.priority_player = state.active_player = 1
    player = state.players[1]
    spell_id = player.hand[0]
    card = state.cards[spell_id]
    card.name = "Leyline Binding"
    card.types = ["Enchantment"]
    card.type_line = "Enchantment"
    card.mana_cost = "{5}{W}"
    card.oracle_text = LEYLINE_ORACLE
    for name in ("Plains", "Island", "Swamp"):
        land_id = player.library.pop()
        land = state.cards[land_id]
        land.name = name
        land.types = ["Land"]
        land.type_line = f"Basic Land — {name}"
        land.zone = Zone.BATTLEFIELD
        land.tapped = False
        player.battlefield.append(land_id)
    return state, card


def test_domain_discount_is_oracle_driven_and_does_not_change_mana_value() -> None:
    state, card = _state_with_leyline()
    assert not can_pay_with_pool_and_lands(state, 1, card.mana_cost, spell_types=set(card.types))
    assert can_pay_with_pool_and_lands(
        state, 1, card.mana_cost, spell_types=set(card.types), oracle_text=card.oracle_text,
    )
    assert mana_value(card.mana_cost) == 6
    assert any(move["type"] == "cast_spell" and move["card_id"] == card.id for move in legal_moves(state, 1))
    assert AIAgent(difficulty="master", archetype="Control")._can_pay_card_cost(state, 1, card)

    unrelated = CardInstance(
        id="unrelated", name="Different Enchantment", owner=1, controller=1,
        zone=Zone.HAND, types=["Enchantment"], mana_cost=card.mana_cost,
        oracle_text="Flash",
    )
    assert not AIAgent(difficulty="master", archetype="Control")._can_pay_card_cost(state, 1, unrelated)


def test_domain_discount_applies_to_real_cast_payment() -> None:
    state, card = _state_with_leyline()
    RulesEngine().take_action(state, 1, {"type": "cast_spell", "card_id": card.id}, reject_invalid=True)
    assert state.stack and state.stack[-1].source_card_id == card.id
    assert sum(state.cards[cid].tapped for cid in state.players[1].battlefield if "Land" in state.cards[cid].types) == 3
    assert mana_value(card.mana_cost) == 6


def test_domain_discount_combines_with_opponent_spell_tax() -> None:
    state, card = _state_with_leyline()
    tax = CardInstance(
        id="tax", name="Spell Tax", owner=2, controller=2, zone=Zone.BATTLEFIELD,
        types=["Creature"], oracle_text="Noncreature spells cost {1} more to cast.",
    )
    state.cards[tax.id] = tax
    state.players[2].battlefield.append(tax.id)
    assert not can_pay_with_pool_and_lands(
        state, 1, card.mana_cost, spell_types=set(card.types), oracle_text=card.oracle_text,
    )
