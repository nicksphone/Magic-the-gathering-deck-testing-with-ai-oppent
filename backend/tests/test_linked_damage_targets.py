"""Canonical linked player/planeswalker and creature target instances."""
import json
from copy import deepcopy
from pathlib import Path

import pytest

from game_state.state import MatchFactory, Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.cast_choice import build_cast_hints, has_available_targets_for_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from effects.registry import resolve_effect
from tests.test_ai_search_prefix import bare_state
from tests.test_ai_recurring_engines import add


FIXTURES = Path(__file__).parent / 'fixtures'


def raw_card(state, raw, seat, zone):
    sample = MatchFactory.from_decks([{**raw, 'card_name': raw['name'], 'quantity': 8}], [], seed=831)
    card = deepcopy(next(iter(sample.cards.values())))
    card.id = state.allocate_object_id()
    card.owner = card.controller = seat
    card.move_to_zone(zone)
    state.cards[card.id] = card
    getattr(state.players[seat], zone.value).append(card.id)
    return card


def position(seat=1, primary='player'):
    state = bare_state(seat)
    raw = json.loads((FIXTURES / 'coupled_targets/searing-blaze.json').read_text())
    spell = raw_card(state, raw, seat, Zone.HAND)
    creature = add(state, 'Torrential Gearhulk', 3-seat)
    walker = None
    if primary == 'planeswalker':
        raw = json.loads((FIXTURES / 'coupled_targets/ugin.json').read_text())
        walker = raw_card(state, raw, 3-seat, Zone.BATTLEFIELD)
    state.players[seat].mana_pool = {'R': 2}
    targets = ({'target_player': 3-seat, 'target_card_id': creature.id} if walker is None
               else {'target_card_ids': [walker.id, creature.id]})
    return state, spell, creature, walker, targets


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('primary', ['player', 'planeswalker'])
@pytest.mark.parametrize('entry', ['none', 'before', 'after', 'opponent'])
def test_paid_linked_damage_selects_one_amount_and_both_recipients(seat, primary, entry):
    state, spell, creature, walker, targets = position(seat, primary)
    if entry == 'before':
        state.land_entries_this_turn[seat] = 1
    if entry == 'opponent':
        state.land_entries_this_turn[3-seat] = 1
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': spell.id, 'targets': targets})
    assert state.players[seat].mana_pool['R'] == 0
    if entry == 'after':
        state.land_entries_this_turn[seat] = 1
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    before = state.players[3-seat].life if walker is None else state.cards[walker.id].loyalty
    amount = 3 if entry in ['before', 'after'] else 1
    assert resolve_top_of_stack(state)
    assert state.cards[creature.id].counters.get('__damage_marked', 0) == amount
    after = state.players[3-seat].life if walker is None else state.cards[walker.id].loyalty
    assert after == before-amount
    assert state.cards[spell.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad', ['empty', 'player_only', 'creature_only', 'wrong_controller', 'mixed', 'wrong_order'])
def test_incomplete_or_wrong_dependency_rejects_without_payments(seat, bad):
    state, spell, creature, _, targets = position(seat)
    invalid = {
        'empty': {}, 'player_only': {'target_player': 3-seat},
        'creature_only': {'target_card_id': creature.id},
        'wrong_controller': {'target_player': seat, 'target_card_id': creature.id},
        'mixed': {**targets, 'target_card_ids': [creature.id]},
        'wrong_order': {'target_card_ids': [creature.id, creature.id]},
    }[bad]
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': spell.id, 'targets': invalid})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_empty_creature_board_has_no_complete_linked_cast(seat):
    state, spell, creature, _, _ = position(seat)
    resolve_effect(state, seat, 'exile', {'target_card_id': creature.id})
    hints = build_cast_hints(state, spell, seat)
    assert not has_available_targets_for_action(hints)
    assert not any(move.get('card_id') == spell.id for move in RulesEngine().legal_moves(state, seat))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('change', ['exile', 'return', 'control', 'hexproof'])
def test_illegal_secondary_does_not_prevent_player_damage(seat, change):
    state, spell, creature, _, targets = position(seat)
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': spell.id, 'targets': targets})
    if change in ['exile', 'return']:
        resolve_effect(state, seat, 'exile', {'target_card_id': creature.id})
        if change == 'return':
            state.players[3-seat].exile.remove(creature.id)
            state.cards[creature.id].move_to_zone(Zone.BATTLEFIELD)
            state.players[3-seat].battlefield.append(creature.id)
    elif change == 'control':
        resolve_effect(state, seat, 'change_control', {'target_card_id': creature.id})
    else:
        resolve_effect(state, seat, 'grant_keyword', {'target_card_id': creature.id, 'keyword': 'hexproof'})
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    before = state.players[3-seat].life
    assert resolve_top_of_stack(state)
    assert state.players[3-seat].life == before-1
    assert state.cards[creature.id].counters.get('__damage_marked', 0) == 0


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('style', ['Aggro', 'Control', 'Tempo', 'Midrange'])
def test_ai_materializes_a_complete_planeswalker_pair_when_player_is_shielded(seat, style):
    from ai.agent import AIAgent
    state, spell, _, _, _ = position(seat, 'planeswalker')
    rows = json.loads((FIXTURES / 'opening_hand.json').read_text())
    if isinstance(rows, dict):
        rows = rows['cards']
    leyline = next(card for card in rows if card['name'] == 'Leyline of Sanctity')
    raw_card(state, leyline, 3-seat, Zone.BATTLEFIELD)
    before = serialize_match_snapshot(state)
    move = next(move for move in RulesEngine().legal_moves(state, seat) if move.get('card_id') == spell.id)
    action = AIAgent('master', style)._materialize_action(state, move, seat)
    assert not action.get('_invalid_ai_choice')
    assert serialize_match_snapshot(state) == before
    accepted = checked_action(state, RulesEngine(), seat, action)
    assert accepted.cards[spell.id].zone == Zone.STACK


def leyline(state, seat):
    rows = json.loads((FIXTURES / 'opening_hand.json').read_text())
    rows = rows['cards'] if isinstance(rows, dict) else rows
    raw_card(state, next(card for card in rows if card['name'] == 'Leyline of Sanctity'), seat, Zone.BATTLEFIELD)


@pytest.mark.parametrize('seat', [1, 2])
def test_new_player_hexproof_preserves_legal_creature_damage(seat):
    state, spell, creature, _, targets = position(seat)
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': spell.id, 'targets': targets})
    leyline(state, 3-seat)
    before = state.players[3-seat].life
    assert resolve_top_of_stack(state)
    assert state.players[3-seat].life == before
    assert state.cards[creature.id].counters['__damage_marked'] == 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('both', [False, True])
def test_planeswalker_dependency_uses_current_controller(seat, both):
    state, spell, creature, walker, targets = position(seat, 'planeswalker')
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': spell.id, 'targets': targets})
    resolve_effect(state, seat, 'change_control', {'target_card_id': walker.id})
    if both:
        resolve_effect(state, seat, 'change_control', {'target_card_id': creature.id})
    assert resolve_top_of_stack(state)
    assert state.cards[walker.id].loyalty == 6
    assert state.cards[creature.id].counters.get('__damage_marked', 0) == int(both)


@pytest.mark.parametrize('seat', [1, 2])
def test_all_illegal_targets_fizzle_without_needing_legacy_history(seat):
    state, spell, creature, _, targets = position(seat)
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': spell.id, 'targets': targets})
    leyline(state, 3-seat)
    resolve_effect(state, seat, 'exile', {'target_card_id': creature.id})
    state.land_entry_history_known = False
    before = state.players[3-seat].life
    assert resolve_top_of_stack(state)
    assert state.players[3-seat].life == before
    assert state.cards[spell.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_unverified_departed_planeswalker_dependency_is_explicit_and_nonmutating(seat):
    state, spell, _, walker, targets = position(seat, 'planeswalker')
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': spell.id, 'targets': targets})
    resolve_effect(state, seat, 'exile', {'target_card_id': walker.id})
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected, match='LKI coverage'):
        resolve_top_of_stack(state)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_linked_copy_keeps_original_reference_without_ward_on_returned_object(seat):
    from effects.handlers import copy_spell
    from tests.test_ward_resolution import add as add_ward
    state, spell, _, _, _ = position(seat)
    warded = add_ward(state, 'Tolarian Terror', 3-seat)
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': spell.id,
                           'targets': {'target_player': 3-seat, 'target_card_id': warded.id}})
    original = next(item.id for item in state.stack if item.source_card_id == spell.id)
    assert len([item for item in state.stack if item.effect_key == 'ward_payment']) == 1
    resolve_effect(state, seat, 'exile', {'target_card_id': warded.id})
    state.players[3-seat].exile.remove(warded.id)
    state.cards[warded.id].move_to_zone(Zone.BATTLEFIELD)
    state.players[3-seat].battlefield.append(warded.id)
    copy_spell(state, seat, {'target_stack_id': original})
    wards = [item for item in state.stack if item.effect_key == 'ward_payment']
    assert len(wards) == 1
    assert wards[0].payload['target_stack_id'] == original
