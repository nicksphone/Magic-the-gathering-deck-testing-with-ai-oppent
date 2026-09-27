"""Targeted ETB choices are made for abilities, not announced on creature casts."""
import pytest

from tests.test_permanent_spell_context import state, card, cast
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import validate_action, ActionRejected
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack


def setup_targeted_sage(*, seat=1, with_warden=False):
    game = state()
    game.trigger_order_choice_required = True
    game.trigger_order_choice_players = {seat}
    game.players[seat].mana_pool.update({color: 20 for color in 'WUBRGC'})
    if seat == 2:
        game.priority_player = 2
        game.active_player = 2
    ring = card(game, 'Sol Ring', Zone.BATTLEFIELD, owner=seat)
    copter = card(game, "Smuggler's Copter", Zone.BATTLEFIELD, owner=3 - seat)
    if with_warden:
        card(game, 'Soul Warden', Zone.BATTLEFIELD, owner=seat)
    sage = card(game, 'Reclamation Sage', owner=seat)
    rules = RulesEngine()
    action = {'type': 'cast_spell', 'card_id': sage.id}
    validate_action(game, rules, seat, action)
    rules.take_action(game, seat, action, reject_invalid=True)
    assert game.stack[-1].source_card_id == sage.id
    assert ring.zone == copter.zone == Zone.BATTLEFIELD
    resolve_top_of_stack(game)
    return game, rules, sage, ring, copter


def test_etb_target_is_selected_after_permanent_resolves_and_is_snapshot_safe():
    game, rules, sage, ring, copter = setup_targeted_sage()
    assert sage.zone == Zone.BATTLEFIELD
    assert game.pending_trigger_order['phase'] == 'targets'
    moves = rules.legal_moves(game, 1)
    assert {move.get('target_card_id') for move in moves} == {ring.id, copter.id}
    assert not rules.legal_moves(game, 2)
    game = deserialize_match_snapshot(serialize_match_snapshot(game))
    choice = next(move for move in rules.legal_moves(game, 1) if move.get('target_card_id') == ring.id)
    action = {'type': 'choose_trigger_target', 'stack_id': choice['stack_id'], 'target_card_id': ring.id}
    validate_action(game, rules, 1, action)
    rules.take_action(game, 1, action, reject_invalid=True)
    assert game.pending_trigger_order is None
    assert game.stack[-1].payload['target_card_id'] == ring.id
    resolve_top_of_stack(game)
    assert game.cards[ring.id].zone == Zone.GRAVEYARD
    assert game.cards[copter.id].zone == Zone.BATTLEFIELD


def test_incorrect_seat_or_target_cannot_mutate_pending_choice():
    game, rules, _, ring, _ = setup_targeted_sage(seat=2)
    before = serialize_match_snapshot(game)
    move = rules.legal_moves(game, 2)[0]
    with pytest.raises(ActionRejected):
        validate_action(game, rules, 1, {'type': 'choose_trigger_target', 'stack_id': move['stack_id'], 'target_card_id': ring.id})
    with pytest.raises(ActionRejected):
        validate_action(game, rules, 2, {'type': 'choose_trigger_target', 'stack_id': move['stack_id'], 'target_card_id': 'missing'})
    assert serialize_match_snapshot(game) == before


def test_target_choice_follows_simultaneous_trigger_order():
    game, rules, _, ring, _ = setup_targeted_sage(with_warden=True)
    assert game.pending_trigger_order and 'phase' not in game.pending_trigger_order
    order_moves = rules.legal_moves(game, 1)
    assert order_moves and all(move['type'] == 'choose_trigger_order' for move in order_moves)
    order = order_moves[0]['trigger_order']
    rules.take_action(game, 1, {'type': 'choose_trigger_order', 'trigger_order': order}, reject_invalid=True)
    assert game.pending_trigger_order['phase'] == 'targets'
    target = next(move for move in rules.legal_moves(game, 1) if move.get('target_card_id') == ring.id)
    rules.take_action(game, 1, {'type': 'choose_trigger_target', 'stack_id': target['stack_id'], 'target_card_id': ring.id}, reject_invalid=True)
    assert game.pending_trigger_order is None


def test_chosen_target_becoming_illegal_prevents_trigger_resolution():
    game, rules, _, ring, copter = setup_targeted_sage()
    target = next(move for move in rules.legal_moves(game, 1) if move.get('target_card_id') == copter.id)
    rules.take_action(game, 1, {'type': 'choose_trigger_target', 'stack_id': target['stack_id'], 'target_card_id': copter.id}, reject_invalid=True)
    game.players[2].battlefield.remove(copter.id)
    game.players[2].graveyard.append(copter.id)
    copter.zone = Zone.GRAVEYARD
    resolve_top_of_stack(game)
    assert ring.zone == Zone.BATTLEFIELD
    assert any('does not resolve' in line for line in game.log)


def test_unattended_trigger_prefers_opposing_permanent_and_never_pauses():
    game = state()
    ring = card(game, 'Sol Ring', Zone.BATTLEFIELD, owner=1)
    copter = card(game, "Smuggler's Copter", Zone.BATTLEFIELD, owner=2)
    sage = card(game, 'Reclamation Sage')
    cast(game, sage)
    resolve_top_of_stack(game)
    assert game.pending_trigger_order is None
    assert game.stack[-1].payload['target_card_id'] == copter.id
    resolve_top_of_stack(game)
    assert ring.zone == Zone.BATTLEFIELD
    assert copter.zone == Zone.GRAVEYARD


def test_targeted_trigger_without_legal_target_does_not_stall():
    game = state()
    game.trigger_order_choice_required = True
    game.trigger_order_choice_players = {1}
    sage = card(game, 'Reclamation Sage')
    cast(game, sage)
    resolve_top_of_stack(game)
    assert sage.zone == Zone.BATTLEFIELD
    assert game.pending_trigger_order is None
    assert not game.stack
    assert any('no legal target' in line for line in game.log)
