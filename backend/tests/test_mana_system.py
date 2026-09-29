from __future__ import annotations

from game_state.state import Zone
from game_state.state import CardInstance, MatchFactory, Step
from rules_engine.engine import RulesEngine
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.mana import add_generic_to_cost, auto_pay_cost, can_pay_with_pool_and_lands, hybrid_payment_symbols, land_mana_amount, mana_value
import pytest


def test_newly_controlled_animated_land_cannot_tap_until_ready_unless_hasty() -> None:
    deck = [{"quantity": 60, "card_name": "Forest", "type_line": "Basic Land - Forest"}]
    state = MatchFactory.from_decks(deck, deck, seed=118)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = 1
    cid = state.players[1].hand.pop()
    card = state.cards[cid]
    card.zone = Zone.BATTLEFIELD
    card.types = ["Land", "Creature"]
    card.summoning_sick = True
    state.players[1].battlefield.append(cid)
    assert not can_pay_with_pool_and_lands(state, 1, "{G}")
    RulesEngine().take_action(state, 1, {"type": "tap_land_for_mana", "card_id": cid})
    assert not card.tapped and state.players[1].mana_pool["G"] == 0
    card.keywords.append("haste")
    assert can_pay_with_pool_and_lands(state, 1, "{G}")
    RulesEngine().take_action(state, 1, {"type": "tap_land_for_mana", "card_id": cid})
    assert card.tapped and state.players[1].mana_pool["G"] == 1


def test_snow_cost_requires_source_provenance_and_survives_pool_snapshot() -> None:
    from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot

    deck = [{"quantity": 60, "card_name": "Forest"}]
    state = MatchFactory.from_decks(deck, deck, seed=926)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = 1
    state.step = Step.PRECOMBAT_MAIN
    source_id = state.players[1].library.pop()
    source = state.cards[source_id]
    source.zone = Zone.BATTLEFIELD
    source.types = ["Land"]
    source.type_line = "Basic Land - Forest"
    state.players[1].battlefield.append(source_id)
    assert not can_pay_with_pool_and_lands(state, 1, "{S}")
    assert not auto_pay_cost(state, 1, "{S}")
    assert not source.tapped

    source.name = "Snow-Covered Forest"
    source.type_line = "Basic Snow Land - Forest"
    assert can_pay_with_pool_and_lands(state, 1, "{S}")
    tapped = checked_action(state, RulesEngine(), 1, {"type": "tap_land_for_mana", "card_id": source_id})
    assert tapped.players[1].mana_pool["G"] == 1
    assert tapped.players[1].snow_mana_pool["G"] == 1
    restored = deserialize_match_snapshot(serialize_match_snapshot(tapped))
    cleared = deserialize_match_snapshot(serialize_match_snapshot(tapped))
    RulesEngine()._clear_mana_pools(cleared)
    assert cleared.players[1].mana_pool["G"] == cleared.players[1].snow_mana_pool["G"] == 0
    assert not can_pay_with_pool_and_lands(cleared, 1, "{S}")
    assert can_pay_with_pool_and_lands(restored, 1, "{S}")
    assert auto_pay_cost(restored, 1, "{S}", card_name="Icehide Golem")
    assert restored.players[1].mana_pool["G"] == 0
    assert restored.players[1].snow_mana_pool["G"] == 0


def test_snow_mana_cannot_pay_two_costs_at_once_and_preserves_color() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=927)
    state.players[1].mana_pool["U"] = 1
    state.players[1].snow_mana_pool["U"] = 1
    assert can_pay_with_pool_and_lands(state, 1, "{S}")
    assert not can_pay_with_pool_and_lands(state, 1, "{U}{S}")
    state.players[1].mana_pool["U"] = 2
    assert can_pay_with_pool_and_lands(state, 1, "{U}{S}")
    assert auto_pay_cost(state, 1, "{U}{S}")
    assert state.players[1].mana_pool["U"] == 0
    assert state.players[1].snow_mana_pool["U"] == 0


