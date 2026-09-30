"""Real held costs, not creature names, determine mana/attack opportunity."""
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from game_state.state import Step, Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.mana import mana_source_outputs
from tests.test_ai_recurring_engines import fixture, add as add_card, resolve


CARDS = {row["name"]: row for row in json.loads(
    (Path(__file__).parent / "fixtures" / "postcombat_mana.json").read_text())}


def add(state, name, player=1, zone=Zone.BATTLEFIELD):
    card = add_card(state, name, player, zone, cards=CARDS)
    card.summoning_sick = False
    return card


def board(source_name="Llanowar Elves", spell_name="Steel Leaf Champion", lands=("Forest", "Forest"), *, player=1):
    state = fixture()
    state.turn = 3
    state.step = Step.DECLARE_ATTACKERS
    state.active_player = state.priority_player = player
    for seat in state.players.values():
        seat.mana_pool.clear()
    for name in lands:
        add(state, name, player)
    source = add(state, source_name, player)
    spell = add(state, spell_name, player, Zone.HAND)
    return state, source, spell


@pytest.mark.parametrize("style", ["Aggro", "Burn", "Control", "Tempo", "Midrange", "Ramp", "Drain", "Aristocrats", "Tokens", "Tribal"])
@pytest.mark.parametrize("player", [1, 2])
def test_all_styles_reserve_one_damage_for_known_three_green_cast_and_resume(style, player):
    state, source, spell = board(player=player)
    before = serialize_match_snapshot(state)
    agent = AIAgent(difficulty="master", archetype=style)
    assert agent._choose_attackers(state, [source.id], player) == []
    restored = deserialize_match_snapshot(before)
    assert agent._choose_attackers(restored, [source.id], player) == []
    assert serialize_match_snapshot(state) == before
    assert serialize_match_snapshot(restored) == before
    state = checked_action(state, RulesEngine(), player, {"type": "attack", "attackers": []})
    for _ in range(20):
        if state.step == Step.POSTCOMBAT_MAIN:
            break
        state = checked_action(state, RulesEngine(), state.priority_player, {"type": "pass_priority"})
    assert state.step == Step.POSTCOMBAT_MAIN and not state.cards[source.id].tapped
    action = agent.choose_action(state, RulesEngine().legal_moves(state, player), player).action
    assert action["type"] == "cast_spell" and action["card_id"] == spell.id
    state = resolve(checked_action(state, RulesEngine(), player, action))
    assert state.cards[spell.id].zone == Zone.BATTLEFIELD
    assert state.cards[source.id].tapped


@pytest.mark.parametrize("source,spell,lands", [
    ("Avacyn's Pilgrim", "Benalish Marshal", ("Plains", "Plains")),
    ("Palladium Myr", "Wurmcoil Engine", ("Swamp",) * 4),
    ("Dryad Arbor", "Steel Leaf Champion", ("Forest", "Forest")),
])
def test_other_colors_multiple_mana_and_land_creatures_use_real_payment(source, spell, lands):
    state, card, _ = board(source, spell, lands)
    before = serialize_match_snapshot(state)
    assert mana_source_outputs(state, 1, card.id)
    assert AIAgent()._choose_attackers(state, [card.id], 1) == []
    assert serialize_match_snapshot(state) == before


def test_redundant_sources_attack_but_only_required_source_is_reserved():
    state, first, _ = board()
    second = add(state, "Llanowar Elves")
    before = serialize_match_snapshot(state)
    chosen = AIAgent()._choose_attackers(state, [first.id, second.id], 1)
    assert len(chosen) == 1
    assert serialize_match_snapshot(state) == before
    add(state, "Forest")
    assert AIAgent()._choose_attackers(state, [first.id, second.id], 1) == [first.id, second.id]


def test_wrong_color_and_cheap_alternative_do_not_create_false_dependence():
    state, source, spell = board(spell_name="Torrential Gearhulk")
    agent = AIAgent()
    assert agent._choose_attackers(state, [source.id], 1) == [source.id]
    spell.move_to_zone(Zone.GRAVEYARD)
    state.players[1].hand.remove(spell.id)
    state.players[1].graveyard.append(spell.id)
    add(state, "Grizzly Bears", zone=Zone.HAND)
    assert agent._choose_attackers(state, [source.id], 1) == [source.id]


