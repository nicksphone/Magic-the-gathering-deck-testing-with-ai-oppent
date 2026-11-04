"""Canonical full printings in controlled pregame poses, not game replays."""
from collections import Counter
from copy import deepcopy
import random

import pytest

from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from game_state.state import MatchFactory, Zone
from rules_engine.engine import RulesEngine
from tests.browser_positive83_canonical import entry
from tests.opening_printed_canonical import raw_cards


def pose(seat, names, count, *, kind='mulligan_bottom', battlefield=()):
    counts = Counter([*names, *battlefield])
    counts['Plains'] += 60 - sum(counts.values())
    opening = raw_cards()
    deck = [({**opening[name], 'card_name': name, 'quantity': n}
             if name in opening else entry(name, n)) for name, n in counts.items()]
    state = MatchFactory.from_decks(deck, deck, seed=2026110411)
    player = state.players[seat]
    for cid in list(player.hand):
        player.hand.remove(cid); player.library.append(cid)
        state.cards[cid].move_to_zone(Zone.LIBRARY)
    for name in [*names, *battlefield]:
        cid = next(cid for cid in player.library if state.cards[cid].name == name)
        player.library.remove(cid)
        zone = Zone.HAND if len(player.hand) < len(names) else Zone.BATTLEFIELD
        state.cards[cid].move_to_zone(zone)
        getattr(player, zone.value).append(cid)
        if zone == Zone.BATTLEFIELD:
            state.cards[cid].counters['luck'] = 1
    state.active_player = state.priority_player = seat
    state.mulligan_count[seat] = count if kind == 'mulligan_bottom' else 0
    state.pending_mechanic_choice = dict(kind=kind, player_id=seat, options=list(player.hand),
        count=count, min_count=count, remaining_players=[], label='Controlled canonical opening pose')
    return state


def select(state, seat, *, style='Midrange', options=None):
    if options is not None:
        state.pending_mechanic_choice['options'] = list(options)
    before = serialize_match_snapshot(state)
    rng, local = random.getstate(), state.rng.getstate()
    moves = RulesEngine().legal_moves(deepcopy(state), seat)
    original_moves = deepcopy(moves)
    ai = AIAgent('master', style)
    first = ai.choose_action(state, moves, seat).action
    second = ai.choose_action(state, moves, seat).action
    assert first == second and first['type'] == 'choose_mechanic'
    chosen = first['card_ids']
    assert len(chosen) == state.pending_mechanic_choice['count']
    assert len(chosen) == len(set(chosen))
    assert set(chosen) <= set(state.pending_mechanic_choice['options'])
    assert before == serialize_match_snapshot(state) and moves == original_moves
    assert random.getstate() == rng and state.rng.getstate() == local
    return chosen


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('style', ['Aggro', 'Midrange', 'Control', 'Ramp'])
def test_five_lands_two_three_mana_bodies_keep_development(seat, style):
    state = pose(seat, ['Plains']*5 + ['Palace Guard', 'Adeline, Resplendent Cathar'], 2)
    ai = AIAgent('master', style)
    body = next(cid for cid in state.players[seat].hand if state.cards[cid].name == 'Palace Guard')
    land = next(cid for cid in state.players[seat].hand if state.cards[cid].name == 'Plains')
    # Global resource prices are deliberately unchanged, not a blanket land-price fix.
    assert ai._hand_retention_value(state, body, seat) == 3.4
    assert ai._hand_retention_value(state, land, seat) == 5.
    chosen = select(state, seat, style=style)
    assert all('Land' in state.cards[cid].types for cid in chosen)


@pytest.mark.parametrize('seat', [1, 2])
def test_land_light_hand_retains_both_known_sources(seat):
    state = pose(seat, ['Plains']*2 + ['Palace Guard']*3 + ['Adeline, Resplendent Cathar']*2, 2)
    chosen = select(state, seat)
    assert all('Land' not in state.cards[cid].types for cid in chosen)


@pytest.mark.parametrize('seat', [1, 2])
def test_retained_color_source_is_not_lost_to_independent_ties(seat):
    state = pose(seat, ['Plains'] + ['Swamp']*4 + ['Adeline, Resplendent Cathar']*2, 2)
    chosen = select(state, seat)
    assert all(state.cards[cid].name == 'Swamp' for cid in chosen)


@pytest.mark.parametrize('seat', [1, 2])
def test_opening_exile_counts_real_battlefield_land_resource(seat):
    names = ['Plains']*3 + ['Palace Guard', 'Adeline, Resplendent Cathar', 'Serra Angel']
    without = pose(seat, names, 1)
    assert state_names(without, select(without, seat)) == ['Serra Angel']
    state = pose(seat, names, 1, kind='opening_hand_exile', battlefield=['Gemstone Caverns'])
    caverns = state.cards[state.players[seat].battlefield[0]]
    assert AIAgent()._land_colors(caverns, state) == set('WUBRG')
    assert state_names(state, select(state, seat)) == ['Plains']


def state_names(state, ids):
    return [state.cards[cid].name for cid in ids]


@pytest.mark.parametrize('count', [0, 1, 2, 7])
def test_counts_and_ties_stay_stable_for_identical_cards(count):
    state = pose(1, ['Plains']*7, count)
    expected = sorted(state.players[1].hand)[:count]
    assert select(state, 1, options=list(reversed(state.players[1].hand))) == expected


def test_only_offered_cards_may_be_removed_not_all_hand_subsets():
    state = pose(1, ['Plains']*5 + ['Palace Guard', 'Adeline, Resplendent Cathar'], 2)
    offered = [cid for cid in state.players[1].hand if 'Creature' in state.cards[cid].types]
    assert set(select(state, 1, options=offered)) == set(offered)


def test_cleanup_discard_is_not_changed_to_opening_hand_selection():
    state = pose(1, ['Plains']*5 + ['Palace Guard', 'Adeline, Resplendent Cathar'], 2,
                 kind='cleanup_discard')
    state.pregame_pending = False
    assert all('Creature' in state.cards[cid].types for cid in select(state, 1))


def test_repeated_offered_ids_do_not_create_repeated_removals():
    state = pose(1, ['Plains']*5 + ['Palace Guard', 'Adeline, Resplendent Cathar'], 2)
    offered = list(state.players[1].hand)
    assert len(set(select(state, 1, options=offered + offered))) == 2


def test_nonstandard_wide_hand_retains_legacy_bounded_fallback():
    # Explicit width protocol, not a claimed legal seven-card opening.
    state = pose(1, ['Plains']*5 + ['Palace Guard']*2 + ['Adeline, Resplendent Cathar'], 2)
    ai = AIAgent('master', 'Midrange')
    offered = state.players[1].hand
    expected = sorted(offered, key=lambda cid: (ai._hand_retention_value(state, cid, 1), cid))[:2]
    before = serialize_match_snapshot(state)
    assert ai._choose_opening_hand_removals(state, offered, 2, 1) == expected
    assert serialize_match_snapshot(state) == before
