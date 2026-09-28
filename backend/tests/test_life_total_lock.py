from __future__ import annotations

import pytest

from effects.handlers import gain_life, lose_life
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, StackItem, Step, Zone
from rules_engine.combat import _combat_damage_step
from rules_engine.costs import CostOption, activated_cost_available, apply_activated_costs, apply_additional_costs, check_cost_option_available
from rules_engine.damage_results import apply_player_damage
from rules_engine.entry import land_entry_options
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.replacement import can_pay_life, player_cant_gain_life, player_cant_lose_life
from rules_engine.replacement import pay_life
from rules_engine.stack_engine import resolve_top_of_stack


def game():
    deck = [{"quantity": 60, "card_name": "Island", "type_line": "Basic Land - Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=83)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = 1
    state.step = Step.PRECOMBAT_MAIN
    return state


def add_emperion(state):
    card = CardInstance(
        id="emperion", name="Platinum Emperion", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Artifact", "Creature"], power=8, toughness=8,
        oracle_text="Your life total can't change.",
    )
    state.cards[card.id] = card
    state.players[1].battlefield.append(card.id)
    return card.id


def test_life_total_lock_blocks_changes_and_nonzero_payments_but_not_zero_payment():
    state = game()
    add_emperion(state)
    assert player_cant_gain_life(state, 1)
    assert player_cant_lose_life(state, 1)
    assert not can_pay_life(state, 1, 2)
    assert can_pay_life(state, 1, 0)
    gain_life(state, 1, {"target_player": 1, "amount": 5})
    lose_life(state, 2, {"target_player": 1, "amount": 4})
    apply_player_damage(state, 1, 3, None)
    assert state.players[1].life == 20
    assert not player_cant_gain_life(state, 2)
    assert can_pay_life(state, 2, 2)


def test_locked_life_prevents_conditional_land_payment():
    state = game()
    add_emperion(state)
    land = CardInstance(
        id="foundry", name="Sacred Foundry", owner=1, controller=1,
        zone=Zone.HAND, types=["Land"],
        oracle_text="As this land enters, you may pay 2 life. If you don't, it enters tapped.",
    )
    state.cards[land.id] = land
    state.players[1].hand.append(land.id)
    assert land_entry_options(state, 1, land) == ["tapped"]
    moves = [move for move in RulesEngine().legal_moves(state, 1) if move.get("card_id") == land.id and move["type"] == "play_land"]
    assert [move["entry_choice"] for move in moves] == ["tapped"]
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, {"type": "play_land", "card_id": land.id, "entry_choice": "pay_two_life"})
    assert state.players[1].life == 20 and land.id in state.players[1].hand


def test_damage_is_still_dealt_and_opponent_lifelink_still_gains_life():
    state = game()
    add_emperion(state)
    attacker = CardInstance(
        id="nighthawk", name="Vampire Nighthawk", owner=2, controller=2,
        zone=Zone.BATTLEFIELD, types=["Creature"], power=2, toughness=3,
        keywords=["flying", "deathtouch", "lifelink"], oracle_text="Flying, deathtouch, lifelink",
        summoning_sick=False,
    )
    state.cards[attacker.id] = attacker
    state.players[2].battlefield.append(attacker.id)
    state.attackers = [attacker.id]
    state.active_player = 2
    _combat_damage_step(state, 1, set(), False)
    assert state.players[1].life == 20
    assert state.players[2].life == 22


def test_infect_damage_still_grants_poison_under_life_total_lock():
    state = game()
    add_emperion(state)
    source = CardInstance(
        id="glistener", name="Glistener Elf", owner=2, controller=2,
        zone=Zone.BATTLEFIELD, types=["Creature"], power=1, toughness=1,
        keywords=["infect"], oracle_text="Infect",
    )
    state.cards[source.id] = source
    state.players[2].battlefield.append(source.id)
    apply_player_damage(state, 1, 2, source.id)
    assert state.players[1].life == 20 and state.players[1].poison == 2


def test_life_payment_cost_can_use_exact_remaining_life_without_lock():
    state = game()
    state.players[1].life = 1
    card = CardInstance(
        id="sadist", name="Cruel Sadist", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Creature"], power=1, toughness=1,
        oracle_text="{B}, {T}, Pay 1 life: Put a +1/+1 counter on Cruel Sadist.",
        summoning_sick=False,
    )
    state.cards[card.id] = card
    state.players[1].battlefield.append(card.id)
    state.players[1].mana_pool["B"] = 1
    cost = "{B}, {T}, Pay 1 life"
    assert activated_cost_available(state, 1, card.id, cost)
    assert apply_activated_costs(state, 1, card.id, cost)
    assert state.players[1].life == 0 and card.tapped
    state.players[1].life = 20
    card.tapped = False
    state.players[1].mana_pool["B"] = 1
    add_emperion(state)
    assert not activated_cost_available(state, 1, card.id, cost)
    assert not apply_activated_costs(state, 1, card.id, cost)
    assert state.players[1].life == 20 and not card.tapped


def test_font_of_agonies_triggers_after_cruel_sadist_life_payment():
    state = game()
    font = CardInstance(
        id="font", name="Font of Agonies", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Enchantment"],
        oracle_text="Whenever you pay life, put that many blood counters on this enchantment.\n"
                    "{1}{B}, Remove four blood counters from this enchantment: Destroy target creature.",
    )
    sadist = CardInstance(
        id="sadist", name="Cruel Sadist", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Creature"], power=1, toughness=1,
        oracle_text="{B}, {T}, Pay 1 life: Put a +1/+1 counter on this creature.\n"
                    "{2}{B}, {T}, Remove X +1/+1 counters from this creature: It deals X damage to target creature.",
        summoning_sick=False,
    )
    for card in (font, sadist):
        state.cards[card.id] = card
        state.players[1].battlefield.append(card.id)
    state.players[1].mana_pool["B"] = 1
    engine = RulesEngine()
    action = next(
        move for move in engine.legal_moves(state, 1)
        if move["type"] == "activate_ability" and move.get("card_id") == sadist.id and move.get("ability_index") == 0
    )
    engine.take_action(state, 1, action)
    assert state.players[1].life == 19
    assert [item.source_card_id for item in state.stack] == [sadist.id, font.id]
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert resolve_top_of_stack(state)
    assert state.cards[font.id].counters.get("blood") == 1
    assert [item.source_card_id for item in state.stack] == [sadist.id]


def test_each_life_payment_creates_separate_font_trigger():
    state = game()
    font = CardInstance(
        id="font", name="Font of Agonies", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Enchantment"],
        oracle_text="Whenever you pay life, put that many blood counters on this enchantment.\n"
                    "{1}{B}, Remove four blood counters from this enchantment: Destroy target creature.",
    )
    state.cards[font.id] = font
    state.players[1].battlefield.append(font.id)
    assert pay_life(state, 1, 2)
    assert pay_life(state, 1, 1)
    assert state.players[1].life == 17
    assert [item.payload.get("amount") for item in state.stack] == [2, 1]
    assert resolve_top_of_stack(state)
    assert resolve_top_of_stack(state)
    assert state.cards[font.id].counters.get("blood") == 3


def test_shock_land_life_payment_triggers_font_after_land_enters():
    state = game()
    font = CardInstance(
        id="font", name="Font of Agonies", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Enchantment"],
        oracle_text="Whenever you pay life, put that many blood counters on this enchantment.\n"
                    "{1}{B}, Remove four blood counters from this enchantment: Destroy target creature.",
    )
    land = CardInstance(
        id="foundry", name="Sacred Foundry", owner=1, controller=1,
        zone=Zone.HAND, types=["Land"],
        oracle_text="As this land enters, you may pay 2 life. If you don't, it enters tapped.",
    )
    for card in (font, land):
        state.cards[card.id] = card
    state.players[1].battlefield.append(font.id)
    state.players[1].hand.append(land.id)
    RulesEngine().take_action(state, 1, {"type": "play_land", "card_id": land.id, "entry_choice": "pay_two_life"})
    assert state.cards[land.id].zone == Zone.BATTLEFIELD
    assert state.players[1].life == 18
    assert [item.source_card_id for item in state.stack] == [font.id]
    assert resolve_top_of_stack(state)
    assert state.cards[font.id].counters.get("blood") == 2


def test_human_orders_two_payment_triggers_after_activation():
    state = game()
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {1}
    for cid in ("font-a", "font-b"):
        card = CardInstance(
            id=cid, name="Font of Agonies", owner=1, controller=1,
            zone=Zone.BATTLEFIELD, types=["Enchantment"],
            oracle_text="Whenever you pay life, put that many blood counters on this enchantment.\n"
                        "{1}{B}, Remove four blood counters from this enchantment: Destroy target creature.",
        )
        state.cards[cid] = card
        state.players[1].battlefield.append(cid)
    sadist = CardInstance(
        id="sadist", name="Cruel Sadist", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Creature"], power=1, toughness=1,
        oracle_text="{B}, {T}, Pay 1 life: Put a +1/+1 counter on this creature.",
        summoning_sick=False,
    )
    state.cards[sadist.id] = sadist
    state.players[1].battlefield.append(sadist.id)
    state.players[1].mana_pool["B"] = 1
    engine = RulesEngine()
    action = next(
        move for move in engine.legal_moves(state, 1)
        if move["type"] == "activate_ability" and move.get("card_id") == sadist.id
    )
    engine.take_action(state, 1, action)
    assert state.pending_trigger_order
    assert [item.source_card_id for item in state.stack] == [sadist.id]
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    choice = next(
        move for move in engine.legal_moves(state, 1)
        if move["type"] == "choose_trigger_order" and move["trigger_order"][0].startswith("font-b:")
    )
    engine.take_action(state, 1, choice)
    assert [item.source_card_id for item in state.stack] == [sadist.id, "font-b", "font-a"]


def test_locked_life_payment_creates_no_font_trigger():
    state = game()
    font = CardInstance(
        id="font", name="Font of Agonies", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Enchantment"],
        oracle_text="Whenever you pay life, put that many blood counters on this enchantment.",
    )
    state.cards[font.id] = font
    state.players[1].battlefield.append(font.id)
    add_emperion(state)
    assert not pay_life(state, 1, 1)
    assert pay_life(state, 1, 0)
    assert state.players[1].life == 20
    assert not state.stack


def test_withering_boon_additional_life_cost_triggers_font_above_spell():
    state = game()
    font = CardInstance(
        id="font", name="Font of Agonies", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Enchantment"],
        oracle_text="Whenever you pay life, put that many blood counters on this enchantment.",
    )
    boon = CardInstance(
        id="boon", name="Withering Boon", owner=1, controller=1,
        zone=Zone.HAND, types=["Instant"], mana_cost="{1}{B}",
        oracle_text="As an additional cost to cast this spell, pay 3 life.\nCounter target creature spell.",
    )
    creature = CardInstance(
        id="bear", name="Grizzly Bears", owner=2, controller=2,
        zone=Zone.STACK, types=["Creature"], mana_cost="{1}{G}", power=2, toughness=2,
    )
    state.cards.update({card.id: card for card in (font, boon, creature)})
    state.players[1].battlefield.append(font.id)
    state.players[1].hand.append(boon.id)
    state.players[1].mana_pool.update({"B": 1, "C": 1})
    state.stack.append(StackItem(
        id="bear-spell", source_card_id=creature.id, controller=2,
        label=creature.name, effect_key="noop", payload={},
    ))
    engine = RulesEngine()
    action = next(
        move for move in engine.legal_moves(state, 1)
        if move["type"] == "cast_spell" and move.get("card_id") == boon.id
    )
    state = checked_action(state, engine, 1, {"type": "cast_spell", "card_id": boon.id, "targets": {"target_stack_id": "bear-spell"}})
    assert state.players[1].life == 17
    assert [item.source_card_id for item in state.stack] == [creature.id, boon.id, font.id]
    assert resolve_top_of_stack(state)
    assert state.cards[font.id].counters.get("blood") == 3
    assert resolve_top_of_stack(state)
    assert creature.id in state.players[2].graveyard
    assert boon.id in state.players[1].graveyard
    assert not state.stack


def test_type_qualified_counterspell_rejects_noncreature_stack_target():
    state = game()
    boon = CardInstance(
        id="boon", name="Withering Boon", owner=1, controller=1,
        zone=Zone.HAND, types=["Instant"], mana_cost="{1}{B}",
        oracle_text="As an additional cost to cast this spell, pay 3 life.\nCounter target creature spell.",
    )
    bolt = CardInstance(
        id="bolt", name="Lightning Bolt", owner=2, controller=2,
        zone=Zone.STACK, types=["Instant"], mana_cost="{R}",
        oracle_text="Lightning Bolt deals 3 damage to any target.",
    )
    state.cards.update({card.id: card for card in (boon, bolt)})
    state.players[1].hand.append(boon.id)
    state.players[1].mana_pool.update({"B": 1, "C": 1})
    state.stack.append(StackItem("bolt-spell", bolt.id, 2, bolt.name, "deal_damage", {}))
    engine = RulesEngine()
    assert not any(move.get("card_id") == boon.id and move["type"] == "cast_spell" for move in engine.legal_moves(state, 1))
    with pytest.raises(ActionRejected):
        checked_action(state, engine, 1, {"type": "cast_spell", "card_id": boon.id, "targets": {"target_stack_id": "bolt-spell"}})
    assert state.players[1].life == 20
    assert boon.id in state.players[1].hand


def test_additional_cost_uses_the_same_life_payment_legality():
    state = game()
    spell = CardInstance(
        id="bolt", name="Lightning Bolt", owner=1, controller=1,
        zone=Zone.HAND, types=["Instant"], mana_cost="{R}",
        oracle_text="Lightning Bolt deals 3 damage to any target.",
    )
    state.cards[spell.id] = spell
    state.players[1].hand.append(spell.id)
    state.players[1].mana_pool["R"] = 1
    option = CostOption(id="life-cost-test", label="Pay 1 life", mana_cost="{R}", pay_life=1)
    state.players[1].life = 1
    assert check_cost_option_available(state, 1, spell, option)
    assert apply_additional_costs(state, 1, option, spell.id)
    assert state.players[1].life == 0
    state.players[1].life = 20
    add_emperion(state)
    assert not check_cost_option_available(state, 1, spell, option)
    assert not apply_additional_costs(state, 1, option, spell.id)
    assert state.players[1].life == 20
