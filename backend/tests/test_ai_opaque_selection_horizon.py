"""Canonical selection is not drawing, nor permission to inspect hidden cards."""
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from ai.information import decision_view, is_unknown
from ai.pending_effects import planning_copy, settled_public_position
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from game_state.state import Zone
from rules_engine.engine import RulesEngine
from effects.handlers import copy_spell
from tests.test_ai_recurring_engines import add as add_card
from tests.test_ai_search_prefix import bare_state
from tests.test_static_ability_suppression import add as add_static


DIRECTORY = Path(__file__).parent / 'fixtures' / 'opaque_selection'
ROWS = {}
for file in DIRECTORY.glob('*.json'):
    raw = json.loads(file.read_text())
    ROWS[raw['name']] = {**raw, 'power': raw.get('power'), 'toughness': raw.get('toughness')}


def position(seat, name):
    state = bare_state(seat)
    state.turn = 10
    card = add_card(state, name, seat, Zone.HAND, cards=ROWS)
    state.players[seat].mana_pool.update({'U': 10})
    return state, card


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,count', [('Impulse', 1), ('Anticipate', 1), ('Memory Deluge', 2), ('Dig Through Time', 2)])
@pytest.mark.parametrize('style', ['Control', 'Tempo', 'Midrange', 'Ramp', 'Drain'])
def test_shared_strategic_horizon_values_only_unknown_hand_count(seat, name, count, style):
    state, card = position(seat, name)
    rules = RulesEngine()
    view, _ = decision_view(state, seat, rules.legal_moves(state, seat))
    agent = AIAgent(difficulty='master', archetype=style)
    announced = planning_copy(view)
    rules.take_action(announced, seat, {'type': 'cast_spell', 'card_id': card.id}, reject_invalid=True)
    before = serialize_match_snapshot(announced)
    projected = settled_public_position(announced, seat, opaque_draw_counts=True)
    assert projected is not None
    assert len(projected.players[seat].hand) == count
    assert all(is_unknown(projected.cards[cid]) for cid in projected.players[seat].hand)
    assert len(projected.players[seat].library) == len(announced.players[seat].library) - count
    assert agent._strategic_position_score(announced, seat) == agent._strategic_position_score(projected, seat)
    assert settled_public_position(announced, seat) is None
    assert serialize_match_snapshot(announced) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,top_n,count', [('Impulse', 4, 1), ('Anticipate', 3, 1), ('Dig Through Time', 7, 2)])
def test_fixed_selection_and_deliberate_bottom_order_survive_reload(seat, name, top_n, count):
    state, card = position(seat, name)
    state.mechanic_choice_players = {1, 2}
    rules = RulesEngine()
    rules.take_action(state, seat, {'type': 'cast_spell', 'card_id': card.id}, reject_invalid=True)
    assert state.stack[-1].effect_key == 'look_top_select_hand'
    assert state.stack[-1].payload['top_n'] == top_n
    while state.pending_mechanic_choice is None:
        rules.take_action(state, state.priority_player, {'type': 'pass_priority'}, reject_invalid=True)
    original = list(state.pending_mechanic_choice['options'])
    assert len(original) == top_n
    assert state.pending_mechanic_choice['count'] == count
    chosen = original[:count]
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    rules.take_action(state, seat, {'type': 'choose_mechanic', 'card_ids': chosen}, reject_invalid=True)
    assert set(chosen).issubset(state.players[seat].hand)
    assert state.pending_mechanic_choice['kind'] == 'topdeck_bottom_order'
    bottom = list(reversed(state.pending_mechanic_choice['options']))
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    rules.take_action(state, seat, {'type': 'choose_mechanic', 'card_ids': bottom}, reject_invalid=True)
    assert state.players[seat].library[:len(bottom)] == bottom
    assert state.pending_mechanic_choice is None
    assert state.cards[card.id].zone == Zone.GRAVEYARD
    assert not any('draws a card' in line for line in state.log)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,count', [('Impulse', 1), ('Anticipate', 1), ('Memory Deluge', 2), ('Dig Through Time', 2)])
def test_selection_is_not_limited_by_spirit_draw_restriction(seat, name, count):
    state, card = position(seat, name)
    add_static(state, 'Spirit of the Labyrinth', 3-seat)
    state.draws_this_turn[seat] = 1
    rules = RulesEngine()
    view, _ = decision_view(state, seat, rules.legal_moves(state, seat))
    rules.take_action(view, seat, {'type': 'cast_spell', 'card_id': card.id}, reject_invalid=True)
    projected = settled_public_position(view, seat, opaque_draw_counts=True)
    assert projected is not None and len(projected.players[seat].hand) == count
    assert projected.draws_this_turn[seat] == 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('cards_left', [0, 1])
def test_short_or_empty_library_selection_is_not_draw_failure(seat, cards_left):
    state, card = position(seat, 'Memory Deluge')
    removed = state.players[seat].library[cards_left:]
    state.players[seat].library = state.players[seat].library[:cards_left]
    for cid in removed:
        state.cards[cid].move_to_zone(Zone.EXILE)
        state.players[seat].exile.append(cid)
    rules = RulesEngine()
    view, _ = decision_view(state, seat, rules.legal_moves(state, seat))
    rules.take_action(view, seat, {'type': 'cast_spell', 'card_id': card.id}, reject_invalid=True)
    projected = settled_public_position(view, seat, opaque_draw_counts=True)
    assert projected is not None
    assert len(projected.players[seat].hand) == cards_left
    assert projected.winner is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Impulse', 'Anticipate', 'Memory Deluge', 'Dig Through Time'])
