"""Canonical cast surfaces, opportunity cost and public-only reservation controls."""
from copy import deepcopy

import pytest

from ai.agent import _card_for_move
from ai.pending_effects import decision_projection_scope
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Step, Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.ai_knowledge_consumer_fixture import (
    actor, modal_case, reservation_case, take, view_and_moves,
)


def reservation(state, seat, draw):
    view, legal = view_and_moves(state, seat)
    move = next(m for m in legal if m['type'] == 'cast_spell' and m['card_id'] == draw.id)
    before = serialize_match_snapshot(view)
    ai = actor('Tempo')
    with decision_projection_scope(view, seat):
        value = ai._instant_value_reservation(view, move, seat)
    assert serialize_match_snapshot(view) == before
    return value


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('resources', ['scarce', 'extra_island', 'extra_pool', 'unpayable_answer'])
def test_actual_adventure_mana_opportunity_cost(seat, resources):
    state, draw, answer, target = reservation_case(seat)
    if resources == 'extra_island':
        take(state, 'Island', seat, Zone.BATTLEFIELD)
    elif resources == 'extra_pool':
        state.players[seat].mana_pool = {'U': 2}
    elif resources == 'unpayable_answer':
        for cid in state.players[seat].battlefield:
            if state.cards[cid].name == 'Mountain':
                state.cards[cid].tapped = True
    before = serialize_match_snapshot(state)
    expected = -6 if resources == 'scarce' else 0
    assert reservation(state, seat, draw) == expected
    assert reservation(deserialize_match_snapshot(before), seat, draw) == expected
    altered = deepcopy(state)
    for player in altered.players.values():
        player.library.reverse()
    assert reservation(altered, seat, draw) == expected
    assert serialize_match_snapshot(state) == before
    if resources != 'unpayable_answer':
        view, legal = view_and_moves(state, seat)
        move = next(m for m in legal if m.get('card_id') == answer.id and m.get('selected_face_index') == 1)
        checked = checked_action(state, RulesEngine(), seat, actor('Tempo')._materialize_action(view, move, seat))
        assert checked.stack[-1].effect_key == 'return_permanent_to_hand'
        assert checked.stack[-1].payload['target_card_id'] == target.id


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('boundary', ['end_step', 'cleanup', 'own_turn', 'emergency', 'friendly_only', 'no_target'])
def test_no_blanket_hold_or_friendly_bounce_reservation(seat, boundary):
    state, draw, answer, target = reservation_case(seat)
    if boundary in {'end_step', 'cleanup'}:
        state.step = Step.END_STEP if boundary == 'end_step' else Step.CLEANUP
    elif boundary == 'own_turn':
        state.active_player = seat
    elif boundary == 'emergency':
        state.players[seat].life = 1
    else:
        enemy = state.players[3-seat]
        enemy.battlefield.remove(target.id)
        target.move_to_zone(Zone.EXILE)
        enemy.exile.append(target.id)
        if boundary == 'friendly_only':
            take(state, 'Delver of Secrets', seat, Zone.BATTLEFIELD)
    # Cleanup doesn't offer a cast priority action; the heuristic guard still
    # receives the unchanged offered action from the prior priority window.
    if boundary == 'cleanup':
        state.step = Step.END_STEP
        view, legal = view_and_moves(state, seat)
        move = next(m for m in legal if m.get('card_id') == draw.id)
        view.step = Step.CLEANUP
        assert actor('Tempo')._instant_value_reservation(view, move, seat) == 0
    else:
        assert reservation(state, seat, draw) == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_interaction_itself_is_not_penalized_as_value_spell(seat):
    state, _, answer, _ = reservation_case(seat)
    view, legal = view_and_moves(state, seat)
    move = next(m for m in legal if m.get('card_id') == answer.id and m.get('selected_face_index') == 1)
    assert actor('Tempo')._instant_value_reservation(view, move, seat) == 0


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('role', ['race', 'convert'])
def test_modal_adjustment_and_materializer_share_selected_surface(seat, role):
    state, source = modal_case(seat, role)
    view, legal = view_and_moves(state, seat)
    move = next(m for m in legal if m.get('card_id') == source.id and m.get('selected_face_index') == 1)
    ai = actor('Midrange', 'Tempo')
    before = serialize_match_snapshot(view)
    original = view.cards[source.id]
    selected = _card_for_move(view, move)
    expected_state = deepcopy(view)
    expected_state.cards[source.id] = selected
    assert ai._matchup_move_adjustment(view, move, seat) == ai._matchup_move_adjustment(expected_state, move, seat)
    action = ai._materialize_action(view, move, seat)
    result = checked_action(state, RulesEngine(), seat, action)
    assert result.stack[-1].source_card_id == source.id
    assert action['selected_face_index'] == 1
    assert original.name == 'Bonecrusher Giant' and selected.name == 'Stomp'
    assert serialize_match_snapshot(view) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('prohibited', [False, True])
def test_phyrexian_cost_authority_without_broadening_legacy_debuff_tags(seat, prohibited):
    from tests.test_contextual_cost_prohibitions import canonical
    state, draw, answer, _ = reservation_case(seat)
    state.players[seat].hand.remove(answer.id)
    answer.move_to_zone(Zone.EXILE)
    state.players[seat].exile.append(answer.id)
    spell = canonical(state, 'dismember', seat, Zone.HAND)
    for cid in state.players[seat].battlefield:
        if state.cards[cid].name == 'Mountain':
            state.cards[cid].tapped = True
    if prohibited:
        canonical(state, 'angel-of-jubilation', 3-seat)
    from rules_engine.cast_choice import available_cast_options_and_hints
    assert bool(available_cast_options_and_hints(state, spell, seat)[0]) is (not prohibited)
    assert not actor('Tempo')._spell_tags(spell)
    # Debuff classification is a separate known seam, not this bounce repair.
    assert reservation(state, seat, draw) == 0
