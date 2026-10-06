"""Future resource retention must not relax actual mana-payment legality."""
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from ai.heuristics import _board_value, _creature_value, _noncreature_value, repeatable_mana_value
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.mana import nonland_mana_outputs, repeatable_nonland_mana_outputs
from tests.test_ai_recurring_engines import fixture, add as add_card


CARDS = {row["name"]: row for row in json.loads(
    (Path(__file__).parent / "fixtures" / "mana_resources.json").read_text())}


def add(state, name, player=1, zone=Zone.BATTLEFIELD):
    return add_card(state, name, player, zone, cards=CARDS)


@pytest.mark.parametrize("name,expected", [
    ("Llanowar Elves", {"G": 1}), ("Avacyn's Pilgrim", {"W": 1}),
    ("Boreal Druid", {"C": 1}), ("Palladium Myr", {"C": 2}),
    ("Birds of Paradise", {color: 1 for color in "WUBRG"}),
    ("Gilded Lotus", {color: 3 for color in "WUBRG"}), ("Sol Ring", {"C": 2}),
    ("Springleaf Drum", {}), ("Skirk Prospector", {}), ("Grizzly Bears", {}),
    ("Renowned Weaponsmith", {}), ("Basalt Monolith", {}),
])
def test_canonical_printed_capacity_is_shared_but_not_payment_permission(name, expected):
    state = fixture()
    source = add(state, name)
    before = serialize_match_snapshot(state)
    initial_sickness = source.summoning_sick
    assert repeatable_nonland_mana_outputs(source) == expected
    if expected:
        source.summoning_sick = False
        assert nonland_mana_outputs(state, source.id, source) == expected
        source.summoning_sick = "Creature" in source.types
        assert nonland_mana_outputs(state, source.id, source) == ({} if source.summoning_sick else expected)
    source.tapped = True
    # A source-free sacrifice activation is legal even while tapped or sick.
    # Repeatable capacity still excludes this consumable source below.
    assert nonland_mana_outputs(state, source.id, source) == ({'R': 1} if name == 'Skirk Prospector' else {})
    assert repeatable_nonland_mana_outputs(source) == expected
    source.tapped = False
    source.summoning_sick = initial_sickness
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize("style", ["Aggro", "Burn", "Control", "Tempo", "Midrange", "Ramp", "Drain", "Aristocrats", "Tokens", "Tribal"])
def test_public_resource_values_cross_styles_without_hidden_hand_dependence(style):
    state = fixture()
    elf = add(state, "Llanowar Elves", 2)
    bear = add(state, "Grizzly Bears", 2)
    agent = AIAgent(archetype=style)
    elf.summoning_sick = True
    before = serialize_match_snapshot(state)
    assert repeatable_mana_value(state, elf.id) == 2
    assert _creature_value(state, elf.id) > _creature_value(state, bear.id)
    assert agent._creature_threat_score(state, elf.id, 1) > agent._creature_threat_score(state, bear.id, 1)
    assert agent._sacrifice_loss(state, elf.id, 2) > agent._sacrifice_loss(state, bear.id, 2)
    assert serialize_match_snapshot(state) == before
    for _ in range(4):
        add(state, "Swamp", 2)
    assert repeatable_mana_value(state, elf.id) == .75
    assert _creature_value(state, elf.id) < _creature_value(state, bear.id)
    add(state, "Gilded Lotus", 2, Zone.HAND)
    assert repeatable_mana_value(state, elf.id) == .75


def test_cast_scoring_retains_future_resource_not_current_ready_mana():
    state = fixture()
    elf = add(state, "Llanowar Elves", zone=Zone.HAND)
    elf.summoning_sick = True
    agent = AIAgent(archetype="Ramp")
    move = {"type": "cast_spell", "card_id": elf.id}
    early = agent._cast_bias(state, move, 1)
    for _ in range(4):
        add(state, "Swamp")
    assert agent._cast_bias(state, move, 1) < early
    assert nonland_mana_outputs(state, elf.id, elf) == {}


def test_flexible_color_outputs_are_alternatives_not_five_resources():
    state = fixture()
    lotus = add(state, "Gilded Lotus")
    before = serialize_match_snapshot(state)
    assert repeatable_mana_value(state, lotus.id) == 6  # three mana, not fifteen
    assert _board_value(state, 1) == _noncreature_value(lotus) + 6
    lotus.tapped = True
    assert repeatable_mana_value(state, lotus.id) == 6
    lotus.tapped = False
    assert serialize_match_snapshot(state) == before
