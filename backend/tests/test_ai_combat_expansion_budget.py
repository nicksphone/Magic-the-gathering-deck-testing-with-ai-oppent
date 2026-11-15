"""Decision-wide deterministic combat work; canonical cards and checked outcomes."""
from copy import deepcopy
import random
from unittest.mock import patch

import pytest

from ai.agent import AIAgent, AIDecision
from ai import pending_effects
from game_state.serializers import serialize_match_snapshot
from game_state.state import Step, Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_ai_strategy_fundamentals import position


def allowance(state, seat, limit):
    return pending_effects.decision_projection_scope(state, seat, limit)


def available(charge=False):
    return pending_effects.combat_expansion_available(charge=charge)


def combat(seat=1, blockers=0):
    state, _, _, move = position(seat, [], ['Forest'] * 8,
        reserve=['Sheoldred, the Apocalypse', *(['Llanowar Elves'] * blockers)])
    attacker = move('Sheoldred, the Apocalypse', seat, Zone.BATTLEFIELD)
    defenders = [move('Llanowar Elves', 3-seat, Zone.BATTLEFIELD) for _ in range(blockers)]
    state.turn = 14
    state.step = Step.DECLARE_ATTACKERS
    state.players[3-seat].life = 4
    return state, attacker, defenders


@pytest.mark.parametrize('difficulty,limit', [('master', 128), ('master_plus', 256)])
def test_public_choose_action_initializes_one_finite_allowance(difficulty, limit):
    state, _, _ = combat()
    observed = []

    class InspectingAgent(AIAgent):
        def _choose_action(self, view, moves, seat):
            observed.extend(available(True) for _ in range(limit + 2))
            return AIDecision({'type': 'pass_priority'}, 'scope probe only')

    agent = InspectingAgent(difficulty)
    agent.choose_action(state, RulesEngine().legal_moves(state, 1), 1)
    assert observed == [True] * limit + [False, False]
    observed.clear()
    agent.choose_action(state, RulesEngine().legal_moves(state, 1), 1)
    assert observed == [True] * limit + [False, False]


@pytest.mark.parametrize('difficulty', ['strong', 'normal', 'casual'])
def test_other_public_difficulties_do_not_acquire_a_limit(difficulty):
    state, _, _ = combat()
    observed = []

    class InspectingAgent(AIAgent):
        def _choose_action(self, view, moves, seat):
            observed.extend(available(True) for _ in range(300))
            return AIDecision({'type': 'pass_priority'}, 'scope probe only')

    InspectingAgent(difficulty).choose_action(state, RulesEngine().legal_moves(state, 1), 1)
    assert observed == [True] * 300


def test_nested_scopes_share_remaining_work_and_sticky_exhaustion():
    state, _, _ = combat()
    with allowance(state, 1, 2):
        assert available(True)
        with allowance(deepcopy(state), 2, 256):
            assert available(True)
            assert available()  # Exact capacity can still complete a search.
            assert not available(True)
        assert not available() and not available(True)
    with allowance(state, 1, 1):
        assert available(True) and available()
    assert available(True)


def test_scope_restores_after_exception_without_resetting_outer_allowance():
    state, _, _ = combat()
    with allowance(state, 1, 1):
        with pytest.raises(RuntimeError), allowance(state, 2, 128):
            assert available(True)
            raise RuntimeError('diagnostic')
        assert not available(True)
    assert available(True)


@pytest.mark.parametrize('seat', [1, 2])
def test_zero_budget_cannot_project_an_apparently_winning_attack(seat):
    state, attacker, _ = combat(seat)
    agent = AIAgent('master')
    before = serialize_match_snapshot(state)
    rng, global_rng = state.rng.getstate(), random.getstate()
    assert agent._project_attack_line(state, seat, [attacker])[0].winner == seat
    with allowance(state, seat, 0):
        assert agent._project_attack_line(state, seat, [attacker]) is None
        assert not available()
        assert agent._next_board_attack_wins(state, seat) is None
    assert serialize_match_snapshot(state) == before
    assert state.rng.getstate() == rng and random.getstate() == global_rng


@pytest.mark.parametrize('seat', [1, 2])
def test_attack_and_final_native_block_complete_on_the_exact_last_token(seat):
    state, attacker, _ = combat(seat)
    with allowance(state, seat, 2):
        outcome = AIAgent('master')._project_attack_line(state, seat, [attacker])
        assert outcome is not None and outcome[0].winner == seat
        assert available()
        assert not available(True)