def test_snow_source_autopayment_and_nonland_colorless_provenance() -> None:
    deck = [{"quantity": 60, "card_name": "Forest"}]
    state = MatchFactory.from_decks(deck, deck, seed=928)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = 1
    state.step = Step.PRECOMBAT_MAIN
    land_id = state.players[1].library.pop()
    land = state.cards[land_id]
    land.name, land.type_line, land.zone = "Snow-Covered Forest", "Basic Snow Land - Forest", Zone.BATTLEFIELD
    state.players[1].battlefield.append(land_id)
    assert auto_pay_cost(state, 1, "{S}", card_name="Icehide Golem")
    assert land.tapped
    assert state.players[1].mana_pool["G"] == state.players[1].snow_mana_pool["G"] == 0

    source_id = state.players[1].library.pop()
    source = state.cards[source_id]
    source.name = "Boreal Druid"
    source.types, source.type_line = ["Creature"], "Snow Creature - Elf Druid"
    source.oracle_text = "{T}: Add {C}."
    source.zone, source.summoning_sick = Zone.BATTLEFIELD, False
    state.players[1].battlefield.append(source_id)
    tapped = checked_action(state, RulesEngine(), 1, {"type": "tap_nonland_for_mana", "card_id": source_id, "color": "C"})
    assert tapped.players[1].mana_pool["C"] == tapped.players[1].snow_mana_pool["C"] == 1
    assert auto_pay_cost(tapped, 1, "{S}", card_name="Icehide Golem")
    assert tapped.players[1].mana_pool["C"] == tapped.players[1].snow_mana_pool["C"] == 0


def test_colored_payment_keeps_snow_provenance_when_ordinary_mana_is_available() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=929)
    state.players[1].mana_pool["U"] = 2
    state.players[1].snow_mana_pool["U"] = 1
    assert auto_pay_cost(state, 1, "{U}")
    assert state.players[1].mana_pool["U"] == state.players[1].snow_mana_pool["U"] == 1
    assert auto_pay_cost(state, 1, "{S}")
    state.players[1].mana_pool["U"] = 2
    state.players[1].snow_mana_pool["U"] = 1
    assert auto_pay_cost(state, 1, "{1}")
    assert state.players[1].mana_pool["U"] == state.players[1].snow_mana_pool["U"] == 1
    assert auto_pay_cost(state, 1, "{S}")


def test_generic_payment_preserves_snow_from_other_colors_and_reports_spend() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=932)
    player = state.players[1]
    player.mana_pool.update({"C": 1, "G": 1})
    player.snow_mana_pool["C"] = 1
    first: dict = {}
    assert auto_pay_cost(state, 1, "{1}", payment_details=first)
    assert player.mana_pool["G"] == 0
    assert player.mana_pool["C"] == player.snow_mana_pool["C"] == 1
    assert first["snow_mana_spent"] == 0
    second: dict = {}
    assert auto_pay_cost(state, 1, "{1}", payment_details=second)
    assert second["snow_mana_spent"] == 1
    assert second["snow_mana_colors"] == {"C": 1}


def test_generic_payment_prefers_ordinary_source_before_snow_source() -> None:
    deck = [{"quantity": 60, "card_name": "Forest"}]
    state = MatchFactory.from_decks(deck, deck, seed=934)
    snow_id = state.players[1].library.pop()
    ordinary_id = state.players[1].library.pop()
    for cid in (snow_id, ordinary_id):
        card = state.cards[cid]
        card.zone = Zone.BATTLEFIELD
        card.types, card.type_line = ["Land"], "Basic Land - Forest"
        state.players[1].battlefield.append(cid)
    state.cards[snow_id].name = "Snow-Covered Forest"
    state.cards[snow_id].type_line = "Basic Snow Land - Forest"
    details: dict = {}
    assert auto_pay_cost(state, 1, "{1}", payment_details=details)
    assert state.cards[ordinary_id].tapped
    assert not state.cards[snow_id].tapped
    assert details["snow_mana_spent"] == 0


def test_snow_payment_search_preserves_colored_snow_pool_for_colored_cost() -> None:
    deck = [{"quantity": 60, "card_name": "Forest"}]
    state = MatchFactory.from_decks(deck, deck, seed=931)
    state.players[1].mana_pool["U"] = 1
    state.players[1].snow_mana_pool["U"] = 1
    land_id = state.players[1].library.pop()
    land = state.cards[land_id]
    land.name, land.type_line, land.zone = "Snow-Covered Forest", "Basic Snow Land - Forest", Zone.BATTLEFIELD
    state.players[1].battlefield.append(land_id)
    assert can_pay_with_pool_and_lands(state, 1, "{U}{S}")
    assert auto_pay_cost(state, 1, "{U}{S}")
    assert land.tapped
    assert all(value == 0 for value in state.players[1].mana_pool.values())
    assert all(value == 0 for value in state.players[1].snow_mana_pool.values())


