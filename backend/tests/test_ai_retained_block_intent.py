"""Canonical native combat: execute the block plan that ranking evaluated."""
from copy import deepcopy
import random

import pytest

from ai.agent import AIAgent
from ai.action_contract import complete_action
from ai.declaration_policy import finalize_declaration
from ai.pending_effects import combat_expansion_available, decision_projection_scope
from game_state.serializers import serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.combat_canonical_022 import canonical_card, canonical_entry


def declared_combat(seat, life):
    state = MatchFactory.from_decks(
        [canonical_entry('Forest', 60)], [canonical_entry('Forest', 60)], seed=7631,
    )
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.turn = 5
    state.active_player = state.priority_player = 3 - seat
    state.step = Step.DECLARE_ATTACKERS
    state.players[seat].life = life
    for cid, name, owner in [('attacker', 'Hill Giant', 3 - seat),
                             ('blocker', 'Grizzly Bears', seat)]:
        card = canonical_card(name, id=cid, owner=owner, controller=owner,
                              zone=Zone.BATTLEFIELD, summoning_sick=False)
        state.cards[cid] = card
        state.players[owner].battlefield.append(cid)
    rules = RulesEngine()
    state = checked_action(state, rules, 3 - seat, {
        'type': 'attack', 'attackers': ['attacker'],
        'attack_targets': {'attacker': f'player:{seat}'}, 'bands': [],
    })
    for _ in range(4):
        if state.step == Step.DECLARE_BLOCKERS:
            break
        state = checked_action(state, rules, state.priority_player, {'type': 'pass_priority'})
    assert state.step == Step.DECLARE_BLOCKERS and state.priority_player == seat
    return state, rules


def end_combat(state, rules, action):
    state = checked_action(state, rules, state.priority_player, action)
    for _ in range(8):
        if state.winner is not None or state.step == Step.END_COMBAT:
            return state
        state = checked_action(state, rules, state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('Checked vanilla combat did not finish')


@pytest.mark.parametrize('seat', [1, 2])
def test_ranked_safe_empty_plan_is_not_replaced_after_denial(seat):
    state, rules = declared_combat(seat, 20)
    agent = AIAgent('master', archetype='Control')
    legal = rules.legal_moves(state, seat)
    before, offered, rng = serialize_match_snapshot(state), deepcopy(legal), random.getstate()
    with decision_projection_scope(state, seat, 1):
        ranked = agent._rank_moves(state, legal, seat)
        assert not combat_expansion_available()
        selected = next(move for move in ranked if move['type'] == 'block')
        action = complete_action(finalize_declaration(
            state, agent._materialize_action(state, selected, seat)))
    actual = end_combat(state, rules, action)
    assert actual.players[seat].life == 17
    assert actual.cards['blocker'].zone == Zone.BATTLEFIELD
    assert action == {'type': 'block', 'blocks': {}}
    assert serialize_match_snapshot(state) == before and legal == offered and random.getstate() == rng


@pytest.mark.parametrize('seat', [1, 2])
def test_retention_does_not_preserve_partial_search_known_to_lose(seat):
    state, rules = declared_combat(seat, 3)
    agent = AIAgent('master', archetype='Control')
    with decision_projection_scope(state, seat, 1):
        ranked = agent._rank_moves(state, rules.legal_moves(state, seat), seat)
        assert not combat_expansion_available()
        selected = next(move for move in ranked if move['type'] == 'block')
        action = complete_action(finalize_declaration(
            state, agent._materialize_action(state, selected, seat)))
    actual = end_combat(state, rules, action)
    assert actual.winner is None and actual.players[seat].life == 3
    assert actual.cards['blocker'].zone == Zone.GRAVEYARD
    assert action == {'type': 'block', 'blocks': {'attacker': ['blocker']}}


@pytest.mark.parametrize('seat', [1, 2])
def test_complete_empty_block_action_remains_empty(seat):
    state, rules = declared_combat(seat, 20)
    declared = {'type': 'block', 'blocks': {}}
    original = deepcopy(declared)
    with decision_projection_scope(state, seat, 0):
        assert not combat_expansion_available(charge=True)
        actual = complete_action(finalize_declaration(
            state, AIAgent('master')._materialize_action(state, declared, seat)))
    assert actual == {'type': 'block', 'blocks': {}}
    assert declared == original


@pytest.mark.parametrize('seat', [1, 2])
def test_empty_generic_descriptor_keeps_legacy_block_selection(seat):
    state, rules = declared_combat(seat, 20)
    descriptor = next(move for move in rules.legal_moves(state, seat) if move['type'] == 'block')
    offered = {**descriptor, 'blocks': {}}
    before = deepcopy(offered)
    with decision_projection_scope(state, seat, 0):
        assert not combat_expansion_available(charge=True)
        materialized = AIAgent('master')._materialize_action(state, offered, seat)
    assert '_ai_retained_blocks' not in materialized
    action = complete_action(finalize_declaration(state, materialized))
    assert action == {'type': 'block', 'blocks': {'attacker': ['blocker']}}
    actual = end_combat(state, rules, action)
    assert actual.players[seat].life == 20
    assert actual.cards['blocker'].zone == Zone.GRAVEYARD
    assert offered == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('life', [3, 20])
def test_public_choice_keeps_survival_and_safe_material_with_shared_denial(seat, life):
    state, rules = declared_combat(seat, life)
    legal = rules.legal_moves(state, seat)
    before, offered, rng = serialize_match_snapshot(state), deepcopy(legal), random.getstate()
    with decision_projection_scope(state, seat, 1):
        decision = AIAgent('master', archetype='Control').choose_action(state, legal, seat)
        assert not combat_expansion_available()
    assert '_ai_retained_blocks' not in decision.action
    action = complete_action(decision.action)
    actual = end_combat(state, rules, action)
    assert actual.winner is None
    assert actual.players[seat].life == (3 if life == 3 else 17)
    assert actual.cards['blocker'].zone == (Zone.GRAVEYARD if life == 3 else Zone.BATTLEFIELD)
    assert serialize_match_snapshot(state) == before and legal == offered and random.getstate() == rng
