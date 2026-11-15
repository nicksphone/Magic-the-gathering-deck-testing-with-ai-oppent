"""Canonical declared boards; synthetic Q routing, not fitted-model strength.

Real proposal generation, actor projection, choices, native admission and combat
forecasts stay intact. No private game roots or fitted checkpoints are loaded.
"""
from copy import deepcopy
import random

import pytest

from ai import learned_policy, learned_qv
from ai.action_contract import complete_action
from ai.agent import AIAgent
from ai.declaration_policy import finalize_declaration
from ai.information import decision_view, is_unknown
from game_state.serializers import serialize_match_snapshot
from game_state.state import Step, Zone
from rules_engine import action_validation
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from tests.test_learned_declared_combat_guard import _declared_combat
from tests.test_live_learned_policy import _binding
from tests.test_training_reference_context import _expanded, _field


RULES = RulesEngine()
EMPTY = {'type': 'block', 'blocks': {}}


def board(seat, *, life=20):
    state, attacker, blocker, _ = _declared_combat(seat)
    state.players[seat].life = life  # Declared old-board life pose, not played history.
    # A real hidden canonical card exercises masking, not invented printed facts.
    enemy = state.players[3-seat]
    cid = enemy.library.pop()
    enemy.hand.append(cid)
    state.cards[cid].move_to_zone(Zone.HAND)
    return state, attacker, blocker


def shortlist(state, seat, *, agent=None, limit=8):
    moves = RULES.legal_moves(deepcopy(state), seat)
    before, old_moves, rng = serialize_match_snapshot(state), deepcopy(moves), random.getstate()
    view, supplied = decision_view(state, seat, moves)
    old_view = serialize_match_snapshot(view)
    actions = (agent or AIAgent())._strategic_top_actions(view, supplied, seat, limit)
    assert serialize_match_snapshot(state) == before and moves == old_moves
    assert serialize_match_snapshot(view) == old_view and random.getstate() == rng
    assert all(is_unknown(view.cards[cid]) for cid in view.players[3-seat].hand)
    return actions


@pytest.mark.parametrize('seat', [1, 2])
def test_real_shortlist_offers_explicit_empty_alongside_heuristic_block(seat):
    state, attacker, blocker = board(seat)
    actions = shortlist(state, seat)
    assert any(a['type'] == 'block' and finalize_declaration(state, a).get('blocks') == {attacker: [blocker]}
               for a in actions)
    assert EMPTY in actions, 'Explicit checked block:{} is missing (pass is not its identity)'
    assert sum(a == EMPTY for a in actions) == 1 and len(actions) <= 9
    current = complete_action(finalize_declaration(state, EMPTY))
    result = checked_action(state, RULES, seat, current)
    assert result.blockers_declared and result.blocks == {}


def synthetic_scores(monkeypatch):
    """In-memory protocol checkpoint + ranking double; no fitted payload/NN."""
    scored = []

    class Scores:
        def predict(self, pack):
            root = _expanded(pack)
            kind = _field(root, 'type')['value']
            empty = kind == 'block' and not _field(root, 'blocks')['items']
            scored.append((kind, empty))
            return {'q': 0.95 if empty else -0.5 if kind == 'block' else 0.1, 'v': 0.0}

    monkeypatch.setattr(learned_qv.QVPolicy, 'prepare', lambda _policy, _pack: Scores())
    return scored


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('lethal', [False, True])
def test_public_learned_route_checks_empty_and_keeps_known_loss_guard(monkeypatch, seat, lethal):
    state, _, _ = board(seat, life=2 if lethal else 20)
    scored = synthetic_scores(monkeypatch)
    binding = _binding(learned_policy)  # Existing numerical protocol fixture, NOT a fit.
    agent = AIAgent(learned_binding=binding)
    moves = RULES.legal_moves(deepcopy(state), seat)
    before, old_moves, rng = serialize_match_snapshot(state), deepcopy(moves), random.getstate()
    admitted = []
    delegate = action_validation.checked_action

    def audited(root, engine, actor, action):
        result = delegate(root, engine, actor, action)
        if root is state:
            admitted.append(deepcopy(action))
        return result

    monkeypatch.setattr(action_validation, 'checked_action', audited)
    decision = agent.choose_action(state, moves, seat)
    assert 'Q ranking' in decision.reasoning
    assert ('block', True) in scored and ('block', False) in scored
    assert any(a['type'] == 'block' and a['blocks'] == {} for a in admitted)
    assert decision.action['type'] == 'block'
    assert bool(decision.action['blocks']) is lethal
    checked_action(state, RULES, seat, decision.action)
    assert serialize_match_snapshot(state) == before and moves == old_moves
    assert random.getstate() == rng


