from __future__ import annotations

from effects.handlers import counter_spell, destroy_all_enchantments, destroy_permanent
from game_state.state import CardInstance, MatchFactory, StackItem, Step, Zone
from rules_engine.costs import apply_activated_costs
from rules_engine.dredge import resolve_dredge
from rules_engine.engine import RulesEngine
from rules_engine.replacement import replace_die_zone, replacement_options
from rules_engine.events import emit_event
from rules_engine.state_based_actions import apply_state_based_actions
from rules_engine.stack_engine import finish_stack_resolution, resolve_top_of_stack
from rules_engine.zone_actions import discard_selected


LORCAN_ORACLE = (
    "Flying\n"
    "Whenever a creature card is put into an opponent's graveyard from anywhere, "
    "you may pay life equal to its mana value. If you do, put it onto the battlefield "
    "under your control. It's a Warlock in addition to its other types.\n"
    "If a Warlock you control would die, exile it instead."
)
REST_IN_PEACE_ORACLE = (
    "When this enchantment enters, exile all graveyards.\n"
    "If a card or token would be put into a graveyard from anywhere, exile it instead."
)
LEYLINE_OF_THE_VOID_ORACLE = (
    "If this card is in your opening hand, you may begin the game with it on the battlefield.\n"
    "If a card would be put into an opponent's graveyard from anywhere, exile it instead."
)


def _leyline_state():
    deck = [{"quantity": 60, "card_name": "Swamp"}]
    state = MatchFactory.from_decks(deck, deck, seed=41)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.cards["leyline"] = CardInstance(
        id="leyline", name="Leyline of the Void", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Enchantment"], type_line="Enchantment",
        oracle_text=LEYLINE_OF_THE_VOID_ORACLE,
    )
    state.players[1].battlefield.append("leyline")
    return state


def test_opponent_graveyard_replacement_uses_owner_not_controller() -> None:
    state = _leyline_state()
    own_card = state.players[1].hand[0]
    opposing_card = state.players[2].hand[0]
    assert discard_selected(state, 1, [own_card])
    assert discard_selected(state, 2, [opposing_card])
    assert state.cards[own_card].zone == Zone.GRAVEYARD
    assert state.cards[opposing_card].zone == Zone.EXILE

    stolen = CardInstance(
        id="stolen", name="Grizzly Bears", owner=2, controller=1,
        zone=Zone.BATTLEFIELD, types=["Creature"], type_line="Creature — Bear",
        power=2, toughness=2, counters={"__damage_marked": 2},
    )
    state.cards[stolen.id] = stolen
    state.players[1].battlefield.append(stolen.id)
    apply_state_based_actions(state)
    assert stolen.zone == Zone.EXILE
    assert stolen.id in state.players[2].exile


def test_opponent_card_replacement_does_not_apply_to_tokens() -> None:
    state = _leyline_state()
    token = CardInstance(
        id="token", name="Spirit", owner=2, controller=2,
        zone=Zone.BATTLEFIELD, types=["Creature", "Token"], power=1, toughness=1,
    )
    state.cards[token.id] = token
    state.players[2].battlefield.append(token.id)
    assert replace_die_zone(state, 2, token.id) == "graveyard"
    assert not any(option["source_id"] == "leyline" for option in replacement_options(state, "die_zone", target_card_id=token.id))


def test_opponent_card_replacement_applies_to_resolved_spells_only_for_opponent() -> None:
    state = _leyline_state()
    for owner in (1, 2):
        cid = f"bolt-{owner}"
        state.cards[cid] = CardInstance(
            id=cid, name="Lightning Bolt", owner=owner, controller=owner,
            zone=Zone.STACK, types=["Instant"], type_line="Instant",
            oracle_text="Lightning Bolt deals 3 damage to any target.",
        )
        item = StackItem(
            id=f"item-{cid}", source_card_id=cid, controller=owner,
            label="Lightning Bolt", effect_key="deal_damage", payload={},
        )
        finish_stack_resolution(state, item, {})
        assert state.cards[cid].zone == (Zone.GRAVEYARD if owner == 1 else Zone.EXILE)