def test_spectral_procession_hybrid_cost_uses_white_or_generic_mana() -> None:
    cost = "{2/W}{2/W}{2/W}"
    assert mana_value(cost) == 6
    for land_name, count in (("Plains", 3), ("Island", 6)):
        deck = [{"quantity": 60, "card_name": land_name}]
        state = MatchFactory.from_decks(deck, deck, seed=101)
        for _ in range(count):
            cid = state.players[1].library.pop()
            state.cards[cid].zone = Zone.BATTLEFIELD
            state.players[1].battlefield.append(cid)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.step = Step.PRECOMBAT_MAIN
        state.priority_player = 1
        spell_id = state.players[1].hand[0]
        spell = state.cards[spell_id]
        spell.name = "Spectral Procession"
        spell.types = ["Sorcery"]
        spell.mana_cost = cost
        assert any(move["type"] == "cast_spell" and move.get("card_id") == spell_id
                   for move in RulesEngine().legal_moves(state, 1))
        assert can_pay_with_pool_and_lands(state, 1, cost)
        assert auto_pay_cost(state, 1, cost)
        assert sum(state.cards[cid].tapped for cid in state.players[1].battlefield) == count
        assert all(value == 0 for value in state.players[1].mana_pool.values())


def test_two_color_hybrid_uses_either_color_without_changing_mana_value() -> None:
    assert mana_value("{W/U}{W/U}") == 2
    for land_name in ("Plains", "Island"):
        deck = [{"quantity": 60, "card_name": land_name}]
        state = MatchFactory.from_decks(deck, deck, seed=102)
        for _ in range(2):
            cid = state.players[1].library.pop()
            state.cards[cid].zone = Zone.BATTLEFIELD
            state.players[1].battlefield.append(cid)
        assert can_pay_with_pool_and_lands(state, 1, "{W/U}{W/U}")
        assert auto_pay_cost(state, 1, "{W/U}{W/U}")


def test_explicit_hybrid_payment_rejects_unaffordable_branch_without_tapping() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=104)
    cid = state.players[1].library.pop()
    state.cards[cid].zone = Zone.BATTLEFIELD
    state.players[1].battlefield.append(cid)
    assert hybrid_payment_symbols("{W/U}") == [{"symbol": "W/U", "choices": ["W", "U"]}]
    assert not can_pay_with_pool_and_lands(state, 1, "{W/U}", hybrid_choices=["W"])
    assert not auto_pay_cost(state, 1, "{W/U}", hybrid_choices=["W"])
    assert not state.cards[cid].tapped
    assert auto_pay_cost(state, 1, "{W/U}", hybrid_choices=["U"])
    assert state.cards[cid].tapped


def test_checked_cast_requires_valid_affordable_per_symbol_hybrid_choices() -> None:
    deck = [{"quantity": 60, "card_name": "Plains"}]
    state = MatchFactory.from_decks(deck, deck, seed=105)
    for _ in range(3):
        cid = state.players[1].library.pop()
        state.cards[cid].zone = Zone.BATTLEFIELD
        state.players[1].battlefield.append(cid)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = 1
    state.step = Step.PRECOMBAT_MAIN
    spell_id = state.players[1].hand[0]
    spell = state.cards[spell_id]
    spell.name = "Spectral Procession"
    spell.types, spell.type_line, spell.mana_cost = ["Sorcery"], "Sorcery", "{2/W}{2/W}{2/W}"
    spell.oracle_text = "Create three 1/1 white Spirit creature tokens with flying."
    move = next(move for move in RulesEngine().legal_moves(state, 1) if move.get("card_id") == spell_id and move["type"] == "cast_spell")
    option = move["cost_options"][0]
    assert option["hybrid_symbols"] == [{"symbol": "2/W", "choices": ["2", "W"]}] * 3
    action = {"type": "cast_spell", "card_id": spell_id, "cost_choice": {"id": option["id"]}}
    for choices in (["2", "2", "2"], ["W", "W"], ["U", "W", "W"]):
        with pytest.raises(ActionRejected):
            checked_action(state, RulesEngine(), 1, {**action, "hybrid_choices": choices})
        assert spell_id in state.players[1].hand
        assert not any(state.cards[cid].tapped for cid in state.players[1].battlefield)
    cast = checked_action(state, RulesEngine(), 1, {**action, "hybrid_choices": ["W", "W", "W"]})
    assert cast.stack[-1].source_card_id == spell_id
    assert sum(cast.cards[cid].tapped for cid in cast.players[1].battlefield) == 3


