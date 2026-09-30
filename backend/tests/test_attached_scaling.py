"""Canonical scaling attachments use public state, not a flat inferred bonus."""
import json
from pathlib import Path

import pytest

from ai.heuristics import _creature_value
from game_state.state import Zone
from game_state.serializers import serialize_match, serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.continuous import effective_power, effective_toughness, effective_keywords, continuous_layer_trace
from tests.test_ai_recurring_engines import fixture, add as add_card

CARDS = {row['name']: row for row in json.loads(
    (Path(__file__).parent / 'fixtures' / 'attached_scaling.json').read_text())}


def add(state, name, player=1):
    return add_card(state, name, player, cards=CARDS)


@pytest.mark.parametrize('player', [1, 2])
@pytest.mark.parametrize('name,resources,delta,keywords', [
    ('All That Glitters', ['Sol Ring', 'Ornithopter', 'Unholy Strength'], (4, 4), set()),
    ('Nettlecyst', ['Sol Ring', 'Ornithopter', 'Unholy Strength'], (4, 4), set()),
    ('Ethereal Armor', ['Unholy Strength', 'Sol Ring'], (2, 2), {'first strike'}),
    ('Cranial Plating', ['Sol Ring', 'Ornithopter', 'Unholy Strength'], (3, 0), set()),
    ('Granite Grip', ['Mountain', 'Mountain', 'Swamp'], (2, 0), set()),
    ('Lashwrithe', ['Swamp', 'Swamp', 'Mountain'], (2, 2), set()),
    ('Glaive of the Guildpact', ['Azorius Guildgate', 'Azorius Guildgate', 'Swamp'], (2, 0), {'vigilance', 'menace'}),
    ('Vampirism', ['Llanowar Elves', 'Ornithopter'], (2, 2), set()),
])
def test_scaling_selectors_count_current_source_controller_and_restore(player, name, resources, delta, keywords):
    state = fixture()
    target = add(state, 'Llanowar Elves', 3 - player)
    attachment = add(state, name, player)
    attachment.attached_to = target.id
    for resource in resources:
        add(state, resource, player)
    # Opposing resources do not contribute, even though they control the target.
    for resource in resources:
        add(state, resource, 3 - player)
    before = serialize_match_snapshot(state)
    for candidate in (state, deserialize_match_snapshot(before)):
        assert effective_power(candidate, target.id) == 1 + delta[0]
        assert effective_toughness(candidate, target.id) == 1 + delta[1]
        assert keywords <= set(effective_keywords(candidate, target.id))
        view = next(card for card in serialize_match(candidate)['players'][3 - player]['battlefield'] if card['id'] == target.id)
        assert (view['power'], view['toughness']) == (1 + delta[0], 1 + delta[1])
        assert (view['base_power'], view['base_toughness']) == (1, 1)
        assert not continuous_layer_trace(candidate, target.id)['unsupported_attachment_clauses']
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('name,counters,expected', [
    ('Malefic Scythe', {'soul': 4, 'charge': 2, '__damage_marked': 8}, 4),
    ('Gavel of the Righteous', {'charge': 3, '+1/+1': 2, '__entered_turn': 5}, 5),
    ('Malefic Scythe', {'charge': 2}, 0),
])
def test_source_counter_scaling_excludes_other_counters_and_private_metadata(name, counters, expected):
    state = fixture()
    target = add(state, 'Llanowar Elves')
    source = add(state, name)
    source.attached_to = target.id
    source.counters.update(counters)
    assert effective_power(state, target.id) == 1 + expected
    assert effective_toughness(state, target.id) == 1 + expected


def test_resource_change_updates_combat_views_ai_and_layer_trace_without_mutation():
    state = fixture()
    target = add(state, 'Llanowar Elves')
    source = add(state, 'Cranial Plating')
    source.attached_to = target.id
    low = _creature_value(state, target.id)
    resource = add(state, 'Sol Ring')
    before = serialize_match_snapshot(state)
    assert effective_power(state, target.id) == 3
    assert _creature_value(state, target.id) > low
    assert any(row['layer'] == 'pt-mod:2/0' for row in continuous_layer_trace(state, target.id)['applied_layers'])
    assert serialize_match_snapshot(state) == before
    state.players[1].battlefield.remove(resource.id)
    resource.move_to_zone(Zone.GRAVEYARD)
    assert effective_power(state, target.id) == 2
    state.players[1].battlefield.remove(source.id)
    source.move_to_zone(Zone.GRAVEYARD)
    assert effective_power(state, target.id) == 1


@pytest.mark.parametrize('name', ['Ancestral Mask', 'Armament of Nyx'])
def test_unknown_scaling_or_condition_is_diagnosed_not_flat_or_unconditional(name):
    state = fixture()
    target = add(state, 'Llanowar Elves')
    source = add(state, name)
    source.attached_to = target.id
    assert (effective_power(state, target.id), effective_toughness(state, target.id)) == (1, 1)
    assert 'double strike' not in effective_keywords(state, target.id)
    assert continuous_layer_trace(state, target.id)['unsupported_attachment_clauses']
    source_view = next(card for card in serialize_match(state)['players'][1]['battlefield'] if card['id'] == source.id)
    assert source_view['effect_warnings']


def test_supported_conditional_keyword_does_not_erase_separate_fixed_bonus():
    state = fixture()
    target = add(state, 'Llanowar Elves')
    source = add(state, 'Abzan Runemark')
    source.attached_to = target.id
    assert (effective_power(state, target.id), effective_toughness(state, target.id)) == (3, 3)
    assert 'vigilance' in effective_keywords(state, target.id)
    assert not continuous_layer_trace(state, target.id)['unsupported_attachment_clauses']


@pytest.mark.parametrize('name,delta,keywords', [
    ('Bonesplitter', (2, 0), set()), ('Gryff\'s Boon', (1, 0), {'flying'}),
    ('Rancor', (2, 0), {'trample'}), ('Giant\'s Amulet', (0, 1), set()),
])
def test_fixed_clauses_still_apply_but_quoted_abilities_are_not_inferred(name, delta, keywords):
    state = fixture()
    target = add(state, 'Llanowar Elves')
    source = add(state, name)
    source.attached_to = target.id
    assert (effective_power(state, target.id), effective_toughness(state, target.id)) == (1 + delta[0], 1 + delta[1])
    assert keywords <= set(effective_keywords(state, target.id))
    assert 'hexproof' not in effective_keywords(state, target.id)


def test_multitype_permanent_counts_once_and_control_change_uses_new_source_controller():
    state = fixture()
    target = add(state, 'Llanowar Elves')
    source = add(state, 'All That Glitters')
    source.attached_to = target.id
    add(state, 'Whip of Erebos')
    assert effective_power(state, target.id) == 3  # Aura + one artifact/enchantment.
    state.players[1].battlefield.remove(source.id)
    state.players[2].battlefield.append(source.id)
    source.controller = 2
    assert effective_power(state, target.id) == 2


def test_other_creature_excludes_the_attached_target_not_the_aura():
    from rules_engine.continuous import _attached_scale_count
    state = fixture()
    target = add(state, 'Llanowar Elves')
    source = add(state, 'Vampirism')
    source.attached_to = target.id
    assert _attached_scale_count(state, source, target, 'other creature you control') == 0
    add(state, 'Ornithopter')
    assert _attached_scale_count(state, source, target, 'other creature you control') == 1
