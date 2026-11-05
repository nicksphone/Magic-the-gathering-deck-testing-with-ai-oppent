"""Sticky denial stops speculation, not native fallback or the learned shortlist."""
from copy import deepcopy
import random

import pytest

from ai import agent as agent_module, pending_effects
from ai.agent import AIAgent
from ai.action_contract import complete_action
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import checked_action
from tests.test_ai_strategy_fundamentals import position, settle


def available(charge=False):
    return pending_effects.combat_expansion_available(charge=charge)


def deny():
    while available(True):
        pass


def fixture(seat=1):
    state, cards, _, move = position(seat, ['Lava Spike', 'Monastery Swiftspear'],
                                    ['Mountain'] * 2, reserve=['Lightning Bolt'])
    state.turn = 10
    return state, cards, move


def ordered(agent, monkeypatch):
    monkeypatch.setattr(agent, '_rank_moves', lambda _s, moves, _p, **kw: moves)


@pytest.mark.parametrize('method', ['line', 'state', 'stack'])
def test_private_entry_denial_precedes_all_work(monkeypatch, method):
    state, _, _ = fixture()
    ai = AIAgent('master')
    calls = []
    monkeypatch.setattr(agent_module, 'planning_copy', lambda *_: calls.append('copy'))
    monkeypatch.setattr(ai, '_complete_strategic_combat_leaf', lambda *_: calls.append('leaf'))
    with pending_effects.decision_projection_scope(state, 1, 0):
        deny()
        with pytest.raises(pending_effects.UncertainSimulation):
            if method == 'line':
                ai._strategic_line_score(state, {'type': 'pass_priority'}, 1, 0)
            elif method == 'state':
                ai._strategic_state_score(state, 1, 0, 0.)
            else:
                ai._stack_two_ply_value(state, 1)
    assert calls == []


@pytest.mark.parametrize('seat', [1, 2])
def test_root_checks_denial_before_extra_preparation(monkeypatch, seat):
    state, _, _ = fixture(seat)
    ai = AIAgent('master')
    ordered(ai, monkeypatch)
    calls = []

    def rank(_s, moves, _p, **kw):
        deny()
        return moves

    monkeypatch.setattr(ai, '_rank_moves', rank)
    monkeypatch.setattr(ai, '_materialize_action', lambda *a: calls.append(a) or a[1])
    with pending_effects.decision_projection_scope(state, seat, 0):
        assert ai._strategic_plan_action(state, ai.engine.legal_moves(state, seat), seat) is None
    assert calls == []


@pytest.mark.parametrize('seat', [1, 2])
def test_checked_incumbent_survives_later_denial(monkeypatch, seat):
    state, cards, _ = fixture(seat)
    ai = AIAgent('master')
    ordered(ai, monkeypatch)
    moves = ai.engine.legal_moves(state, seat)
    cast = next(m for m in moves if m.get('card_id') == cards['Monastery Swiftspear'])
    moves = [cast, {'type': 'pass_priority'}]
    incumbent = complete_action(ai._materialize_action(state, cast, seat))
    checked_action(state, ai.engine, seat, incumbent)
    calls = []

    def score(_s, move, _p, depth):
        calls.append(move)
        if len(calls) == 1:
            return 1.
        deny()
        raise pending_effects.UncertainSimulation('denied second line')

    monkeypatch.setattr(ai, '_strategic_line_score', score)
    with pending_effects.decision_projection_scope(state, seat, 0):
        assert complete_action(ai._strategic_plan_action(state, moves, seat)) == incumbent
    assert len(calls) == 2


def test_root_does_not_hide_nonbudget_uncertainty(monkeypatch):
    state, _, _ = fixture()
    ai = AIAgent('master')
    ordered(ai, monkeypatch)

    def score(*a, **kw):
        raise pending_effects.UncertainSimulation('unrelated uncertainty')

    monkeypatch.setattr(ai, '_strategic_line_score', score)
    with pending_effects.decision_projection_scope(state, 1, 0):
        with pytest.raises(pending_effects.UncertainSimulation, match='unrelated'):
            ai._strategic_plan_action(state, ai.engine.legal_moves(state, 1), 1)


