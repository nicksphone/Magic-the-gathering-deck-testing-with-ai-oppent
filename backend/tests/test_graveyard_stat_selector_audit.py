"""Canonical CDA queries, not Suspend or whole-card certification."""
import json
from pathlib import Path

import pytest

from game_state.state import MatchFactory, Zone
from game_state.serializers import (
    serialize_match_snapshot, deserialize_match_snapshot, serialize_card_view,
)
from rules_engine.continuous import (
    effective_combat_stats, _stat_resource_count, _graveyard_card_matches_selector,
)

FIX = Path(__file__).parent / 'fixtures'
ROWS = {
    name: json.loads((FIX / path).read_text())
    for name, path in {
        'Detritivore': 'graveyard_stat_selector/detritivore.json',
        'Terravore': 'graveyard_stat_selector/terravore.json',
        'Island': 'canonical_land_animation_audit/island.json',
        'Mutavault': 'canonical_land_animation_audit/mutavault.json',
        'Dryad Arbor': 'graveyard_permissions/dryad-arbor.json',
    }.items()
}


def add(state, name, owner, zone, controller=None):
    raw = ROWS[name]
    sample = MatchFactory.from_decks([{**raw, 'card_name': name, 'quantity': 1}], [], seed=31)
    card = next(iter(sample.cards.values()))
    card.id = state.allocate_object_id()
    card.owner = owner
    card.controller = owner if controller is None else controller
    card.move_to_zone(zone)
    state.cards[card.id] = card
    holder = card.controller if zone == Zone.BATTLEFIELD else owner
    getattr(state.players[holder], zone.value).append(card.id)
    return card


def setup(seat, family, zone=Zone.BATTLEFIELD, foreign=False):
    state = MatchFactory.from_decks([], [], seed=43)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    # Explicit controlled inventory fixture, not a simulated control-changing spell.
    card = add(state, family, seat, zone, 3-seat if foreign else seat)
    add(state, 'Island', seat, Zone.GRAVEYARD)
    add(state, 'Mutavault', seat, Zone.GRAVEYARD)
    add(state, 'Island', 3-seat, Zone.GRAVEYARD)
    add(state, 'Dryad Arbor', 3-seat, Zone.GRAVEYARD)
    add(state, 'Terravore', 3-seat, Zone.GRAVEYARD)
    return state, card


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family,expected', [('Detritivore', 1), ('Terravore', 4)])
@pytest.mark.parametrize('zone', [Zone.BATTLEFIELD, Zone.HAND, Zone.GRAVEYARD])
def test_printed_canonical_stats_public_snapshot_and_query_purity(seat, family, expected, zone):
    state, card = setup(seat, family, zone)
    before = serialize_match_snapshot(state)
    restored = deserialize_match_snapshot(before)
    observed = effective_combat_stats(state, card.id)
    replay = effective_combat_stats(restored, card.id)
    view = serialize_card_view(state, card.id)
    assert serialize_match_snapshot(state) == before
    assert serialize_match_snapshot(restored) == before
    assert observed == replay == (expected, expected)
    assert (view['power'], view['toughness']) == (expected, expected)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('zone', [Zone.BATTLEFIELD, Zone.HAND])
def test_opponent_count_uses_controller_on_battlefield_owner_elsewhere(seat, zone):
    state, card = setup(seat, 'Detritivore', zone, foreign=True)
    add(state, 'Mutavault', seat, Zone.GRAVEYARD)
    before = serialize_match_snapshot(state)
    expected = 2 if zone == Zone.BATTLEFIELD else 1
    actual = effective_combat_stats(state, card.id)
    assert serialize_match_snapshot(state) == before
    assert actual == (expected, expected)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,basic', [('Island', True), ('Mutavault', False), ('Dryad Arbor', False)])
def test_basic_is_supertype_not_land_subtype(seat, name, basic):
    state = MatchFactory.from_decks([], [], seed=9)
    card = add(state, name, seat, Zone.GRAVEYARD)
    before = serialize_match_snapshot(state)
    values = (_graveyard_card_matches_selector(card, 'basic land'),
              _graveyard_card_matches_selector(card, 'nonbasic land'))
    assert serialize_match_snapshot(state) == before
    assert values == (basic, not basic)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('domain,expected', [('your', 2), ("your opponents'", 2), ('all', 4)])
def test_existing_unqualified_land_domains_remain_supported(seat, domain, expected):
    state, card = setup(seat, 'Terravore')
    before = serialize_match_snapshot(state)
    actual = _stat_resource_count(state, card, f'land cards in {domain} graveyards')
    assert serialize_match_snapshot(state) == before
    assert actual == expected


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('selector', ['nonbasic artifact', 'unknown land', 'land nonsense', 'basic land nonsense'])
def test_unknown_selectors_do_not_count_or_mutate(seat, selector):
    state, card = setup(seat, 'Terravore')
    before = serialize_match_snapshot(state)
    actual = _stat_resource_count(state, card, f'{selector} cards in all graveyards')
    assert serialize_match_snapshot(state) == before
    assert actual == 0


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('qualifier', ['basic', 'nonbasic'])
@pytest.mark.parametrize('domain,expected', [('your', 1), ("your opponents'", 1), ('all', 2)])
def test_qualified_land_counts_respect_graveyard_domain(seat, qualifier, domain, expected):
    state, card = setup(seat, 'Terravore')
    before = serialize_match_snapshot(state)
    actual = _stat_resource_count(state, card, f'{qualifier} land cards in {domain} graveyards')
    assert serialize_match_snapshot(state) == before
    assert actual == expected