def test_hybrid_choices_are_exposed_for_exile_and_top_library_casts() -> None:
    deck = [{"quantity": 60, "card_name": "Plains"}]
    state = MatchFactory.from_decks(deck, deck, seed=106)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = 1
    state.step = Step.PRECOMBAT_MAIN
    player = state.players[1]
    for _ in range(3):
        cid = player.library.pop()
        state.cards[cid].zone = Zone.BATTLEFIELD
        player.battlefield.append(cid)
    exile_id = player.library.pop()
    exiled = state.cards[exile_id]
    exiled.name, exiled.types, exiled.type_line = "Spectral Procession", ["Sorcery"], "Sorcery"
    exiled.mana_cost = "{2/W}{2/W}{2/W}"
    exiled.oracle_text = "Create three 1/1 white Spirit creature tokens with flying."
    exiled.zone = Zone.EXILE
    player.exile.append(exile_id)
    player.exile_play_until[exile_id] = state.turn
    walker = CardInstance(
        id="walker-hybrid", name="Realmwalker", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Creature"], type_line="Creature - Shapeshifter",
        chosen_creature_type="Kithkin",
        oracle_text="You may cast creature spells of the chosen type from the top of your library.",
    )
    state.cards[walker.id] = walker
    player.battlefield.append(walker.id)
    top = state.cards[player.library[-1]]
    top.name, top.types, top.type_line = "Figure of Destiny", ["Creature"], "Creature — Kithkin"
    top.mana_cost = "{R/W}"
    moves = RulesEngine().legal_moves(state, 1)
    exile_move = next(move for move in moves if move.get("card_id") == exile_id and move.get("from_exile"))
    library_move = next(move for move in moves if move.get("card_id") == top.id and move.get("from_library"))
    assert exile_move["cost_options"][0]["hybrid_symbols"] == [{"symbol": "2/W", "choices": ["2", "W"]}] * 3
    assert library_move["cost_options"][0]["hybrid_symbols"] == [{"symbol": "R/W", "choices": ["R", "W"]}]


def test_phyrexian_payment_and_life_reservation_use_shared_planner() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=107)
    assert mana_value("{G/P}{G/U/P}") == 2
    assert hybrid_payment_symbols("{G/P}{G/U/P}") == [
        {"symbol": "G/P", "choices": ["G", "P"]},
        {"symbol": "G/U/P", "choices": ["G", "U", "P"]},
    ]
    assert can_pay_with_pool_and_lands(state, 1, "{G/P}", hybrid_choices=["P"])
    assert not can_pay_with_pool_and_lands(state, 1, "{G/P}", hybrid_choices=["G"])
    state.players[1].life = 3
    assert not can_pay_with_pool_and_lands(state, 1, "{G/P}", hybrid_choices=["P"], reserved_life=2)
    assert not auto_pay_cost(state, 1, "{G/P}", hybrid_choices=["P"], reserved_life=2)
    assert state.players[1].life == 3
    assert auto_pay_cost(state, 1, "{G/U/P}", hybrid_choices=["P"])
    assert state.players[1].life == 1
    assert not can_pay_with_pool_and_lands(state, 1, "{G/P}", hybrid_choices=["P"])


def test_activated_phyrexian_cost_reserves_separate_life_payment() -> None:
    from rules_engine.costs import activated_cost_available, apply_activated_costs

    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=109)
    source = CardInstance(
        id="cost-probe", name="Cost probe", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Artifact"],
    )
    state.cards[source.id] = source
    state.players[1].battlefield.append(source.id)
    state.players[1].life = 3
    cost = "{B/P}, Pay 2 life"
    assert not activated_cost_available(state, 1, source.id, cost)
    assert not apply_activated_costs(state, 1, source.id, cost)
    assert state.players[1].life == 3
    state.players[1].life = 5
    assert activated_cost_available(state, 1, source.id, cost)
    assert apply_activated_costs(state, 1, source.id, cost)
    assert state.players[1].life == 1


def test_pestilent_souleater_activated_phyrexian_choice() -> None:
    from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
    from rules_engine.continuous import has_keyword
    from rules_engine.stack_engine import resolve_top_of_stack
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=110)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = 1
    state.step = Step.PRECOMBAT_MAIN
    source = CardInstance(
        id="pestilent-souleater", name="Pestilent Souleater", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Artifact", "Creature"],
        oracle_text="{B/P}: Pestilent Souleater gains infect until end of turn.",
        power=3, toughness=3,
    )
    state.cards[source.id] = source
    state.players[1].battlefield.append(source.id)
    move = next(move for move in RulesEngine().legal_moves(state, 1) if move.get("card_id") == source.id and move["type"] == "activate_ability")
    assert move["hybrid_symbols"] == [{"symbol": "B/P", "choices": ["B", "P"]}]
    action = {"type": "activate_ability", "card_id": source.id, "ability_index": move["ability_index"]}
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, {**action, "hybrid_choices": ["B"]})
    assert state.players[1].life == 20 and not state.stack
    paid_life = checked_action(state, RulesEngine(), 1, {**action, "hybrid_choices": ["P"]})
    assert paid_life.players[1].life == 18
    assert paid_life.stack[-1].source_card_id == source.id
    assert paid_life.stack[-1].label == "Pestilent Souleater ability"
    assert resolve_top_of_stack(paid_life)
    assert has_keyword(paid_life, source.id, "infect")
    restored = deserialize_match_snapshot(serialize_match_snapshot(paid_life))
    assert has_keyword(restored, source.id, "infect")
    RulesEngine()._clear_marked_damage(restored)
    assert not has_keyword(restored, source.id, "infect")
    state.players[1].mana_pool["B"] = 1
    paid_mana = checked_action(state, RulesEngine(), 1, {**action, "hybrid_choices": ["B"]})
    assert paid_mana.players[1].life == 20
    assert paid_mana.players[1].mana_pool["B"] == 0
    paid_mana.players[1].battlefield.remove(source.id)
    paid_mana.players[1].graveyard.append(source.id)
    paid_mana.cards[source.id].move_to_zone(Zone.GRAVEYARD)
    assert resolve_top_of_stack(paid_mana)
    assert "__eot_keyword_infect" not in paid_mana.cards[source.id].counters


