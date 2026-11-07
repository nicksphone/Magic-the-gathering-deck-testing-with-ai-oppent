"""Canonical landfall sequencing regressions, not training or model labels."""
from copy import deepcopy

import pytest

from ai.agent import AIAgent
from card_data.sync import ScryfallSyncService
from game_state.serializers import serialize_match_snapshot
from game_state.state import Step, Zone
from rules_engine.engine import RulesEngine
from tests.test_ai_search_prefix import bare_state
from tests.test_any_player_cast_damage import checked, settle
from tests.test_burn_core_native_outcomes import RAW
from tests.test_linked_damage_targets import raw_card


def add(state, name, seat, zone=Zone.HAND):
    raw = RAW[name]
    image = ScryfallSyncService._extract_remote_image_uri(raw)
    row = {**deepcopy(raw), **ScryfallSyncService._normalize_payload(raw, image),
           'colors': deepcopy(raw['colors']), 'card_faces': deepcopy(raw.get('card_faces', []))}
    card = raw_card(state, row, seat, zone)
    assert card.oracle_text == raw['oracle_text'] and card.mana_cost == raw['mana_cost']
    return card.id


def position(seat):
    state = bare_state(seat)
    state.turn = 9
    state.step = Step.UPKEEP
    state.players[3-seat].life = 16
    spell = add(state, 'Searing Blaze', seat)
    lands = [add(state, 'Plains', seat) for _ in range(2)]
    for _ in range(4):
        add(state, 'Mountain', seat, Zone.BATTLEFIELD)
        enemy_land = add(state, 'Island', 3-seat, Zone.BATTLEFIELD)
        state.cards[enemy_land].tapped = True
    raven = add(state, 'Augury Raven', 3-seat, Zone.BATTLEFIELD)
    state.cards[raven].summoning_sick = False
    return state, spell, lands, raven


def choose(state, seat):
    before = serialize_match_snapshot(state)
    moves = RulesEngine().legal_moves(deepcopy(state), seat)
    saved = deepcopy(moves)
    agent = AIAgent(difficulty='master', archetype='Burn', opponent_archetype='Control')
    decision = agent.choose_action(state, moves, seat)
    print('DECISION', seat, state.step, decision.action, decision.reasoning, flush=True)
    assert serialize_match_snapshot(state) == before and moves == saved
    return decision.action


@pytest.mark.parametrize('seat', [1, 2])
def test_known_land_precedes_nonlethal_landfall_burn(seat):
    state, spell, lands, raven = position(seat)
    moves = RulesEngine().legal_moves(deepcopy(state), seat)
    assert any(move.get('card_id') == spell and move['type'] == 'cast_spell' for move in moves)
    assert not any(move['type'] == 'play_land' for move in moves)
    action = choose(state, seat)
    assert action == {'type': 'pass_priority'}
    # Advance native priority/steps, without predicting the unseen draw.
    for _ in range(8):
        if state.step == Step.PRECOMBAT_MAIN:
            break
        state = checked(state, state.priority_player, {'type': 'pass_priority'})
    assert state.step == Step.PRECOMBAT_MAIN
    action = choose(state, seat)
    assert action['type'] == 'play_land'
    assert action['card_id'] in lands
    state = checked(state, seat, action)
    assert state.land_entries_this_turn[seat] == 1
    action = choose(state, seat)
    assert action['type'] == 'cast_spell' and action['card_id'] == spell
    state = settle(checked(state, seat, action))
    assert state.cards[spell].zone == Zone.GRAVEYARD
    assert state.cards[raven].zone == Zone.GRAVEYARD
    assert state.players[3-seat].life == 13


@pytest.mark.parametrize('seat', [1, 2])
def test_immediate_one_damage_lethal_is_not_deferred(seat):
    state, spell, _, _ = position(seat)
    state.players[3-seat].life = 1
    action = choose(state, seat)
    assert action['type'] == 'cast_spell' and action['card_id'] == spell
    state = settle(checked(state, seat, action))
    assert state.winner == seat


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('boundary', ['no_known_land', 'opponent_turn', 'landfall_active',
                                     'land_drop_used', 'floating_mana_only', 'stack_response'])
def test_burn_without_a_safe_land_first_window_still_casts(seat, boundary):
    state, spell, lands, raven = position(seat)
    if boundary == 'no_known_land':
        for cid in lands:
            state.players[seat].hand.remove(cid)
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            state.players[seat].library.append(cid)
    elif boundary == 'opponent_turn':
        state.active_player = 3-seat
    elif boundary == 'landfall_active':
        state.step = Step.PRECOMBAT_MAIN
        state = checked(state, seat, {'type': 'play_land', 'card_id': lands[0]})
        state.step = Step.UPKEEP
    elif boundary == 'land_drop_used':
        player = state.players[seat]
        player.last_land_play_turn = state.turn
        player.lands_played_this_turn = player.land_plays_recorded_on_turn = 1
    elif boundary == 'floating_mana_only':
        for cid in state.players[seat].battlefield:
            state.cards[cid].tapped = True
        state.players[seat].mana_pool = {'R': 2}
    elif boundary == 'stack_response':
        bolt = add(state, 'Lightning Bolt', 3-seat)
        add(state, 'Mountain', 3-seat, Zone.BATTLEFIELD)
        state.priority_player = 3-seat
        state = checked(state, 3-seat, {'type': 'cast_spell', 'card_id': bolt,
                                       'targets': {'target_player': seat}})
        state = checked(state, 3-seat, {'type': 'pass_priority'})
        assert state.stack and state.priority_player == seat
    action = choose(state, seat)
    assert action['type'] == 'cast_spell' and action['card_id'] == spell
    state = settle(checked(state, seat, action))
    assert state.cards[spell].zone == Zone.GRAVEYARD
    assert state.players[3-seat].life == (13 if boundary == 'landfall_active' else 15)