@pytest.mark.parametrize('raises', [False, True])
def test_line_denial_during_execution_is_not_a_bad_numeric_score(monkeypatch, raises):
    state, _, _ = fixture()
    ai = AIAgent('master')

    def execute(*a, **kw):
        deny()
        if raises:
            raise pending_effects.UncertainSimulation('execution denied')

    monkeypatch.setattr(agent_module, 'simulation_take_action', execute)
    with pending_effects.decision_projection_scope(state, 1, 0):
        with pytest.raises(pending_effects.UncertainSimulation):
            ai._strategic_line_score(state, {'type': 'pass_priority'}, 1, 0)


@pytest.mark.parametrize('stage', ['leaf', 'position', 'stack'])
def test_line_stops_after_denial_in_each_consuming_callee(monkeypatch, stage):
    state, _, _ = fixture()
    ai = AIAgent('master')
    calls = []

    def leaf(*a):
        calls.append('leaf')
        if stage == 'leaf':
            deny()
        return None

    def position_score(*a):
        calls.append('position')
        if stage == 'position':
            deny()
        return 0.

    def stack(*a):
        calls.append('stack')
        if stage == 'stack':
            deny()
        return 0.

    monkeypatch.setattr(ai, '_complete_strategic_combat_leaf', leaf)
    monkeypatch.setattr(ai, '_strategic_position_score', position_score)
    monkeypatch.setattr(ai, '_stack_two_ply_value', stack)
    monkeypatch.setattr(ai, '_instant_value_reservation', lambda *a: calls.append('reservation') or 0.)
    with pending_effects.decision_projection_scope(state, 1, 0):
        with pytest.raises(pending_effects.UncertainSimulation):
            ai._strategic_line_score(state, {'type': 'pass_priority'}, 1, 1)
    assert calls == ['leaf', 'position', 'stack'][:['leaf', 'position', 'stack'].index(stage) + 1]


@pytest.mark.parametrize('raises', [False, True])
def test_recursive_denial_stops_materialization_without_swallowing(monkeypatch, raises):
    state, _, _ = fixture()
    ai = AIAgent('master')
    ordered(ai, monkeypatch)
    calls = []

    def materialize(_s, move, _p):
        calls.append(move)
        deny()
        if raises:
            raise pending_effects.UncertainSimulation('materialization denied')
        return {'type': 'pass_priority'}

    monkeypatch.setattr(ai, '_materialize_action', materialize)
    monkeypatch.setattr(ai, '_strategic_position_score', lambda *a: 0.)
    with pending_effects.decision_projection_scope(state, 1, 0):
        with pytest.raises(pending_effects.UncertainSimulation):
            ai._strategic_state_score(state, 1, 1, 0.)
    assert len(calls) == 1


def stack_fixture(seat=1):
    state, _, move = fixture(seat)
    cid = move('Lightning Bolt', 3-seat, Zone.HAND)
    state.priority_player = 3-seat
    state.players[3-seat].mana_pool = {'R': 1}
    state = checked_action(state, AIAgent().engine, 3-seat,
        {'type': 'cast_spell', 'card_id': cid, 'targets': {'target_player': seat}})
    return state


@pytest.mark.parametrize('reply', [False, True])
def test_stack_execution_and_reply_catches_propagate_sticky_denial(monkeypatch, reply):
    state = stack_fixture()
    ai = AIAgent('master')
    calls = []
    execute = agent_module.simulation_take_action

    def action(engine, sim, seat, move, **kw):
        calls.append(move)
        if len(calls) == (2 if reply else 1):
            deny()
            raise pending_effects.UncertainSimulation('native execution denied')
        return execute(engine, sim, seat, move, **kw)

    monkeypatch.setattr(ai, '_strategic_top_actions', lambda *a, **kw: [{'type': 'pass_priority'}])
    monkeypatch.setattr(agent_module, 'simulation_take_action', action)
    with pending_effects.decision_projection_scope(state, state.priority_player, 0):
        with pytest.raises(pending_effects.UncertainSimulation):
            ai._stack_two_ply_value(state, 1)
    assert len(calls) == (2 if reply else 1)