def test_compleated_uses_announced_phyrexian_life_choice_on_entry() -> None:
    from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
    from effects.handlers import counter_spell
    from rules_engine.stack_engine import resolve_top_of_stack
    from rules_engine.state_based_actions import apply_state_based_actions

    for branch, pool, expected_loyalty in (
        ("P", {"C": 2, "G": 1, "U": 1}, 3),
        ("G", {"C": 2, "G": 2, "U": 1}, 5),
    ):
        deck = [{"quantity": 60, "card_name": "Island"}]
        state = MatchFactory.from_decks(deck, deck, seed=924)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.active_player = state.priority_player = 1
        state.step = Step.PRECOMBAT_MAIN
        source = state.cards[state.players[1].hand[0]]
        source.name = "Tamiyo, Compleated Sage"
        source.types = ["Legendary", "Planeswalker"]
        source.mana_cost = "{2}{G}{G/U/P}{U}"
        source.loyalty = 5
        source.oracle_text = (
            "Compleated ({G/U/P} can be paid with {G}, {U}, or 2 life. "
            "If life was paid, this planeswalker enters with two fewer loyalty counters.)\n"
            "+1: Tap up to one target artifact or creature. It doesn't untap during its controller's next untap step."
        )
        state.players[1].mana_pool.update(pool)
        action = {"type": "cast_spell", "card_id": source.id, "cost_choice": {"id": "base"}, "hybrid_choices": [branch]}
        cast = checked_action(state, RulesEngine(), 1, action)
        assert cast.players[1].life == (18 if branch == "P" else 20)
        assert cast.stack[-1].payload["__phyrexian_life_symbols"] == (1 if branch == "P" else 0)
        if branch == "P":
            countered = deserialize_match_snapshot(serialize_match_snapshot(cast))
            counter_spell(countered, 2, {"target_stack_id": countered.stack[-1].id})
            assert countered.cards[source.id].zone == Zone.GRAVEYARD
            assert countered.cards[source.id].loyalty == 5
        restored = deserialize_match_snapshot(serialize_match_snapshot(cast))
        assert resolve_top_of_stack(restored)
        assert restored.cards[source.id].loyalty == expected_loyalty
        assert restored.cards[source.id].zone == Zone.BATTLEFIELD
        restored.players[1].battlefield.remove(source.id)
        restored.players[1].graveyard.append(source.id)
        restored.cards[source.id].move_to_zone(Zone.GRAVEYARD)
        apply_state_based_actions(restored)
        assert restored.cards[source.id].loyalty == 5


def test_mutagenic_growth_phyrexian_life_trigger_is_above_spell() -> None:
    from copy import deepcopy
    from ai.agent import AIAgent
    from rules_engine.stack_engine import resolve_top_of_stack

    deck = [{"quantity": 60, "card_name": "Forest"}]
    state = MatchFactory.from_decks(deck, deck, seed=108)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = 1
    state.step = Step.PRECOMBAT_MAIN
    spell_id = state.players[1].hand[0]
    spell = state.cards[spell_id]
    spell.name, spell.types, spell.type_line = "Mutagenic Growth", ["Instant"], "Instant"
    spell.mana_cost = "{G/P}"
    spell.oracle_text = "Target creature gets +2/+2 until end of turn."
    creature = CardInstance(
        id="elf-phyrexian", name="Llanowar Elves", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Creature"], power=1, toughness=1,
    )
    font = CardInstance(
        id="font-phyrexian", name="Font of Agonies", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Enchantment"],
        oracle_text="Whenever you pay life, put that many blood counters on this enchantment.",
    )
    for card in (creature, font):
        state.cards[card.id] = card
        state.players[1].battlefield.append(card.id)
    move = next(move for move in RulesEngine().legal_moves(state, 1) if move.get("card_id") == spell_id and move["type"] == "cast_spell")
    assert move["cost_options"][0]["hybrid_symbols"] == [{"symbol": "G/P", "choices": ["G", "P"]}]
    danger = deepcopy(state)
    danger.players[1].life = 2
    ai_move = AIAgent(archetype="Aggro").choose_action(danger, RulesEngine().legal_moves(danger, 1), 1).action
    assert ai_move.get("type") != "cast_spell" or ai_move.get("card_id") != spell_id
    action = {"type": "cast_spell", "card_id": spell_id, "cost_choice": {"id": move["cost_options"][0]["id"]},
              "targets": {"target_card_id": creature.id}}
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, {**action, "hybrid_choices": ["G"]})
    assert state.players[1].life == 20 and spell_id in state.players[1].hand
    paid = checked_action(state, RulesEngine(), 1, {**action, "hybrid_choices": ["P"]})
    assert paid.players[1].life == 18
    assert [item.source_card_id for item in paid.stack] == [spell_id, font.id]
    assert resolve_top_of_stack(paid)
    assert paid.cards[font.id].counters.get("blood") == 2
    paid.players[1].life = 1
    assert not can_pay_with_pool_and_lands(paid, 1, "{G/P}", hybrid_choices=["P"])