def test_opponent_card_replacement_applies_before_source_leaves_in_same_batch() -> None:
    state = _leyline_state()
    state.cards["anthem"] = CardInstance(
        id="anthem", name="Glorious Anthem", owner=2, controller=2,
        zone=Zone.BATTLEFIELD, types=["Enchantment"], type_line="Enchantment",
        oracle_text="Creatures you control get +1/+1.",
    )
    state.players[2].battlefield.append("anthem")

    destroy_all_enchantments(state, 1, {})

    assert state.cards["leyline"].zone == Zone.GRAVEYARD
    assert state.cards["anthem"].zone == Zone.EXILE


def _rest_in_peace_state():
    deck = [{"quantity": 60, "card_name": "Plains"}]
    state = MatchFactory.from_decks(deck, deck, seed=37)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.cards["rip"] = CardInstance(
        id="rip", name="Rest in Peace", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Enchantment"], type_line="Enchantment",
        oracle_text=REST_IN_PEACE_ORACLE,
    )
    state.players[1].battlefield.append("rip")
    return state


def test_rest_in_peace_exiles_a_dying_creature() -> None:
    state = _rest_in_peace_state()
    cid = state.players[2].hand.pop()
    state.players[2].battlefield.append(cid)
    card = state.cards[cid]
    card.zone = Zone.BATTLEFIELD
    card.types = ["Creature"]
    card.name = "Grizzly Bears"
    card.type_line = "Creature — Bear"
    card.power = card.toughness = 2
    card.counters["+1/+1"] = 1
    card.counters["__damage_marked"] = 3

    apply_state_based_actions(state)

    assert card.zone == Zone.EXILE
    assert cid in state.players[2].exile
    assert card.counters == {}


def test_rest_in_peace_exiles_a_discarded_card() -> None:
    state = _rest_in_peace_state()
    cid = state.players[2].hand[0]

    assert discard_selected(state, 2, [cid])
    assert state.cards[cid].zone == Zone.EXILE
    assert cid in state.players[2].exile


def test_rest_in_peace_exiles_itself_when_destroyed() -> None:
    state = _rest_in_peace_state()

    destroy_permanent(state, 2, {"target_card_id": "rip"})

    assert state.cards["rip"].zone == Zone.EXILE
    assert "rip" not in state.players[1].graveyard


def test_rest_in_peace_exiles_simultaneously_destroyed_enchantments() -> None:
    state = _rest_in_peace_state()
    state.cards["anthem"] = CardInstance(
        id="anthem", name="Glorious Anthem", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Enchantment"], type_line="Enchantment",
        oracle_text="Creatures you control get +1/+1.",
    )
    state.players[1].battlefield.append("anthem")

    destroy_all_enchantments(state, 2, {})

    assert {state.cards[cid].zone for cid in ("rip", "anthem")} == {Zone.EXILE}
    assert not state.players[1].graveyard


def test_rest_in_peace_exiles_a_resolved_or_countered_spell() -> None:
    from rules_engine.stack_engine import add_to_stack

    state = _rest_in_peace_state()
    for card_id, countered in (("resolved", False), ("countered", True)):
        card = CardInstance(
            id=card_id, name="Lightning Bolt", owner=2, controller=2,
            zone=Zone.STACK, types=["Instant"], type_line="Instant",
            oracle_text="Lightning Bolt deals 3 damage to any target.",
        )
        state.cards[card_id] = card
        item = add_to_stack(
            state, card_id, 2, "Lightning Bolt", "deal_damage", {},
        )
        if countered:
            counter_spell(state, 1, {"target_stack_id": item.id})
        else:
            finish_stack_resolution(state, state.stack.pop(), {})
        assert card.zone == Zone.EXILE
        assert card_id in state.players[2].exile
        assert card_id not in state.players[2].graveyard


def test_rest_in_peace_entry_trigger_exiles_existing_graveyards() -> None:
    state = _rest_in_peace_state()
    buried = []
    for player in state.players.values():
        cid = player.hand.pop()
        player.graveyard.append(cid)
        state.cards[cid].zone = Zone.GRAVEYARD
        buried.append(cid)

    emit_event(state, "enters_battlefield", {"card_id": "rip", "controller": 1})
    assert state.stack and state.stack[-1].effect_key == "exile_all_graveyards"
    assert resolve_top_of_stack(state)

    assert all(not player.graveyard for player in state.players.values())
    for cid in buried:
        assert state.cards[cid].zone == Zone.EXILE
        assert cid in state.players[state.cards[cid].owner].exile


