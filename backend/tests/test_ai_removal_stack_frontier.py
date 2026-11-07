"""Canonical paid responses; hidden older effects are not TRAIN labels or wins."""
from copy import deepcopy
import random

import pytest

from ai.agent import AIAgent
from ai.information import decision_view
from ai.pending_effects import friendly_destruction_profit
from game_state.serializers import serialize_match_snapshot
from game_state.state import Step, Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_ai_friendly_material_conservation import CARDS
from tests.test_ai_recurring_engines import fixture
from tests.test_linked_damage_targets import raw_card


def response_position(seat, spell, body, *, opposing_hook=False, enemy=False,
                      own_artist=False, opposing_life=20, pending_theft=False,
                      temporary_control=False):
    state = fixture()
    state.active_player = state.priority_player = seat if temporary_control else 3-seat
    state.step = Step.PRECOMBAT_MAIN if pending_theft or temporary_control else Step.END_STEP
    state.players[3-seat].life = opposing_life
    for player in state.players.values():
        player.mana_pool = {color: 5 for color in 'WUBRGC'}
    target = raw_card(state, CARDS[body], 3-seat if temporary_control else seat, Zone.BATTLEFIELD)
    target.summoning_sick = False
    source = raw_card(state, CARDS[spell], seat, Zone.HAND)
    other = raw_card(state, CARDS[body], 3-seat, Zone.BATTLEFIELD) if enemy else None
    if opposing_hook:
        raw_card(state, CARDS['The Meathook Massacre'], 3-seat, Zone.BATTLEFIELD)
    if own_artist:
        raw_card(state, CARDS['Blood Artist'], seat, Zone.BATTLEFIELD)
    draw = raw_card(state, CARDS['Growth Spiral'], 3-seat, Zone.HAND)
    rules = RulesEngine()
    if temporary_control:
        theft = raw_card(state, CARDS['Claim the Firstborn'], seat, Zone.HAND)
        state = checked_action(state, rules, seat, {
            'type': 'cast_spell', 'card_id': theft.id,
            'targets': {'target_card_id': target.id}})
        for _ in range(8):
            if not state.stack:
                break
            state = checked_action(state, rules, state.priority_player, {'type': 'pass_priority'})
        assert state.cards[target.id].controller == seat
        assert target.id in state.temporary_control_changes
        state = checked_action(state, rules, seat, {'type': 'pass_priority'})
    if pending_theft:
        theft = raw_card(state, CARDS['Claim the Firstborn'], 3-seat, Zone.HAND)
        state = checked_action(state, rules, 3-seat, {
            'type': 'cast_spell', 'card_id': theft.id,
            'targets': {'target_card_id': target.id}})
        assert state.stack[-1].source_card_id == theft.id
    mana_before = sum(state.players[3-seat].mana_pool.values())
    state = checked_action(state, rules, 3-seat, {
        'type': 'cast_spell', 'card_id': draw.id, 'targets': {}})
    assert sum(state.players[3-seat].mana_pool.values()) == mana_before - 2
    state = checked_action(state, rules, 3-seat, {'type': 'pass_priority'})
    assert state.priority_player == seat and len(state.stack) == (2 if pending_theft else 1)
    moves = rules.legal_moves(state, seat)
    view, moves = decision_view(state, seat, moves)
    action = {'type': 'cast_spell', 'card_id': source.id,
              'targets': {'target_card_id': target.id}}
    checked_action(state, rules, seat, action)
    return view, moves, action, other.id if other else None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('spell', ['Fatal Push', 'Lightning Bolt'])
@pytest.mark.parametrize('body', ['Recruitment Officer', 'Llanowar Elves'])
@pytest.mark.parametrize('hook', [False, True])
def test_known_uncompensated_removal_is_vetoed_before_unknown_older_draw(seat, spell, body, hook):
    view, moves, action, _ = response_position(seat, spell, body, opposing_hook=hook)
    before = serialize_match_snapshot(view)
    offered = deepcopy(moves)
    rng = random.getstate(), view.rng.getstate()
    agent = AIAgent('master', 'Midrange')
    # The full future remains unknown; only the paid response's public loss is known.
    assert friendly_destruction_profit(view, seat, action) is None
    assert agent._harmful_friendly_removal(view, action, seat) is True
    assert agent._materialize_action(view, action, seat).get('_invalid_ai_choice') is True
    assert serialize_match_snapshot(view) == before and moves == offered
    assert (random.getstate(), view.rng.getstate()) == rng


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('hook', [False, True])
def test_public_enemy_target_remains_available_instead_of_own_body(seat, hook):
    view, _, action, enemy = response_position(
        seat, 'Fatal Push', 'Recruitment Officer', opposing_hook=hook, enemy=True)
    before = serialize_match_snapshot(view)
    chosen = AIAgent('master', 'Midrange')._materialize_action(view, action, seat)
    assert not chosen.get('_invalid_ai_choice')
    assert chosen['targets']['target_card_id'] == enemy
    checked_action(view, RulesEngine(), seat, chosen)
    assert serialize_match_snapshot(view) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('hook', [False, True])
