"""Canonical 'can't enter' clauses apply before placement, not to stack spells."""
import pytest

from effects.registry import resolve_effect
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_graveyard_play_permissions import ROWS, add, position, moves
from tests.test_ai_recurring_engines import resolve


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('blocker', ["Grafdigger's Cage", 'Weathered Runestone'])
@pytest.mark.parametrize('name', ['Gravecrawler', 'Sol Ring', 'Forest', 'Dryad Arbor'])
@pytest.mark.parametrize('zone', [Zone.GRAVEYARD, Zone.LIBRARY])
def test_direct_placement_respects_source_zone_and_selector(seat, blocker, name, zone):
    state = position(seat)
    add(state, blocker, 3-seat, cards=ROWS)
    target = add(state, name, seat, zone, cards=ROWS)
    blocked = (name in {'Gravecrawler', 'Dryad Arbor'} if blocker == "Grafdigger's Cage"
               else name in {'Gravecrawler', 'Sol Ring'})
    if zone == Zone.GRAVEYARD:
        resolve_effect(state, seat, 'return_permanent_from_graveyard_to_battlefield', {'target_card_id': target.id})
    else:
        resolve_effect(state, seat, 'search_library', {'contains': 'card', 'destination': 'battlefield',
                       'selected_card_ids': [target.id], 'shuffle': False, 'count': 1})
    assert target.zone == (zone if blocked else Zone.BATTLEFIELD)
    assert (target.id in getattr(state.players[seat], zone.value)) == blocked
    assert (target.id in state.players[seat].battlefield) != blocked
    assert state.pending_replacement_choice is None and state.pending_mechanic_choice is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('effect', ['topdeck_put_creatures_battlefield', 'topdeck_put_permanents_battlefield'])
def test_blocked_library_creature_goes_to_rest_not_battlefield(seat, effect):
    state = position(seat)
    add(state, "Grafdigger's Cage", 3-seat, cards=ROWS)
    creature = add(state, 'Gravecrawler', seat, Zone.LIBRARY, cards=ROWS)
    resolve_effect(state, seat, effect, {'top_n': 1, 'selected_card_ids': [creature.id], 'bottom_random': False})
    assert creature.zone == Zone.LIBRARY
    assert creature.id in state.players[seat].library
    assert creature.id not in state.players[seat].battlefield


@pytest.mark.parametrize('seat', [1, 2])
def test_creature_return_block_does_not_emit_departure_or_charge_life(seat):
    state = position(seat)
    add(state, "Grafdigger's Cage", 3-seat, cards=ROWS)
    add(state, 'Tormod, the Desecrator', seat, cards=ROWS)
    creature = add(state, 'Gravecrawler', seat, Zone.GRAVEYARD, cards=ROWS)
    before = serialize_match_snapshot(state)
    resolve_effect(state, seat, 'return_creature_from_graveyard_to_battlefield',
                   {'target_card_id': creature.id, 'lose_life_equal_to_mana_value': True})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_creature_land_graveyard_play_block_but_normal_land_allowed(seat):
    state = position(seat)
    add(state, 'Crucible of Worlds', seat, cards=ROWS)
    add(state, "Grafdigger's Cage", 3-seat, cards=ROWS)
    creature_land = add(state, 'Dryad Arbor', seat, Zone.GRAVEYARD, cards=ROWS)
    normal = add(state, 'Forest', seat, Zone.GRAVEYARD, cards=ROWS)
    assert not moves(state, seat, creature_land.id)
    assert any(move['type'] == 'play_land' for move in moves(state, seat, normal.id))


@pytest.mark.parametrize('seat', [1, 2])
def test_graveyard_spell_already_on_stack_can_resolve_after_blocker_arrives(seat):
    state = position(seat)
    add(state, 'Diregraf Ghoul', seat, cards=ROWS)
    creature = add(state, 'Gravecrawler', seat, Zone.GRAVEYARD, cards=ROWS)
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': creature.id, 'from_graveyard': True})
    add(state, "Grafdigger's Cage", 3-seat, cards=ROWS)
    state = resolve(state)
    assert state.cards[creature.id].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('reveal', [True, False])
def test_blocked_split_search_does_not_shift_destinations_or_leak_hidden_names(seat, reveal):
    state = position(seat)
    add(state, "Grafdigger's Cage", 3-seat, cards=ROWS)
    first = add(state, 'Gravecrawler', seat, Zone.LIBRARY, cards=ROWS)
    second = add(state, 'Sol Ring', seat, Zone.LIBRARY, cards=ROWS)
    resolve_effect(state, seat, 'search_library', {'contains': 'card', 'destination': 'split_battlefield_hand',
                   'selected_card_ids': [first.id, second.id], 'count': 2, 'reveal': reveal, 'shuffle': False})
    assert first.zone == Zone.LIBRARY and first.id in state.players[seat].library
    assert second.zone == Zone.HAND and second.id in state.players[seat].hand
    assert (first.id in state.card_observations.get(3-seat, {})) == reveal


@pytest.mark.parametrize('seat', [1, 2])
def test_effect_cost_permission_does_not_override_cage(seat):
    from rules_engine.costs import collect_cost_options
    state = position(seat)
    add(state, "Grafdigger's Cage", 3-seat, cards=ROWS)
    card = add(state, 'Gravecrawler', seat, Zone.GRAVEYARD, cards=ROWS)
    add(state, 'Diregraf Ghoul', seat, cards=ROWS)
    assert collect_cost_options(state, seat, card, without_mana=True) == []