@pytest.mark.parametrize('stage', ['entry', 'rank', 'materialize'])
def test_opted_in_shortlist_aborts_at_boundary(monkeypatch, stage):
    state, _, _ = fixture()
    ai = AIAgent('master')
    calls = []

    def rank(_s, moves, _p, **kw):
        calls.append('rank')
        if stage == 'rank':
            deny()
        return moves

    def materialize(_s, move, _p):
        calls.append('materialize')
        deny()
        return move

    monkeypatch.setattr(ai, '_rank_moves', rank)
    monkeypatch.setattr(ai, '_materialize_action', materialize)
    with pending_effects.decision_projection_scope(state, 1, 0):
        if stage == 'entry':
            deny()
        with pytest.raises(pending_effects.UncertainSimulation):
            ai._strategic_top_actions(state, [{'type': 'pass_priority'}], 1, 2, _speculative=True)
    assert calls == {'entry': [], 'rank': ['rank'], 'materialize': ['rank', 'materialize']}[stage]


@pytest.mark.parametrize('seat', [1, 2])
def test_exact_last_token_and_empty_shortlist_remain_completed(monkeypatch, seat):
    state, _, _ = fixture(seat)
    ai = AIAgent('master')
    with pending_effects.decision_projection_scope(state, seat, 1):
        assert available(True) and available()
        assert ai._strategic_top_actions(state, [], seat, 2, _speculative=True) == []
        value = ai._strategic_line_score(state, {'type': 'pass_priority'}, seat, 0)
        assert isinstance(value, float) and available()
        assert ai._stack_two_ply_value(state, seat) == 0.


def test_ordinary_invalid_execution_keeps_existing_penalty_and_skip(monkeypatch):
    state, _, _ = fixture()
    ai = AIAgent('master')

    def unknown(*a, **kw):
        raise pending_effects.UncertainSimulation('ordinary unknown')

    monkeypatch.setattr(agent_module, 'simulation_take_action', unknown)
    assert ai._strategic_line_score(state, {'type': 'pass_priority'}, 1, 0) == -9999.
    assert ai._strategic_state_score(state, 1, 1, 7.) == 7.
    assert ai._stack_two_ply_value(stack_fixture(), 1) == 0.


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_learned_adapter_uses_default_shortlist_after_denial(seat):
    # Synthetic in-memory scores only; no checkpoint, model body or NN inference.
    from ai import learned_policy
    from ai.information import decision_view

    state, _, _ = fixture(seat)
    ai = AIAgent('master', 'Burn')
    calls = []

    class Scores:
        def prepare(self, pack):
            calls.append('prepare')
            return self

        def predict(self, pack):
            calls.append('predict')
            return {'q': 0., 'v': 0.}

    contract = learned_policy._current_contract()
    binding = learned_policy.LivePolicyBinding(Scores(), 'synthetic-no-checkpoint',
                                               tuple(sorted(contract.items())))
    moves = ai.engine.legal_moves(state, seat)
    view, supplied = decision_view(state, seat, moves)
    before = serialize_match_snapshot(state)
    with pending_effects.decision_projection_scope(state, seat, 0):
        deny()
        action = learned_policy.choose_learned_action(binding, ai, view, supplied, seat,
            admit=lambda act: checked_action(state, ai.engine, seat, act))
        assert not available()
    assert action is not None and calls.count('prepare') == 1 and 'predict' in calls
    checked_action(state, ai.engine, seat, action)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['master', 'strong'])