def test_hidden_order_invariance_and_raw_state_rejection(seat, name):
    state, card = position(seat, name)
    rules = RulesEngine()
    rules.take_action(state, seat, {'type': 'cast_spell', 'card_id': card.id}, reject_invalid=True)
    assert settled_public_position(state, seat, opaque_draw_counts=True) is None
    view, _ = decision_view(state, seat, rules.legal_moves(state, seat))
    permuted = planning_copy(view)
    permuted.players[seat].library.reverse()
    agent = AIAgent(difficulty='master', archetype='Control')
    assert agent._strategic_position_score(view, seat) == agent._strategic_position_score(permuted, seat)
    projected = settled_public_position(view, 3-seat, opaque_draw_counts=True)
    assert projected is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('style', ['Control', 'Tempo'])
@pytest.mark.parametrize('name', ['Impulse', 'Anticipate', 'Memory Deluge', 'Dig Through Time'])
def test_master_can_actually_cast_selection_with_an_empty_hand(seat, style, name):
    state, card = position(seat, name)
    before = serialize_match_snapshot(state)
    agent = AIAgent(difficulty='master', archetype=style)
    decision = agent.choose_action(state, RulesEngine().legal_moves(state, seat), seat)
    assert decision.action['type'] == 'cast_spell' and decision.action['card_id'] == card.id
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,count', [('Impulse', 2), ('Anticipate', 2), ('Memory Deluge', 2), ('Dig Through Time', 4)])
def test_actual_copies_keep_fixed_counts_but_not_mana_spent(seat, name, count):
    state, card = position(seat, name)
    rules = RulesEngine()
    rules.take_action(state, seat, {'type': 'cast_spell', 'card_id': card.id}, reject_invalid=True)
    copy_spell(state, seat, {'target_stack_id': state.stack[-1].id})
    view, _ = decision_view(state, seat, [])
    before = serialize_match_snapshot(view)
    projected = settled_public_position(view, seat, opaque_draw_counts=True)
    assert projected is not None and len(projected.players[seat].hand) == count
    assert serialize_match_snapshot(view) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_announced_counter_prevents_selective_hand_gain(seat):
    state, card = position(seat, 'Memory Deluge')
    counter = add_card(state, 'Counterspell', 3-seat, Zone.HAND, cards=ROWS)
    state.players[3-seat].mana_pool.update({'U': 2})
    rules = RulesEngine()
    rules.take_action(state, seat, {'type': 'cast_spell', 'card_id': card.id}, reject_invalid=True)
    target = state.stack[-1].id
    rules.take_action(state, seat, {'type': 'pass_priority'}, reject_invalid=True)
    rules.take_action(state, 3-seat, {'type': 'cast_spell', 'card_id': counter.id,
                                   'targets': {'target_stack_id': target}}, reject_invalid=True)
    view, _ = decision_view(state, seat, [])
    projected = settled_public_position(view, seat, opaque_draw_counts=True)
    assert projected is not None and projected.players[seat].hand == []


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Impulse', 'Memory Deluge'])
def test_known_top_card_keeps_conservative_fallback(seat, name):
    from copy import deepcopy
    state, card = position(seat, name)
    rules = RulesEngine()
    rules.take_action(state, seat, {'type': 'cast_spell', 'card_id': card.id}, reject_invalid=True)
    view, _ = decision_view(state, seat, [])
    top = view.players[seat].library[-1]
    view.cards[top] = deepcopy(state.cards[top])
    assert not is_unknown(view.cards[top])
    assert settled_public_position(view, seat, opaque_draw_counts=True) is None


@pytest.mark.parametrize('seat', [1, 2])
def test_filtered_creature_search_does_not_invent_hits(seat):
    state, card = position(seat, 'Collected Company')
    state.players[seat].mana_pool.update({'G': 4})
    rules = RulesEngine()
    rules.take_action(state, seat, {'type': 'cast_spell', 'card_id': card.id}, reject_invalid=True)
    view, _ = decision_view(state, seat, [])
    assert settled_public_position(view, seat, opaque_draw_counts=True) is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,count', [('Impulse', 1), ('Memory Deluge', 2), ('Dig Through Time', 2)])
def test_opposing_selection_projects_counts_without_revealing_hand(seat, name, count):
    state, card = position(seat, name)
    rules = RulesEngine()
    rules.take_action(state, seat, {'type': 'cast_spell', 'card_id': card.id}, reject_invalid=True)
    view, _ = decision_view(state, 3-seat, [])
    before = serialize_match_snapshot(view)
    projected = settled_public_position(view, 3-seat, opaque_draw_counts=True)
    assert projected is not None and len(projected.players[seat].hand) == count
    assert all(is_unknown(projected.cards[cid]) for cid in projected.players[seat].hand)
    assert serialize_match_snapshot(view) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,usable', [('Impulse', True), ('Anticipate', True),
                                       ('Memory Deluge', False), ('Dig Through Time', True)])
def test_free_cast_policy_distinguishes_fixed_selection_from_zero_mana_spent(seat, name, usable):
    from ai.effect_cast_policy import usable_cast
    state, card = position(seat, name)
    state.players[seat].hand.remove(card.id)
    state.players[seat].graveyard.append(card.id)
    card.move_to_zone(Zone.GRAVEYARD)
    before = serialize_match_snapshot(state)
    assert (usable_cast(state, seat, card.id) is not None) == usable
    assert serialize_match_snapshot(state) == before