@pytest.mark.parametrize('seat', [1, 2])
def test_unbound_default_remains_heuristic_without_scoring(monkeypatch, seat):
    state, _, _ = board(seat)

    def forbidden(*_args, **_kwargs):
        raise AssertionError('Unbound NoNN default must not use learned route')

    monkeypatch.setattr(learned_policy, 'choose_learned_action', forbidden)
    before, rng = serialize_match_snapshot(state), random.getstate()
    moves = RULES.legal_moves(deepcopy(state), seat)
    decision = AIAgent().choose_action(state, moves, seat)
    assert decision.action['type'] == 'block' and decision.action['blocks']
    assert serialize_match_snapshot(state) == before and random.getstate() == rng


@pytest.mark.parametrize('seat', [1, 2])
def test_mandatory_blocks_cannot_admit_explicit_empty(seat):
    # Existing retained requirement-card operands, not rewritten Bears Oracle.
    # Unlike the full-printing positive boards, this is a legacy rule negative.
    import json
    from pathlib import Path
    from tests.test_linked_damage_targets import raw_card
    from tests.test_ai_block_retention import position, declare
    state, _, _, _ = position(seat, [], ['Grizzly Bears'])
    path = Path(__file__).parent / 'fixtures/combat_payments_requirements.json'
    raw = next(row for row in json.loads(path.read_text()) if row['name'] == 'Taunting Elf')
    elf = raw_card(state, raw, 3-seat, Zone.BATTLEFIELD)
    elf.summoning_sick = False
    state = declare(state, seat, [elf.id])
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RULES, seat, EMPTY)
    for proposal in shortlist(state, seat):
        action = complete_action(finalize_declaration(state, proposal))
        admitted = checked_action(state, RULES, seat, action)
        assert admitted.blocks, 'Mandatory declarations must not admit empty blocks'
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('ordering', ['first', 'last', 'no-pass'])
def test_budget_retains_nonempty_and_pass_with_full_materialized_list(monkeypatch, seat, ordering):
    state, attacker, blocker = board(seat)
    agent = AIAgent()
    original = agent._rank_moves

    def ranked(view, moves, actor):
        actual = original(view, moves, actor)
        block = next(a for a in actual if a['type'] == 'block')
        wait = next(a for a in actual if a['type'] == 'pass_priority')
        # Budget-only ordering double; all entries still use real materialization.
        if ordering == 'no-pass':
            return [deepcopy(block) for _ in range(8)]
        padding = [deepcopy(wait) for _ in range(7)]
        return [block, *padding] if ordering == 'first' else [*padding, block]

    monkeypatch.setattr(agent, '_rank_moves', ranked)
    actions = shortlist(state, seat, agent=agent)
    assert len(actions) <= 9 and EMPTY in actions
    assert any(a['type'] == 'block' and finalize_declaration(state, a).get('blocks') == {attacker: [blocker]}
               for a in actions)
    assert any(a['type'] == 'pass_priority' for a in actions)


@pytest.mark.parametrize('seat', [1, 2])
def test_other_phase_and_after_declaration_do_not_offer_new_block(seat):
    state, _, _ = board(seat)
    after = checked_action(state, RULES, seat, EMPTY)
    assert not any(a['type'] == 'block' for a in shortlist(after, seat))
    from tests.test_ai_strategy_fundamentals import position
    main, _, _, _ = position(seat, [], [])
    assert main.step == Step.PRECOMBAT_MAIN
    assert not any(a['type'] == 'block' for a in shortlist(main, seat))


@pytest.mark.parametrize('seat', [1, 2])
def test_single_slot_preserves_heuristic_and_bound(seat):
    state, _, _ = board(seat)
    actions = shortlist(state, seat, limit=1)
    assert len(actions) <= 2
    assert any(a['type'] == 'block' and a.get('blocks') for a in actions)


@pytest.mark.parametrize('seat', [1, 2])
def test_empty_descriptor_still_uses_existing_generic_materializer(seat):
    state, _, _ = board(seat)
    agent = AIAgent()
    moves = RULES.legal_moves(deepcopy(state), seat)
    descriptor = next(a for a in moves if a['type'] == 'block')
    before = serialize_match_snapshot(state)
    assert agent._materialize_action(state, {**descriptor, 'blocks': {}}, seat)['blocks']
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_active_stack_does_not_receive_new_empty_final_intent(seat):
    from tests.test_learned_tactical_guard import _cast
    state, attacker, _, _ = _declared_combat(seat, response=True)
    cid = next(cid for cid in state.players[seat].hand if state.cards[cid].name == 'Lightning Bolt')
    action = _cast(state, {'Lightning Bolt': cid}, seat, 'Lightning Bolt', {'target_card_id': attacker})
    stack = checked_action(state, RULES, seat, action)
    assert stack.stack and stack.step == Step.DECLARE_BLOCKERS
    assert EMPTY not in shortlist(stack, seat)


@pytest.mark.parametrize('seat', [1, 2])
def test_returned_empty_blocks_are_fresh_per_invocation(seat):
    state, _, _ = board(seat)
    agent = AIAgent()
    first = shortlist(state, seat, agent=agent)
    empty = next(a for a in first if a == EMPTY)
    empty['blocks']['unannounced-test-reference'] = ['not-a-native-choice']
    assert EMPTY in shortlist(state, seat, agent=agent)