def test_native_nonpass_lethal_fallback_hidden_and_rng_purity(seat, difficulty):
    state, cards, _ = fixture(seat)
    state.players[3-seat].life = 3
    before = serialize_match_snapshot(state)
    rng = state.rng.getstate(), random.getstate()
    actions = []
    for hidden in (False, True):
        root = deepcopy(state)
        if hidden:
            for player in root.players.values():
                player.library.reverse()
        ai = AIAgent(difficulty, 'Burn')
        moves = ai.engine.legal_moves(root, seat)
        with pending_effects.decision_projection_scope(root, seat, 0):
            deny()
            action = ai.choose_action(root, moves, seat).action
        assert action['type'] == 'cast_spell' and action['card_id'] == cards['Lava Spike']
        result = settle(checked_action(root, ai.engine, seat, action), seat, 'Burn', difficulty)
        assert result.winner == seat
        actions.append(action)
    assert actions[0] == actions[1]
    assert serialize_match_snapshot(state) == before
    assert (state.rng.getstate(), random.getstate()) == rng


def test_denied_speculation_does_not_mutate_agent_histories(monkeypatch):
    state, _, _ = fixture()
    ai = AIAgent('master')
    ai._main_pass_signature_counts = {('sentinel',): 2}
    ai._knowledge_usage = {'seen': set(), 'counts': {'persisted': 0, 'fallback': 0,
        'opaque': 0, 'fallback_reasons': {}}}
    before = deepcopy((ai._main_pass_signature_counts, ai._knowledge_usage))
    with pending_effects.decision_projection_scope(state, 1, 0):
        deny()
        with pytest.raises(pending_effects.UncertainSimulation):
            ai._strategic_top_actions(state, ai.engine.legal_moves(state, 1), 1, 2,
                                      _speculative=True)
    assert (ai._main_pass_signature_counts, ai._knowledge_usage) == before


@pytest.mark.parametrize('terminal_leaf', [False, True])
def test_reservation_denial_is_unknown_before_more_work(monkeypatch, terminal_leaf):
    state, _, _ = fixture()
    ai = AIAgent('master')
    calls = []
    monkeypatch.setattr(ai, '_complete_strategic_combat_leaf',
                        lambda *a: state if terminal_leaf else None)
    monkeypatch.setattr(ai, '_strategic_position_score', lambda *a: 0.)
    monkeypatch.setattr(ai, '_stack_two_ply_value', lambda *a: 0.)

    def reservation(*a):
        deny()
        return 0.

    monkeypatch.setattr(ai, '_instant_value_reservation', reservation)
    monkeypatch.setattr(agent_module, 'selection_activation_plan',
                        lambda *a: calls.append('plan'))
    with pending_effects.decision_projection_scope(state, 1, 0):
        with pytest.raises(pending_effects.UncertainSimulation):
            ai._strategic_line_score(state, {'type': 'pass_priority'}, 1, 0)
    assert calls == []


def test_default_and_aborted_speculation_have_explicit_bookkeeping_deltas(monkeypatch):
    state, cards, _ = fixture()
    deltas = []
    for speculative in (False, True):
        ai = AIAgent('master')
        ai._knowledge_usage = {'seen': set(), 'counts': {'persisted': 0, 'fallback': 0,
            'opaque': 0, 'fallback_reasons': {}}}
        materialize = ai._materialize_action

        def observed(s, move, pid):
            # Real mutable bookkeeping at a counted dependency boundary. This is
            # a control-flow witness, not a claim every materializer does both.
            ai._should_force_conversion_after_repeated_main_pass(s, pid)
            ai._spell_tags(s.cards[cards['Lava Spike']])
            return materialize(s, move, pid)

        monkeypatch.setattr(ai, '_materialize_action', observed)
        with pending_effects.decision_projection_scope(state, 1, 0):
            deny()
            if speculative:
                with pytest.raises(pending_effects.UncertainSimulation):
                    ai._strategic_top_actions(state, [{'type': 'pass_priority'}], 1, 2,
                                              _speculative=True)
            else:
                assert ai._strategic_top_actions(state, [{'type': 'pass_priority'}], 1, 2)
        deltas.append((sum(ai._main_pass_signature_counts.values()),
                       sum(ai._knowledge_usage['counts'][k]
                           for k in ('persisted', 'fallback', 'opaque'))))
    # Default materialization recursively chooses a main-phase continuation;
    # count the actual bookkeeping, not just this wrapper's first increment.
    assert deltas == [(3, 2), (0, 0)]
