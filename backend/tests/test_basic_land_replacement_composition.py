"""Replacement ordering using existing canonical fixtures and real effect paths."""
import pytest

from effects.registry import resolve_effect
from game_state.serializers import deserialize_match_snapshot, serialize_card_view, serialize_match_snapshot
from rules_engine.basic_land_layer import layer_four_view, permanent_land_replacement
from rules_engine.continuous import effective_combat_stats, has_keyword, continuous_layer_trace
from rules_engine.land_types import effective_type_line
from rules_engine.mana import mana_source_outputs
from rules_engine.query_context import rule_query_scope
from rules_engine.type_effects import effective_types
from tests.test_basic_land_layer_goldens import add, position, setter, CARDS
from tests.test_type_effect_lifecycle import animate


def test_complete_generic_instruction_not_card_name_or_substring():
    assert permanent_land_replacement(CARDS['Song of the Dryads']['oracle_text']) == 'Forest'
    for text in ['Enchanted permanent is a colorless Island land.',
                 'Enchanted permanent is a colorless Mountain land.']:
        assert permanent_land_replacement(text)
    for text in ['If you control a Forest, enchanted permanent is a colorless Forest land.',
                 'Enchanted permanent is a colorless Forest land in addition to its other types.',
                 'Enchanted creature is a colorless Forest land.',
                 'Enchanted permanent is a colorless Forest land and has flying.']:
        assert permanent_land_replacement(text) is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('moon_first', [False, True])
def test_replacement_changes_global_land_targets_dependency_not_timestamp(seat, moon_first):
    state = position(seat)
    target = add(state, 'Royal Assassin', seat)
    if moon_first:
        add(state, 'Blood Moon', 3-seat)
    setter(state, 'Song of the Dryads', 3-seat, target)
    if not moon_first:
        add(state, 'Blood Moon', 3-seat)
    assert effective_type_line(state, target) == 'Land \u2014 Mountain'
    assert mana_source_outputs(state, seat, target.id) == {'R': 1}
    assert serialize_card_view(state, target.id)['colors'] == []


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('song_first', [False, True])
def test_real_nissa_animation_competes_with_replacement_not_source_life(seat, song_first):
    state = position(seat)
    land = add(state, 'Forest', seat)
    if song_first:
        setter(state, 'Song of the Dryads', 3-seat, land)
    nissa = animate(state, land, seat)
    if not song_first:
        setter(state, 'Song of the Dryads', 3-seat, land)
    assert ('Creature' in effective_types(state, land)) == song_first
    assert ('Elemental' in effective_type_line(state, land)) == song_first
    assert effective_type_line(state, land).startswith('Basic Land')
    assert has_keyword(state, land.id, 'haste') and has_keyword(state, land.id, 'vigilance')
    resolve_effect(state, seat, 'destroy_permanent', {'target_card_id': nissa.id})
    assert ('Creature' in effective_types(state, land)) == song_first
    before = serialize_match_snapshot(state)
    with rule_query_scope(state):
        expected = serialize_card_view(state, land.id)
        assert serialize_card_view(state, land.id) == expected
    restored = deserialize_match_snapshot(before)
    assert serialize_card_view(restored, land.id) == expected
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_removed_earlier_loss_source_does_not_continue_into_keywords_or_base_stats(seat):
    state = position(seat)
    elf = add(state, 'Llanowar Elves', seat)
    humility = add(state, 'Humility', 3-seat)
    assert effective_combat_stats(state, elf.id) == (1, 1)
    setter(state, 'Song of the Dryads', seat, humility)
    assert not any(row.get('source_id') == humility.id for row in
                   continuous_layer_trace(state, elf.id)['applied_layers'])
    assert mana_source_outputs(state, seat, elf.id) == {'G': 1}


@pytest.mark.parametrize('seat', [1, 2])
def test_source_departure_restores_printed_characteristics_next_query(seat):
    state = position(seat)
    target = add(state, 'Royal Assassin', seat)
    song = setter(state, 'Song of the Dryads', 3-seat, target)
    with rule_query_scope(state):
        assert serialize_card_view(state, target.id)['colors'] == []
        assert effective_types(state, target) == ['Land']
    resolve_effect(state, seat, 'destroy_permanent', {'target_card_id': song.id})
    with rule_query_scope(state):
        view = serialize_card_view(state, target.id)
        assert view['colors'] == ['B'] and view['types'] == ['Creature']
        assert target.oracle_text == CARDS[target.name]['oracle_text']
        assert target.colors == CARDS[target.name]['colors']


@pytest.mark.parametrize('seat', [1, 2])
def test_query_results_cannot_mutate_shared_characteristic_maps(seat):
    state = position(seat)
    target = add(state, 'Royal Assassin', seat)
    setter(state, 'Song of the Dryads', 3-seat, target)
    before = serialize_match_snapshot(state)
    with rule_query_scope(state):
        view = layer_four_view(state)
        for index in [0, 2]:
            with pytest.raises(TypeError):
                view[index][target.id] = 'polluted'
        returned = effective_types(state, target)
        returned.append('Creature')
        assert effective_types(state, target) == ['Land']
    assert serialize_match_snapshot(state) == before