def test_generic_reduction_applies_after_monocolored_hybrid_choice(monkeypatch) -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=103)
    cid = state.players[1].library.pop()
    state.cards[cid].zone = Zone.BATTLEFIELD
    state.players[1].battlefield.append(cid)
    assert not can_pay_with_pool_and_lands(state, 1, "{2/W}")

    def reduce_one(context):
        context.generic_reduction = 1
        return context

    monkeypatch.setattr("rules_engine.mana.apply_cost_modifiers", reduce_one)
    assert can_pay_with_pool_and_lands(state, 1, "{2/W}")
    assert auto_pay_cost(state, 1, "{2/W}")
    assert state.cards[cid].tapped
    assert add_generic_to_cost("{2/W}{W/U}", 1) == "{1}{2/W}{W/U}"


def test_nonland_single_color_source_is_used_before_flexible_land() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=96)
    fountain = CardInstance(
        id="fountain", name="Hallowed Fountain", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Land"], type_line="Land - Plains Island",
        oracle_text="{T}: Add {W} or {U}.",
    )
    diamond = CardInstance(
        id="diamond", name="Marble Diamond", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Artifact"], type_line="Artifact",
        oracle_text="{T}: Add {W}.",
    )
    for card in (fountain, diamond):
        state.cards[card.id] = card
        state.players[1].battlefield.append(card.id)

    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.priority_player = 1
    spell_id = state.players[1].hand[0]
    spell = state.cards[spell_id]
    spell.name = "Lavinia, Azorius Renegade"
    spell.types = ["Creature", "Legendary"]
    spell.mana_cost = "{W}{U}"
    assert any(move["type"] == "cast_spell" and move.get("card_id") == spell_id
               for move in RulesEngine().legal_moves(state, 1))
    assert can_pay_with_pool_and_lands(state, 1, "{W}{U}")
    assert auto_pay_cost(state, 1, "{W}{U}")
    assert fountain.tapped and diamond.tapped
    assert all(value == 0 for value in state.players[1].mana_pool.values())


def test_multi_mana_source_surplus_pays_generic_cost() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=97)
    lotus = CardInstance(
        id="lotus", name="Gilded Lotus", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Artifact"], type_line="Artifact",
        oracle_text="{T}: Add three mana of any one color.",
    )
    state.cards[lotus.id] = lotus
    state.players[1].battlefield.append(lotus.id)
    assert can_pay_with_pool_and_lands(state, 1, "{W}{2}")
    assert auto_pay_cost(state, 1, "{W}{2}")
    assert lotus.tapped
    assert all(value == 0 for value in state.players[1].mana_pool.values())


def test_can_pay_known_mana_cost_with_untapped_lands() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    # Put a UU spell in hand with known mana cost.
    cid = state.players[1].hand[0]
    state.cards[cid].name = "Counterspell"
    state.cards[cid].types = ["Instant"]
    state.cards[cid].mana_cost = "{U}{U}"

    # Ensure player has at least two islands on battlefield.
    p1 = state.players[1]
    for _ in range(2):
        lid = p1.library.pop()
        p1.battlefield.append(lid)
        state.cards[lid].zone = Zone.BATTLEFIELD
        state.cards[lid].types = ["Land"]
        state.cards[lid].name = "Island"

    assert can_pay_with_pool_and_lands(state, 1, "{U}{U}") is True


def test_cast_spell_rejects_if_cost_unpaid() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    engine = RulesEngine()
    state.step = Step.PRECOMBAT_MAIN
    state.priority_player = 1

    cid = state.players[1].hand[0]
    state.cards[cid].name = "Big Spell"
    state.cards[cid].types = ["Sorcery"]
    state.cards[cid].mana_cost = "{5}{U}{U}"

    before_hand = len(state.players[1].hand)
    engine.take_action(state, 1, {"type": "cast_spell", "card_id": cid})
    assert len(state.players[1].hand) == before_hand