@pytest.mark.parametrize('seat', [1, 2])
def test_incomplete_defense_is_unknown_even_if_one_checked_block_survives(seat):
    state, attacker, defenders = combat(seat, blockers=2)
    agent = AIAgent('master')
    declared = checked_action(state, RulesEngine(), seat, {'type': 'attack', 'attackers': [attacker]})
    RulesEngine().next_step(declared)
    attackers = [{'id': attacker, 'name': state.cards[attacker].name}]
    blockers = [{'id': cid, 'name': state.cards[cid].name} for cid in defenders]
    before = serialize_match_snapshot(declared)
    assert agent._search_block_assignments(declared, attackers, blockers,
        require_complete=True, consider_next_combat=False) is not None
    with allowance(declared, 3-seat, 1):
        assert agent._search_block_assignments(declared, attackers, blockers,
            require_complete=True, consider_next_combat=False) is None
        assert not available()
    assert serialize_match_snapshot(declared) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_attack_plus_defense_compose_instead_of_resetting_local_allowances(seat):
    state, attacker, _ = combat(seat, blockers=2)
    with allowance(state, seat, 1):
        assert AIAgent('master')._project_attack_line(state, seat, [attacker]) is None
        assert not available()


@pytest.mark.parametrize('seat', [1, 2])
def test_public_budget_exhaustion_keeps_a_native_legal_nonpass_fallback(seat):
    state, attacker, _ = combat(seat)
    agent = AIAgent('master', archetype='Ramp')
    before = serialize_match_snapshot(state)
    with allowance(state, seat, 0):
        action = agent.choose_action(state, RulesEngine().legal_moves(state, seat), seat).action
    assert action['type'] == 'attack' and attacker in action['attackers']
    actual = checked_action(state, RulesEngine(), seat, action)
    assert actual.attackers_declared and attacker in actual.attackers
    assert actual.winner is None
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_completed_checked_strategic_incumbent_survives_later_exhaustion(seat):
    state, _, _, _ = position(seat, ['Lava Spike', 'Lightning Bolt'], ['Mountain'] * 3)
    state.turn = 14
    agent = AIAgent('master', archetype='Burn')
    completed = []
    original = agent._strategic_line_score

    def score(view, action, actor, depth):
        if completed:
            while available(True):
                pass
        value = original(view, action, actor, depth)
        if available():
            checked_action(state, RulesEngine(), seat, action)
            completed.append(deepcopy(action))
        return value

    with allowance(state, seat, 8), patch.object(agent, '_strategic_line_score', side_effect=score):
        chosen = agent._strategic_plan_action(state, RulesEngine().legal_moves(state, seat), seat)
    assert completed and chosen == completed[0]
    assert chosen['type'] != 'pass_priority'
    checked_action(state, RulesEngine(), seat, chosen)


@pytest.mark.parametrize('seat', [1, 2])
def test_strong_actual_action_and_checked_outcome_remain_unchanged(seat):
    state, attacker, _ = combat(seat)
    before = serialize_match_snapshot(state)
    action = AIAgent('strong', archetype='Ramp').choose_action(state, RulesEngine().legal_moves(state, seat), seat).action
    assert action['type'] == 'attack' and action['attackers'] == [attacker]
    actual = checked_action(state, RulesEngine(), seat, action)
    assert actual.attackers == [attacker] and actual.winner is None
    assert serialize_match_snapshot(state) == before


def test_recursive_public_choose_action_inherits_the_outer_allowance():
    state, _, _ = combat()
    observations = []

    class NestedAgent(AIAgent):
        nested = False

        def _choose_action(self, view, moves, seat):
            observations.append(available(True))
            if not self.nested:
                self.nested = True
                self.choose_action(view, moves, seat)
            else:
                observations.append(available(True))
            observations.append(available(True))
            return AIDecision({'type': 'pass_priority'}, 'recursive scope probe only')

    with allowance(state, 1, 3):
        NestedAgent('master').choose_action(state, RulesEngine().legal_moves(state, 1), 1)
    assert observations == [True, True, True, False, False]


