"""Canonical stat controls plus explicitly non-card selector ABI probes."""
from types import SimpleNamespace

import pytest

from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.continuous import effective_combat_stats, _graveyard_card_matches_selector, _stat_resource_count
from rules_engine.counter_placement import put_counters
from tests.test_graveyard_stat_selector_audit import setup, add


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family,base', [('Detritivore', 1), ('Terravore', 4)])
def test_native_counter_layer_preserves_printed_cda_and_snapshot(seat, family, base):
    state, card = setup(seat, family)
    assert put_counters(state, '+1/+1', 2, target_card_id=card.id) == 2
    before = serialize_match_snapshot(state)
    assert effective_combat_stats(state, card.id) == (base + 2, base + 2)
    replay = deserialize_match_snapshot(before)
    assert effective_combat_stats(replay, card.id) == (base + 2, base + 2)
    assert serialize_match_snapshot(state) == serialize_match_snapshot(replay) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('qualifier', ['basic', 'nonbasic'])
@pytest.mark.parametrize('domain,expected', [('your', 1), ("your opponents'", 1), ('all', 2)])
def test_plural_qualified_selectors_keep_owner_domains(seat, qualifier, domain, expected):
    state, card = setup(seat, 'Terravore')
    before = serialize_match_snapshot(state)
    assert _stat_resource_count(state, card, f'{qualifier} lands cards in {domain} graveyards') == expected
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family,expected', [('Detritivore', 1), ('Terravore', 4)])
def test_printed_graveyard_counts_ignore_unrelated_battlefield_inventory(seat, family, expected):
    state, card = setup(seat, family)
    add(state, 'Island', seat, Zone.BATTLEFIELD)
    add(state, 'Dryad Arbor', 3-seat, Zone.BATTLEFIELD)
    before = serialize_match_snapshot(state)
    assert effective_combat_stats(state, card.id) == (expected, expected)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('types,line,expected', [
    (['Land'], 'Basic Land', True),
    (['Land'], 'Basic Snow Land - Island', True),
    (['Land'], 'Land - Basic', False),
    (['Land'], 'Land - Forest', False),
    (['Land'], 'Land // Basic Land - Forest', False),
    (['Creature'], 'Basic Creature - Land', None),
    ([], 'Basic Land', None),
    (['Land'], 'Land - Basicland', False),
])
def test_selector_protocol_exact_supertype_boundary(types, line, expected):
    # Structural ABI probes, never canonical game cards or Oracle fixtures.
    value = SimpleNamespace(types=types, type_line=line)
    assert _graveyard_card_matches_selector(value, 'basic land') == (expected is True)
    assert _graveyard_card_matches_selector(value, 'nonbasic lands') == (expected is False)


@pytest.mark.parametrize('selector', ['nonbasic land trailing', 'basic lands extra', 'non basic land', 'basic artifact'])
def test_selector_protocol_unknown_suffix_remains_false(selector):
    value = SimpleNamespace(types=['Land'], type_line='Basic Land - Island')
    assert not _graveyard_card_matches_selector(value, selector)


@pytest.mark.parametrize('selector,expected', [('land', True), ('lands', True), ('card', True), ('creature', False)])
def test_existing_selector_protocol_type_behavior_unchanged(selector, expected):
    value = SimpleNamespace(types=['Land'], type_line='Land - Forest')
    assert _graveyard_card_matches_selector(value, selector) == expected