def test_floating_mana_does_not_survive_to_postcombat_but_lethal_pressure_wins():
    state, source, _ = board()
    state.players[1].mana_pool["G"] = 10
    before = serialize_match_snapshot(state)
    agent = AIAgent()
    assert agent._choose_attackers(state, [source.id], 1) == []
    assert serialize_match_snapshot(state) == before
    state.players[2].life = 1
    assert agent._choose_attackers(state, [source.id], 1) == [source.id]


def test_forced_late_progress_does_not_undo_resource_reservation():
    state, source, _ = board()
    state.turn = 25
    assert AIAgent()._forced_progress_attack(state, RulesEngine().legal_moves(state, 1), 1) is None


def test_unknown_opposing_hand_does_not_change_resource_reservation():
    state, source, _ = board()
    agent = AIAgent()
    before = agent._choose_attackers(state, [source.id], 1)
    add(state, "Lightning Bolt", 2, Zone.HAND)
    assert agent._choose_attackers(state, [source.id], 1) == before


def test_inactive_or_pending_stack_does_not_run_postcombat_forecast():
    state, source, _ = board()
    state.active_player = 2
    assert AIAgent()._reserve_postcombat_mana(state, [source.id], 1) == [source.id]
    state.active_player = 1
    bolt = add(state, "Lightning Bolt", zone=Zone.HAND)
    state.players[1].mana_pool["R"] = 1
    state = checked_action(state, RulesEngine(), 1,
                           {"type": "cast_spell", "card_id": bolt.id, "targets": {"target_player": 2}})
    assert state.stack
    assert AIAgent()._reserve_postcombat_mana(state, [source.id], 1) == [source.id]


def test_flexible_sources_do_not_double_count_colors_for_double_blue():
    state, first, _ = board("Birds of Paradise", "Torrential Gearhulk", ("Forest",) * 4)
    second = add(state, "Birds of Paradise")
    agent = AIAgent()
    assert agent._choose_attackers(state, [first.id, second.id], 1) == []
    third = add(state, "Birds of Paradise")
    assert len(agent._choose_attackers(state, [first.id, second.id, third.id], 1)) == 1


def test_required_colorless_is_not_generic_and_colored_sources_cannot_replace_it():
    state, source, _ = board("Boreal Druid", "Thought-Knot Seer", ("Forest",) * 3)
    assert AIAgent()._choose_attackers(state, [source.id], 1) == []
    other, elf, _ = board("Llanowar Elves", "Thought-Knot Seer", ("Forest",) * 3)
    assert AIAgent()._choose_attackers(other, [elf.id], 1) == [elf.id]


def test_spell_tax_creates_real_postcombat_dependency_for_ramp_spell():
    state, source, _ = board(spell_name="Cultivate", lands=("Forest",) * 3)
    agent = AIAgent(archetype="Ramp")
    assert agent._choose_attackers(state, [source.id], 1) == [source.id]
    tax = add(state, "Thalia, Guardian of Thraben", 2)
    tax.tapped = True
    before = serialize_match_snapshot(state)
    assert agent._choose_attackers(state, [source.id], 1) == []
    assert serialize_match_snapshot(state) == before


def test_actual_vigilance_grant_keeps_attack_and_ready_mana():
    state, source, _ = board()
    add(state, "Always Watching")
    assert AIAgent()._choose_attackers(state, [source.id], 1) == [source.id]
    state = checked_action(state, RulesEngine(), 1, {"type": "attack", "attackers": [source.id]})
    assert not state.cards[source.id].tapped
    assert mana_source_outputs(state, 1, source.id) == {"G": 1}


def test_direct_burn_opportunity_can_be_worth_more_than_one_damage():
    state, source, _ = board("Iron Myr", "Lightning Bolt", ())
    assert AIAgent(archetype="Burn")._choose_attackers(state, [source.id], 1) == []
