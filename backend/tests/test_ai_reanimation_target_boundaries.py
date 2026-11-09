"""Native unknown/terminal/privacy boundaries, separate from passed target cases."""
from copy import deepcopy
from dataclasses import replace
import pickle

import pytest

from ai.agent import AIAgent
from ai.pending_effects import (
    _unanswered_action_outcome, combat_expansion_available, decision_projection_scope,
)
from game_state.state import MatchFactory, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from tests.library_canonical_fixtures import canonical_card
from tests.rules_printed_facts_e4 import canonical_deck_entry
from tests.test_ai_reanimation_target_outcomes import paid_result, position


class UnsafeOnlyReanimationTargets(AssertionError):
    """Data-free failure identity after the native fatal-outcome witnesses."""


class DiscardedUncertainReanimationTarget(AssertionError):
    """Uncertainty must not silently restore a proved-losing default target."""


@pytest.mark.parametrize('seat', [1, 2])
def test_all_known_fatal_targets_leave_the_native_ai_a_pass(seat):
    state, spell, large, small, _ = position(seat, life=2)
    for target, remaining in [(large, -6), (small, 0)]:
        result = paid_result(state, seat, {'type': 'cast_spell', 'card_id': spell,
                                         'targets': {'target_card_id': target}})
        assert result.winner == 3-seat and result.players[seat].life == remaining
    ai = AIAgent('strong', 'Reanimator')
    before = pickle.dumps(state, protocol=5)
    action = ai.choose_action(state, ai.engine.legal_moves(state, seat), seat).action
    assert pickle.dumps(state, protocol=5) == before
    if action['type'] != 'pass_priority' or action.get('card_id') == spell:
        raise UnsafeOnlyReanimationTargets


@pytest.mark.parametrize('seat', [1, 2])
def test_unknown_draw_alternative_remains_available_over_a_proven_loss(seat):
    state, spell, large, small, _ = position(seat, life=6)
    state.players[seat].graveyard.remove(small)
    state.players[seat].exile.append(small)
    state.cards[small].move_to_zone(Zone.EXILE)
    born = MatchFactory.from_decks([canonical_deck_entry('Mulldrifter', 8)], [], seed=0)
    template = next(card for card in born.cards.values() if card.zone == Zone.LIBRARY)
    draw = replace(template, id=state.allocate_object_id(), owner=seat, controller=seat,
                   zone=Zone.GRAVEYARD)
    state.cards[draw.id] = draw
    state.players[seat].graveyard.append(draw.id)
    candidate = {'type': 'cast_spell', 'card_id': spell,
                 'targets': {'target_card_id': draw.id}}
    before = pickle.dumps(state, protocol=5)
    assert _unanswered_action_outcome(state, seat, candidate) is None
    ai = AIAgent('master', 'Reanimator')
    move = next(row for row in ai.engine.legal_moves(state, seat) if row.get('card_id') == spell)
    action = ai._materialize_action(state, move, seat)
    if action['targets']['target_card_id'] != draw.id:
        raise DiscardedUncertainReanimationTarget
    assert _unanswered_action_outcome(state, seat, action) is None
    assert pickle.dumps(state, protocol=5) == before
    actual = paid_result(state, seat, action)
    assert actual.winner is None and actual.players[seat].life == 1
    assert actual.cards[draw.id].zone == Zone.BATTLEFIELD
    assert actual.cards[large].zone == Zone.GRAVEYARD
    assert len(actual.players[seat].hand) == 2


@pytest.mark.parametrize('seat', [1, 2])
def test_explicit_rejected_target_remains_subject_to_engine_validation(seat):
    state, spell, _, _, _ = position(seat)
    ai = AIAgent('master', 'Reanimator')
    move = next(row for row in ai.engine.legal_moves(state, seat) if row.get('card_id') == spell)
    move['targets'] = {'target_card_id': 'absent-graveyard-target'}
    before = pickle.dumps(state, protocol=5)
    action = ai._materialize_action(state, move, seat)
    assert action['targets']['target_card_id'] == 'absent-graveyard-target'
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, action)
    assert pickle.dumps(state, protocol=5) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_opponent_hidden_identity_does_not_change_safe_public_target(seat):
    state, spell, _, small, _ = position(seat)
    hidden_id = state.allocate_object_id()
    state.cards[hidden_id] = canonical_card('Grizzly Bears', id=hidden_id,
        owner=3-seat, controller=3-seat, zone=Zone.HAND)
    state.players[3-seat].hand.append(hidden_id)
    other = deepcopy(state)
    other.cards[hidden_id] = canonical_card('Griselbrand', id=hidden_id,
        owner=3-seat, controller=3-seat, zone=Zone.HAND)
    ai = AIAgent('master', 'Reanimator')
    before = pickle.dumps(state, protocol=5), pickle.dumps(other, protocol=5)
    first_move = next(row for row in ai.engine.legal_moves(state, seat) if row.get('card_id') == spell)
    second_move = next(row for row in ai.engine.legal_moves(other, seat) if row.get('card_id') == spell)
    first = ai._materialize_action(state, first_move, seat)
    second = ai._materialize_action(other, second_move, seat)
    assert first == second and first['targets']['target_card_id'] == small
    assert (pickle.dumps(state, protocol=5), pickle.dumps(other, protocol=5)) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_sticky_combat_denial_stops_new_graveyard_target_projection(seat):
    state, spell, large, _, _ = position(seat)
    ai = AIAgent('master', 'Reanimator')
    move = next(row for row in ai.engine.legal_moves(state, seat) if row.get('card_id') == spell)
    before = pickle.dumps(state, protocol=5)
    with decision_projection_scope(state, seat, combat_expansion_limit=0):
        assert not combat_expansion_available(charge=True)
        action = ai._materialize_action(state, move, seat)
        assert action['targets']['target_card_id'] == large
        assert not combat_expansion_available()
    assert pickle.dumps(state, protocol=5) == before