@pytest.mark.parametrize('opposing_life', [1, 20])
def test_own_death_payoff_is_not_blanket_rejected(seat, hook, opposing_life):
    view, _, action, _ = response_position(
        seat, 'Fatal Push', 'Recruitment Officer', opposing_hook=hook,
        own_artist=True, opposing_life=opposing_life)
    before = serialize_match_snapshot(view)
    agent = AIAgent('master', 'Drain')
    assert agent._harmful_friendly_removal(view, action, seat) is False
    chosen = agent._materialize_action(view, action, seat)
    assert chosen == action
    checked_action(view, RulesEngine(), seat, chosen)
    assert serialize_match_snapshot(view) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('spell', ['Fatal Push', 'Lightning Bolt'])
def test_pending_theft_can_justify_removing_the_currently_friendly_body(seat, spell):
    view, _, action, _ = response_position(
        seat, spell, 'Recruitment Officer', pending_theft=True)
    before = serialize_match_snapshot(view)
    assert friendly_destruction_profit(view, seat, action) is None
    agent = AIAgent('master', 'Midrange')
    assert agent._harmful_friendly_removal(view, action, seat) is False
    assert agent._materialize_action(view, action, seat) == action
    assert serialize_match_snapshot(view) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('hook', [False, True])
def test_actual_temporary_control_is_not_priced_as_permanent_ownership(seat, hook):
    view, _, action, _ = response_position(
        seat, 'Fatal Push', 'Recruitment Officer', temporary_control=True, opposing_hook=hook)
    before = serialize_match_snapshot(view)
    assert friendly_destruction_profit(view, seat, action) is None
    assert AIAgent('master', 'Midrange')._harmful_friendly_removal(view, action, seat) is False
    assert serialize_match_snapshot(view) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_hidden_older_draw_identities_do_not_change_material_veto(seat):
    view, _, action, _ = response_position(
        seat, 'Fatal Push', 'Recruitment Officer', opposing_hook=True)
    swapped = deepcopy(view)
    swapped.players[3-seat].library.reverse()
    before, other = serialize_match_snapshot(view), serialize_match_snapshot(swapped)
    agent = AIAgent('master', 'Midrange')
    assert agent._harmful_friendly_removal(view, action, seat) is True
    assert agent._harmful_friendly_removal(swapped, action, seat) is True
    assert serialize_match_snapshot(view) == before and serialize_match_snapshot(swapped) == other


@pytest.mark.parametrize('seat', [1, 2])
def test_native_shortlist_filters_self_removal_before_synthetic_q_ranking(monkeypatch, seat):
    """Only scores are synthetic; proposal generation and admission remain genuine."""
    from ai import learned_policy, learned_qv
    from tests.test_live_learned_policy import _binding
    from tests.test_training_reference_context import _expanded, _field

    view, moves, _, _ = response_position(
        seat, 'Fatal Push', 'Recruitment Officer', opposing_hook=True)
    before = serialize_match_snapshot(view)
    binding = _binding(learned_policy)
    scored = []

    class SyntheticScores:
        def predict(self, pack):
            kind = _field(_expanded(pack), 'type')['value']
            scored.append(kind)
            return {'q': 0.9 if kind == 'cast_spell' else 0.0, 'v': 0.0}

    monkeypatch.setattr(learned_qv.QVPolicy, 'prepare', lambda _policy, _pack: SyntheticScores())
    agent = AIAgent('master', 'Midrange', learned_binding=binding)
    selected = learned_policy.choose_learned_action(binding, agent, view, moves, seat,
        admit=lambda action: checked_action(view, RulesEngine(), seat, action))
    assert selected is not None and scored
    assert 'cast_spell' not in scored and selected['type'] != 'cast_spell'
    assert serialize_match_snapshot(view) == before
