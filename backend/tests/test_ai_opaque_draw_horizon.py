"""Public draw counts are useful; unseen drawn identities must stay unknown."""
from unittest.mock import patch

import pytest

from ai.agent import AIAgent
from ai.information import decision_view, is_unknown
from ai.pending_effects import planning_copy, settled_public_position
from game_state.serializers import serialize_match_snapshot
from game_state.state import CardInstance, Zone
from rules_engine.engine import RulesEngine
from tests.test_ai_search_prefix import bare_state


def draw_position(seat):
    state = bare_state(seat)
    state.turn = 10
    # Existing printed Divination fixture, not a competitive deck claim.
    card = CardInstance('draw', 'Divination', seat, seat, Zone.HAND, ['Sorcery'],
                        mana_cost='{2}{U}', oracle_text='Draw two cards.')
    state.cards[card.id] = card
    state.players[seat].hand.append(card.id)
    state.players[seat].mana_pool.update({'U': 3})
    moves = RulesEngine().legal_moves(state, seat)
    view, _ = decision_view(state, seat, moves)
    return state, view, moves


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('style', ['Control', 'Tempo', 'Midrange', 'Ramp', 'Drain'])
def test_shared_horizon_values_guaranteed_opaque_draw_counts(seat, style):
    state, view, _ = draw_position(seat)
    ai = AIAgent(difficulty='master', archetype=style)
    before = serialize_match_snapshot(view)
    action = {'type': 'cast_spell', 'card_id': 'draw'}
    assert ai._strategic_line_score(view, action, seat, 0) > ai._strategic_line_score(
        view, {'type': 'pass_priority'}, seat, 0)
    assert serialize_match_snapshot(view) == before
    assert all(is_unknown(view.cards[cid]) for cid in view.players[seat].library)


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_master_draws_in_a_safe_empty_board_instead_of_passing(seat):
    state, _, moves = draw_position(seat)
    before = serialize_match_snapshot(state)
    choice = AIAgent(difficulty='master', archetype='Control').choose_action(state, moves, seat)
    assert choice.action['type'] == 'cast_spell'
    assert choice.action['card_id'] == 'draw'
    assert serialize_match_snapshot(state) == before
    from rules_engine.action_validation import checked_action
    paid = checked_action(planning_copy(state), RulesEngine(), seat, choice.action)
    assert paid.players[seat].mana_pool['U'] == 0
    assert 'draw' not in paid.players[seat].hand
    assert paid.stack[-1].source_card_id == 'draw'


@pytest.mark.parametrize('seat', [1, 2])
def test_existing_strict_projection_still_rejects_raw_hidden_draws(seat):
    state, _, _ = draw_position(seat)
    pending = planning_copy(state)
    RulesEngine().take_action(pending, seat, {'type': 'cast_spell', 'card_id': 'draw'}, reject_invalid=True)
    assert settled_public_position(pending, seat) is None
    assert settled_public_position(pending, seat, opaque_draw_counts=True) is None


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_announced_counterspell_prevents_projected_draw(seat):
    state, _, _ = draw_position(seat)
    opponent = 3-seat
    counter = CardInstance('counter', 'Counterspell', opponent, opponent, Zone.HAND, ['Instant'],
                           mana_cost='{U}{U}', oracle_text='Counter target spell.')
    state.cards[counter.id] = counter
    state.players[opponent].hand.append(counter.id)
    state.players[opponent].mana_pool['U'] = 2
    rules = RulesEngine()
    rules.take_action(state, seat, {'type': 'cast_spell', 'card_id': 'draw'}, reject_invalid=True)
    draw_id = state.stack[-1].id
    rules.take_action(state, seat, {'type': 'pass_priority'}, reject_invalid=True)
    rules.take_action(state, opponent, {'type': 'cast_spell', 'card_id': counter.id,
                                      'targets': {'target_stack_id': draw_id}}, reject_invalid=True)
    view, _ = decision_view(state, seat, rules.legal_moves(state, seat))
    before = serialize_match_snapshot(view)
    projected = settled_public_position(view, seat, opaque_draw_counts=True)
    assert projected is not None
    assert projected.players[seat].library == view.players[seat].library
    assert projected.players[seat].hand == view.players[seat].hand
    assert projected.cards['draw'].zone == Zone.GRAVEYARD
    assert not projected.stack
    assert serialize_match_snapshot(view) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_opposing_draw_increases_only_opaque_opponent_hand_count(seat):
    state, _, _ = draw_position(3-seat)
    rules = RulesEngine()
    rules.take_action(state, 3-seat, {'type': 'cast_spell', 'card_id': 'draw'}, reject_invalid=True)
    view, _ = decision_view(state, seat, rules.legal_moves(state, seat))
    before = serialize_match_snapshot(view)
    projected = settled_public_position(view, seat, opaque_draw_counts=True)
    assert projected is not None
    assert len(projected.players[3-seat].hand) == len(view.players[3-seat].hand) + 2
    assert all(is_unknown(projected.cards[cid]) for cid in projected.players[3-seat].hand)
    assert projected.players[seat].hand == view.players[seat].hand
    assert serialize_match_snapshot(view) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('already_drawn,expected', [(0, 1), (1, 0)])
