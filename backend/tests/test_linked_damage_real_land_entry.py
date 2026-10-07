"""Paid responses establish land-entry history, never direct history assignment."""
import hashlib
from pathlib import Path

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_linked_damage_targets import position, raw_card
from tests.test_optional_land_instruction_compiler import ROWS


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('responding_player', ['caster', 'opponent'])
@pytest.mark.parametrize('select', [False, True])
def test_paid_spiral_response_selects_blaze_amount_from_actual_entry(
        seat, responding_player, select):
    fixture = Path(__file__).parent / 'fixtures/coupled_targets/searing-blaze.json'
    assert hashlib.sha256(fixture.read_bytes()).hexdigest() == (
        '5a01261e3874fc6aeeadba035652e3fa6c336daae59aefa560b07fab09d4b76a')
    state, blaze, creature, _, targets = position(seat)
    state.mechanic_choice_players = {1, 2}
    responder = seat if responding_player == 'caster' else 3-seat
    spiral = raw_card(state, ROWS['Growth Spiral'], responder, Zone.HAND)
    land_id = state.players[responder].library[-1]
    land = state.cards[land_id]
    assert 'Land' in land.types
    state.players[responder].library.remove(land_id)
    land.move_to_zone(Zone.HAND)
    state.players[responder].hand.append(land_id)
    state.players[responder].mana_pool.update({'G': 1, 'U': 1})
    assert not any(state.land_entries_this_turn.values())
    engine = RulesEngine()
    state = checked_action(state, engine, seat, {
        'type': 'cast_spell', 'card_id': blaze.id, 'targets': targets})
    if responder != seat:
        state = checked_action(state, engine, seat, {'type': 'pass_priority'})
    state = checked_action(state, engine, responder, {
        'type': 'cast_spell', 'card_id': spiral.id})
    assert state.players[responder].mana_pool['G'] == 0
    assert state.players[responder].mana_pool['U'] == 0
    assert state.stack[-1].source_card_id == spiral.id
    assert not resolve_top_of_stack(state), 'Resolution must pause for a private land choice'
    assert state.pending_mechanic_choice['kind'] == 'land_from_hand'
    assert state.pending_mechanic_choice['player_id'] == responder
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    before = serialize_match_snapshot(state)
    state = checked_action(state, engine, responder, {
        'type': 'choose_mechanic', 'card_ids': [land_id] if select else []})
    assert before['pending_mechanic_choice'] is not None
    assert state.pending_mechanic_choice is None
    assert state.cards[land_id].zone == (Zone.BATTLEFIELD if select else Zone.HAND)
    assert state.land_entries_this_turn.get(responder, 0) == int(select)
    assert state.players[responder].lands_played_this_turn == 0
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    life = state.players[3-seat].life
    assert state.stack[-1].source_card_id == blaze.id
    assert resolve_top_of_stack(state)
    amount = 3 if select and responder == seat else 1
    assert state.players[3-seat].life == life-amount
    assert state.cards[creature.id].counters.get('__damage_marked', 0) == amount
    assert state.cards[blaze.id].zone == Zone.GRAVEYARD
    assert state.cards[spiral.id].zone == Zone.GRAVEYARD