def test_mana_pool_empties_on_step_transition() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    engine = RulesEngine()
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = 1
    state.priority_player = 1
    state.players[1].mana_pool["U"] = 2
    state.players[2].mana_pool["R"] = 1

    engine.take_action(state, 1, {"type": "pass_priority"})
    engine.take_action(state, 2, {"type": "pass_priority"})

    assert state.step == Step.BEGIN_COMBAT
    assert sum(state.players[1].mana_pool.values()) == 0
    assert sum(state.players[2].mana_pool.values()) == 0


def test_generic_cost_can_use_colored_mana_pool() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    p1 = state.players[1]
    p1.mana_pool["U"] = 3

    assert can_pay_with_pool_and_lands(state, 1, "{3}") is True
    assert auto_pay_cost(state, 1, "{3}") is True
    assert sum(p1.mana_pool.values()) == 0


def test_colored_and_generic_cost_cannot_double_spend_same_pool_mana() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    p1 = state.players[1]
    p1.mana_pool["U"] = 1

    assert can_pay_with_pool_and_lands(state, 1, "{U}{1}") is False


def test_explicit_colorless_symbols_require_colorless_mana() -> None:
    deck = [{"quantity": 60, "card_name": "Mountain"}]
    state = MatchFactory.from_decks(deck, deck)
    p1 = state.players[1]
    p1.mana_pool["R"] = 2

    assert can_pay_with_pool_and_lands(state, 1, "{C}{C}") is False

    p1.mana_pool["R"] = 0
    p1.mana_pool["C"] = 2
    assert can_pay_with_pool_and_lands(state, 1, "{C}{C}") is True
    assert auto_pay_cost(state, 1, "{C}{C}") is True
    assert sum(p1.mana_pool.values()) == 0


def test_dual_land_type_line_counts_as_blue_source_for_double_blue_cost() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    p1 = state.players[1]
    p1.battlefield = []
    # Two Hallowed Fountains should satisfy {U}{U}.
    for _ in range(2):
        cid = p1.library.pop()
        p1.battlefield.append(cid)
        card = state.cards[cid]
        card.zone = Zone.BATTLEFIELD
        card.types = ["Land"]
        card.name = "Hallowed Fountain"
        card.type_line = "Land — Plains Island"
        card.tapped = False

    assert can_pay_with_pool_and_lands(state, 1, "{U}{U}") is True
    assert auto_pay_cost(state, 1, "{U}{U}") is True
    tapped = sum(1 for cid in p1.battlefield if state.cards[cid].tapped)
    assert tapped == 2


def test_dual_land_type_line_supports_multiple_other_colors() -> None:
    deck = [{"quantity": 60, "card_name": "Forest"}]
    state = MatchFactory.from_decks(deck, deck)
    p1 = state.players[1]
    p1.battlefield = []
    # Two Stomping Ground should satisfy {R}{G}.
    for _ in range(2):
        cid = p1.library.pop()
        p1.battlefield.append(cid)
        card = state.cards[cid]
        card.zone = Zone.BATTLEFIELD
        card.types = ["Land"]
        card.name = "Stomping Ground"
        card.type_line = "Land — Mountain Forest"
        card.tapped = False

    assert can_pay_with_pool_and_lands(state, 1, "{R}{G}") is True
    assert auto_pay_cost(state, 1, "{R}{G}") is True


def test_oracle_text_dual_land_without_basic_subtypes_is_supported() -> None:
    deck = [{"quantity": 60, "card_name": "Plains"}]
    state = MatchFactory.from_decks(deck, deck)
    p1 = state.players[1]
    p1.battlefield = []
    cid = p1.library.pop()
    p1.battlefield.append(cid)
    card = state.cards[cid]
    card.zone = Zone.BATTLEFIELD
    card.types = ["Land"]
    card.name = "Battlefield Forge"
    card.type_line = "Land"
    card.oracle_text = "{T}: Add {R} or {W}."
    card.tapped = False

    assert can_pay_with_pool_and_lands(state, 1, "{W}") is True


def test_tap_land_for_mana_honors_requested_color_when_available() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    engine = RulesEngine()
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = 1
    state.priority_player = 1
    p1 = state.players[1]
    p1.battlefield = []
    p1.mana_pool = {"W": 0, "U": 0, "B": 0, "R": 0, "G": 0, "C": 0}

    cid = p1.library.pop()
    p1.battlefield.append(cid)
    card = state.cards[cid]
    card.zone = Zone.BATTLEFIELD
    card.types = ["Land"]
    card.name = "Hallowed Fountain"
    card.type_line = "Land — Plains Island"
    card.oracle_text = "{T}: Add {W} or {U}."
    card.tapped = False

    engine.take_action(state, 1, {"type": "tap_land_for_mana", "card_id": cid, "color": "W"})
    assert state.players[1].mana_pool["W"] == 1
    assert state.players[1].mana_pool["U"] == 0