def test_public_count_uses_real_draw_restrictions(seat, already_drawn, expected):
    from tests.test_static_ability_suppression import add
    state, _, _ = draw_position(seat)
    add(state, 'Spirit of the Labyrinth', 3-seat)
    state.draws_this_turn[seat] = already_drawn
    view, _ = decision_view(state, seat, RulesEngine().legal_moves(state, seat))
    RulesEngine().take_action(view, seat, {'type': 'cast_spell', 'card_id': 'draw'}, reject_invalid=True)
    before = serialize_match_snapshot(view)
    projected = settled_public_position(view, seat, opaque_draw_counts=True)
    assert projected is not None
    assert len(projected.players[seat].hand) == expected
    assert all(is_unknown(projected.cards[cid]) for cid in projected.players[seat].hand)
    assert serialize_match_snapshot(view) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_hidden_order_does_not_change_count_score_or_action(seat):
    state, view, _ = draw_position(seat)
    state.players[seat].library.reverse()
    reordered, _ = decision_view(state, seat, RulesEngine().legal_moves(state, seat))
    ai = AIAgent(difficulty='master', archetype='Control')
    action = {'type': 'cast_spell', 'card_id': 'draw'}
    assert ai._strategic_line_score(view, action, seat, 1) == ai._strategic_line_score(reordered, action, seat, 1)


@pytest.mark.parametrize('seat', [1, 2])
def test_known_library_shortage_is_not_guessed_away(seat):
    state, _, _ = draw_position(seat)
    removed = state.players[seat].library[:-1]
    state.players[seat].library = state.players[seat].library[-1:]
    state.players[seat].graveyard.extend(removed)
    for cid in removed:
        state.cards[cid].move_to_zone(Zone.GRAVEYARD)
    view, _ = decision_view(state, seat, RulesEngine().legal_moves(state, seat))
    ai = AIAgent(difficulty='master', archetype='Control')
    assert ai._strategic_line_score(view, {'type': 'cast_spell', 'card_id': 'draw'}, seat, 0) < (
        ai._strategic_line_score(view, {'type': 'pass_priority'}, seat, 0))


@pytest.mark.parametrize('seat', [1, 2])
def test_unknown_choice_still_rejects_count_projection(seat):
    _, view, _ = draw_position(seat)
    RulesEngine().take_action(view, seat, {'type': 'cast_spell', 'card_id': 'draw'}, reject_invalid=True)
    view.pending_mechanic_choice = {'kind': 'scry', 'player_id': seat, 'options': []}
    before = serialize_match_snapshot(view)
    assert settled_public_position(view, seat, opaque_draw_counts=True) is None
    assert serialize_match_snapshot(view) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_mill_or_library_reordering_is_not_a_draw_count(seat):
    _, view, _ = draw_position(seat)
    RulesEngine().take_action(view, seat, {'type': 'cast_spell', 'card_id': 'draw'}, reject_invalid=True)
    from ai.pending_effects import _opaque_draw_count_changes
    projected = planning_copy(view)
    cid = projected.players[seat].library.pop()
    projected.cards[cid].move_to_zone(Zone.GRAVEYARD)
    projected.players[seat].graveyard.append(cid)
    assert not _opaque_draw_count_changes(view, projected, seat)
    projected = planning_copy(view)
    projected.players[seat].library.reverse()
    assert not _opaque_draw_count_changes(view, projected, seat)
