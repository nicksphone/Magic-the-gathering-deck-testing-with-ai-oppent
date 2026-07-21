from __future__ import annotations

from game_state.state import CardInstance, MatchFactory, Zone
from rules_engine.mana import auto_pay_cost, can_pay_with_pool_and_lands


def _state() -> object:
    state = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Island"}],
        [{"quantity": 60, "card_name": "Island"}],
        seed=73,
    )
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    for player_id in (1, 2):
        for _ in range(2):
            cid = state.players[player_id].library.pop()
            state.cards[cid].zone = Zone.BATTLEFIELD
            state.cards[cid].summoning_sick = False
            state.players[player_id].battlefield.append(cid)
    return state


def test_noncreature_spell_tax_is_shared_by_legality_and_payment() -> None:
    state = _state()
    tax = CardInstance(
        id="tax", name="Static Tax", owner=2, controller=2, zone=Zone.BATTLEFIELD,
        types=["Creature"], oracle_text="Noncreature spells cost {1} more to cast.",
    )
    state.cards[tax.id] = tax
    state.players[2].battlefield.append(tax.id)

    assert not can_pay_with_pool_and_lands(
        state, 1, "{1}{U}", card_name="Consider", spell_types={"Instant"},
    )
    assert can_pay_with_pool_and_lands(
        state, 1, "{1}{U}", card_name="Llanowar Elves", spell_types={"Creature"},
    )
    assert auto_pay_cost(
        state, 1, "{1}{U}", card_name="Consider", spell_types={"Instant"},
    ) is False


def test_opponent_scoped_tax_only_affects_opponent_spells() -> None:
    state = _state()
    tax = CardInstance(
        id="tax-opponents", name="Opponent Tax", owner=1, controller=1, zone=Zone.BATTLEFIELD,
        types=["Enchantment"], oracle_text="Your opponents' noncreature spells cost {1} more to cast.",
    )
    state.cards[tax.id] = tax
    state.players[1].battlefield.append(tax.id)

    assert not can_pay_with_pool_and_lands(
        state, 2, "{1}{U}", card_name="Consider", spell_types={"Instant"},
    )
    assert can_pay_with_pool_and_lands(
        state, 1, "{1}{U}", card_name="Consider", spell_types={"Instant"},
    )