def test_rest_in_peace_replaces_cycling_and_discard_cost_moves() -> None:
    state = _rest_in_peace_state()
    state.step = Step.PRECOMBAT_MAIN
    state.players[1].mana_pool["U"] = 1
    cycler = state.players[1].hand[0]
    card = state.cards[cycler]
    card.name = "Lonely Sandbar"
    card.types = ["Land"]
    card.type_line = "Land"
    card.oracle_text = "This land enters tapped.\n{T}: Add {U}.\nCycling {U} ({U}, Discard this card: Draw a card.)"

    RulesEngine().take_action(state, 1, {"type": "cycle_card", "card_id": cycler})

    assert card.zone == Zone.EXILE
    assert state.stack and state.stack[-1].effect_key == "cycle_draw"

    state.cards["imp"] = CardInstance(
        id="imp", name="Putrid Imp", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Creature"], type_line="Creature — Zombie Imp",
        power=1, toughness=1,
        oracle_text=(
            "Discard a card: This creature gains flying until end of turn.\n"
            "Threshold — As long as there are seven or more cards in your graveyard, "
            "this creature gets +1/+1 and can't block."
        ),
    )
    state.players[1].battlefield.append("imp")
    discarded = state.players[1].hand[0]
    assert apply_activated_costs(state, 1, "imp", "Discard a card")
    assert state.cards[discarded].zone == Zone.EXILE


def test_rest_in_peace_exiles_dredge_mill_and_zero_loyalty_planeswalker() -> None:
    state = _rest_in_peace_state()
    dredger = state.players[1].hand.pop()
    state.players[1].graveyard.append(dredger)
    card = state.cards[dredger]
    card.name = "Stinkweed Imp"
    card.type_line = "Creature — Imp"
    card.types = ["Creature"]
    card.zone = Zone.GRAVEYARD
    card.oracle_text = (
        "Flying\nWhenever this creature deals combat damage to a creature, destroy that creature.\n"
        "Dredge 5 (If you would draw a card, you may mill five cards instead. "
        "If you do, return this card from your graveyard to your hand.)"
    )
    milled = list(state.players[1].library[-5:])

    resolve_dredge(state, 1, {"target_player": 1, "dredge_card_id": dredger})

    assert card.zone == Zone.HAND
    assert all(state.cards[cid].zone == Zone.EXILE for cid in milled)
    assert all(cid in state.players[1].exile for cid in milled)

    state.cards["jace"] = CardInstance(
        id="jace", name="Jace, the Mind Sculptor", owner=2, controller=2,
        zone=Zone.BATTLEFIELD, types=["Planeswalker"],
        type_line="Legendary Planeswalker — Jace", loyalty=0,
    )
    state.players[2].battlefield.append("jace")
    apply_state_based_actions(state)
    assert state.cards["jace"].zone == Zone.EXILE


def test_real_subtype_replacement_applies_before_simultaneous_source_death() -> None:
    deck = [{"quantity": 60, "card_name": "Swamp"}]
    state = MatchFactory.from_decks(deck, deck, seed=31)
    state.pregame_pending = False
    state.kept_hands = {1, 2}

    for cid, name, type_line, power, toughness, oracle in (
        ("lorcan", "Lorcan, Warlock Collector", "Legendary Creature — Devil", 6, 6, LORCAN_ORACLE),
        (
            "poet", "Arrogant Poet", "Creature — Human Warlock", 2, 1,
            "Whenever this creature attacks, you may pay 2 life. If you do, it gains flying until end of turn.",
        ),
        ("bears", "Grizzly Bears", "Creature — Bear", 2, 2, ""),
    ):
        state.cards[cid] = CardInstance(
            id=cid, name=name, owner=1, controller=1, zone=Zone.BATTLEFIELD,
            types=["Creature"], type_line=type_line, power=power,
            toughness=toughness, oracle_text=oracle,
            counters={"__damage_marked": toughness},
        )
        state.players[1].battlefield.append(cid)

    assert [option["source_id"] for option in replacement_options(state, "die_zone", target_card_id="poet")] == ["lorcan"]
    assert replacement_options(state, "die_zone", target_card_id="bears") == []

    apply_state_based_actions(state)

    assert state.cards["lorcan"].zone == Zone.GRAVEYARD
    assert state.cards["poet"].zone == Zone.EXILE
    assert state.cards["bears"].zone == Zone.GRAVEYARD
    assert "poet" not in state.players[1].graveyard