def test_mana_creature_can_help_pay_cost_when_not_summoning_sick() -> None:
    deck = [{"quantity": 60, "card_name": "Forest"}]
    state = MatchFactory.from_decks(deck, deck)
    p1 = state.players[1]
    p1.battlefield = []

    # One Forest land.
    land_id = p1.library.pop()
    p1.battlefield.append(land_id)
    land = state.cards[land_id]
    land.zone = Zone.BATTLEFIELD
    land.types = ["Land"]
    land.name = "Forest"
    land.type_line = "Basic Land — Forest"
    land.tapped = False

    # One Llanowar Elves mana creature that can tap for G.
    elf_id = p1.library.pop()
    p1.battlefield.append(elf_id)
    elf = state.cards[elf_id]
    elf.zone = Zone.BATTLEFIELD
    elf.types = ["Creature"]
    elf.name = "Llanowar Elves"
    elf.oracle_text = "{T}: Add {G}."
    elf.tapped = False
    elf.summoning_sick = False

    assert can_pay_with_pool_and_lands(state, 1, "{1}{G}") is True
    assert auto_pay_cost(state, 1, "{1}{G}") is True
    assert land.tapped is True
    assert elf.tapped is True


def test_summoning_sick_mana_creature_cannot_pay_tap_cost() -> None:
    deck = [{"quantity": 60, "card_name": "Forest"}]
    state = MatchFactory.from_decks(deck, deck)
    p1 = state.players[1]
    p1.battlefield = []

    # One Forest land.
    land_id = p1.library.pop()
    p1.battlefield.append(land_id)
    land = state.cards[land_id]
    land.zone = Zone.BATTLEFIELD
    land.types = ["Land"]
    land.name = "Forest"
    land.type_line = "Basic Land — Forest"
    land.tapped = False

    # Llanowar Elves exists but is summoning sick, so can't tap for mana yet.
    elf_id = p1.library.pop()
    p1.battlefield.append(elf_id)
    elf = state.cards[elf_id]
    elf.zone = Zone.BATTLEFIELD
    elf.types = ["Creature"]
    elf.name = "Llanowar Elves"
    elf.oracle_text = "{T}: Add {G}."
    elf.tapped = False
    elf.summoning_sick = True

    assert can_pay_with_pool_and_lands(state, 1, "{1}{G}") is False


def test_noncreature_mana_source_can_pay_cost() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    p1 = state.players[1]
    p1.battlefield = []

    # One Island land.
    land_id = p1.library.pop()
    p1.battlefield.append(land_id)
    land = state.cards[land_id]
    land.zone = Zone.BATTLEFIELD
    land.types = ["Land"]
    land.name = "Island"
    land.type_line = "Basic Land — Island"
    land.tapped = False

    # One mana rock artifact.
    rock_id = p1.library.pop()
    p1.battlefield.append(rock_id)
    rock = state.cards[rock_id]
    rock.zone = Zone.BATTLEFIELD
    rock.types = ["Artifact"]
    rock.name = "Mind Stone"
    rock.oracle_text = "{T}: Add {C}."
    rock.tapped = False

    assert can_pay_with_pool_and_lands(state, 1, "{1}{U}") is True
    assert auto_pay_cost(state, 1, "{1}{U}") is True
    assert land.tapped is True
    assert rock.tapped is True


def test_nissa_style_static_ability_doubles_land_production_and_payment() -> None:
    deck = [{"quantity": 60, "card_name": "Forest"}]
    state = MatchFactory.from_decks(deck, deck)
    p1 = state.players[1]
    p1.battlefield = []
    land_id = p1.library.pop()
    planeswalker_id = p1.library.pop()
    p1.battlefield.extend([land_id, planeswalker_id])

    land = state.cards[land_id]
    land.zone = Zone.BATTLEFIELD
    land.types = ["Land"]
    land.name = "Forest"
    land.type_line = "Basic Land - Forest"
    land.tapped = False
    nissa = state.cards[planeswalker_id]
    nissa.zone = Zone.BATTLEFIELD
    nissa.types = ["Planeswalker"]
    nissa.name = "Nissa, Who Shakes the World"
    nissa.oracle_text = "Lands you control have '{T}: Add two mana of any one color.'"
    nissa.tapped = False

    assert land_mana_amount(state, 1, land_id) == 2
    assert can_pay_with_pool_and_lands(state, 1, "{G}{G}")
    assert auto_pay_cost(state, 1, "{G}{G}")
    assert land.tapped