@pytest.mark.parametrize('seat', [1, 2])
def test_complete_defense_denied_only_in_followup_cannot_return_prior_incumbent(seat):
    state, attacker, defenders = combat(seat, blockers=2)
    state = checked_action(state, RulesEngine(), seat, {'type': 'attack', 'attackers': [attacker]})
    RulesEngine().next_step(state)
    attackers = [{'id': attacker, 'name': state.cards[attacker].name}]
    blockers = [{'id': cid, 'name': state.cards[cid].name} for cid in defenders]
    agent = AIAgent('master')
    # Four native assignments: no block, each Elf separately, both together.
    with allowance(state, 3-seat, 4):
        assert agent._search_block_assignments(state, attackers, blockers,
            require_complete=True, consider_next_combat=False) is not None
        assert available()
    with allowance(state, 3-seat, 4):
        assert agent._search_block_assignments(state, attackers, blockers,
            require_complete=True, consider_next_combat=True) is None
        assert not available()


@pytest.mark.parametrize('seat', [1, 2])
def test_direct_strategic_combat_forecast_cannot_bypass_zero_allowance(seat):
    state, attacker, _ = combat(seat)
    announced = checked_action(state, RulesEngine(), seat, {'type': 'attack', 'attackers': [attacker]})
    agent = AIAgent('master')
    assert agent._forecast_strategic_combat(announced) is not None
    with allowance(announced, seat, 0):
        assert agent._forecast_strategic_combat(announced) is None
        assert agent._complete_strategic_combat_leaf(announced, seat) is None
        assert not available()


@pytest.mark.parametrize('seat', [1, 2])
def test_completed_empty_attack_is_not_unknown_on_the_final_token(seat):
    state, _, _ = combat(seat)
    with allowance(state, seat, 1):
        outcome = AIAgent('master')._project_attack_line(state, seat, [])
        assert outcome is not None and outcome[1] == []
        assert outcome[0].attackers_declared
        assert available()


@pytest.mark.parametrize('seat', [1, 2])
def test_completed_empty_block_is_not_unknown_on_the_final_token(seat):
    state, attacker, defenders = combat(seat, blockers=1)
    state.players[3-seat].life = 20
    state.cards[defenders[0]].tapped = True
    state = checked_action(state, RulesEngine(), seat, {'type': 'attack', 'attackers': [attacker]})
    RulesEngine().next_step(state)
    with allowance(state, 3-seat, 1):
        result = AIAgent('master')._search_block_assignments(state,
            [{'id': attacker}], [{'id': defenders[0]}], require_complete=True, consider_next_combat=False)
        assert result == {}
        assert available()


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('already_denied', [False, True])
def test_already_blocked_setup_is_unknown_without_copy_when_allowance_denied(seat, already_denied):
    from ai import agent as agent_module
    state, attacker, defenders = combat(seat, blockers=1)
    state = checked_action(state, RulesEngine(), seat, {'type': 'attack', 'attackers': [attacker]})
    RulesEngine().next_step(state)
    state = checked_action(state, RulesEngine(), 3-seat, {'type': 'block', 'blocks': {attacker: defenders}})
    assert state.step == Step.DECLARE_BLOCKERS and state.blockers_declared
    before = serialize_match_snapshot(state)
    agent = AIAgent('master')
    with allowance(state, seat, int(already_denied)):
        if already_denied:
            assert available(True) and not available(True)
        with patch.object(agent_module, 'planning_copy', wraps=agent_module.planning_copy) as copies, \
                patch.object(agent, '_finish_combat_projection', wraps=agent._finish_combat_projection) as finish:
            assert agent._setup_combat_forecast(state, seat) is None
        assert not copies.called and not finish.called
        assert not available()
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_ineligible_combat_leaf_does_not_spend_the_last_allowance(seat):
    from ai import agent as agent_module
    state, attacker, _ = combat(seat, blockers=1)
    announced = checked_action(state, RulesEngine(), seat, {'type': 'attack', 'attackers': [attacker]})
    assert not announced.players[3-seat].hand
    before = serialize_match_snapshot(announced)
    with allowance(announced, seat, 1), \
            patch.object(agent_module, 'planning_copy', wraps=agent_module.planning_copy) as copies:
        assert AIAgent('master')._complete_strategic_combat_leaf(announced, seat) is None
        assert available(True)  # Pure rejection must leave the single token untouched.
        assert not copies.called
    assert serialize_match_snapshot(announced) == before
