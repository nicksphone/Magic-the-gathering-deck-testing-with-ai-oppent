"""Canonical continuous subjects and ability-window boundaries."""
import json
from pathlib import Path

from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot, serialize_card_view
from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.cast_choice import build_cast_hints
from rules_engine.continuous import effective_keywords, effective_power, effective_toughness, continuous_layer_trace
from rules_engine.engine import RulesEngine
from tests.test_ai_recurring_engines import fixture, add as add_card, resolve


CARDS = {row["name"]: row for row in json.loads(
    (Path(__file__).parent / "fixtures" / "qualified_continuous.json").read_text())}


def add(state, name, player=1, zone=Zone.BATTLEFIELD):
    return add_card(state, name, player, zone, cards=CARDS)


def test_nontoken_and_token_buffs_do_not_cross_subjects_and_survive_snapshot():
    state = fixture()
    bear = add(state, "Grizzly Bears")
    opponent = add(state, "Grizzly Bears", 2)
    add(state, "Always Watching")
    spell = add(state, "Raise the Alarm", zone=Zone.HAND)
    state.players[1].mana_pool["W"] = 1
    state = resolve(checked_action(state, RulesEngine(), 1, {"type": "cast_spell", "card_id": spell.id, "targets": {}}))
    tokens = [cid for cid in state.players[1].battlefield if state.cards[cid].is_token]
    assert len(tokens) == 2
    assert (effective_power(state, bear.id), effective_toughness(state, bear.id)) == (3, 3)
    assert "vigilance" in effective_keywords(state, bear.id)
    assert effective_power(state, opponent.id) == 2
    for cid in tokens:
        assert effective_power(state, cid) == 1
        assert "vigilance" not in effective_keywords(state, cid)
    add(state, "Intangible Virtue")
    before = serialize_match_snapshot(state)
    clone = deserialize_match_snapshot(before)
    for candidate in (state, clone):
        assert effective_power(candidate, bear.id) == 3
        for cid in tokens:
            assert effective_power(candidate, cid) == 2
            assert "vigilance" in effective_keywords(candidate, cid)
        assert candidate.cards[bear.id].power == 2
        assert serialize_card_view(candidate, bear.id)["power"] == 3
    assert serialize_match_snapshot(state) == before


def test_negative_color_subject_and_other_scope_are_not_tribal_names():
    state = fixture()
    angel = add(state, "Angel of Jubilation")
    bear = add(state, "Grizzly Bears")
    artist = add(state, "Blood Artist")
    opponent = add(state, "Grizzly Bears", 2)
    assert effective_power(state, angel.id) == angel.power
    assert effective_power(state, bear.id) == 3
    assert effective_power(state, artist.id) == 0
    assert effective_power(state, opponent.id) == 2


def test_multiple_color_clauses_stack_on_a_real_multicolor_creature():
    state = fixture()
    liege = add(state, "Creakwood Liege")
    second = add(state, "Creakwood Liege")
    elf = add(state, "Llanowar Elves")
    artist = add(state, "Blood Artist")
    colorless = add(state, "Palladium Myr")
    assert effective_power(state, liege.id) == 4
    assert effective_power(state, second.id) == 4
    assert effective_power(state, elf.id) == 3
    assert effective_power(state, artist.id) == 2
    assert effective_power(state, colorless.id) == 2


def test_artifact_keyword_grants_reach_noncreatures_and_removal_checks():
    state = fixture()
    forge = add(state, "Darksteel Forge")
    spear = add(state, "Shadowspear")
    myr = add(state, "Palladium Myr")
    forest = add(state, "Forest")
    assert "indestructible" in effective_keywords(state, forge.id)
    assert "indestructible" in effective_keywords(state, spear.id)
    assert "indestructible" in effective_keywords(state, myr.id)
    assert "indestructible" not in effective_keywords(state, forest.id)
    assert "indestructible" in serialize_card_view(state, spear.id)["keywords"]
    state.active_player = state.priority_player = 2
    spell = add(state, "Naturalize", 2, Zone.HAND)
    state = resolve(checked_action(state, RulesEngine(), 2, {"type": "cast_spell", "card_id": spell.id,
                                                           "targets": {"target_card_id": spear.id}}))
    assert state.cards[spear.id].zone == Zone.BATTLEFIELD
    state.players[1].battlefield.remove(forge.id)
    state.cards[forge.id].move_to_zone(Zone.GRAVEYARD)
    state.players[1].graveyard.append(forge.id)
    assert "indestructible" not in effective_keywords(state, spear.id)


def test_other_permanents_protection_reaches_lands_and_enchantments_not_its_source():
    state = fixture()
    position = add(state, "Privileged Position")
    watching = add(state, "Always Watching")
    forest = add(state, "Forest")
    spell = add(state, "Naturalize", 2, Zone.HAND)
    assert "hexproof" not in effective_keywords(state, position.id)
    for cid in (watching.id, forest.id):
        assert "hexproof" in effective_keywords(state, cid)
    hints = build_cast_hints(state, spell, 2)
    ids = {target["id"] for key, targets in hints.items() if key.endswith("_targets") and isinstance(targets, list)
           for target in targets if isinstance(target, dict) and "id" in target}
    assert position.id in ids and watching.id not in ids


def test_unactivated_animation_and_keyword_removal_are_not_static_effects():
    state = fixture()
    champion = add(state, "Steel Leaf Champion")
    add(state, "Mutavault")
    add(state, "Avacyn, Angel of Hope")
    forest = add(state, "Forest")
    add(state, "Shadowspear", 2)
    before = serialize_match_snapshot(state)
    assert (effective_power(state, champion.id), effective_toughness(state, champion.id)) == (5, 4)
    assert "indestructible" in effective_keywords(state, forest.id)
    assert "indestructible" in effective_keywords(state, champion.id)
    continuous_layer_trace(state, forest.id)
    assert serialize_match_snapshot(state) == before
