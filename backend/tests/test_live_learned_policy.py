"""Genuine actor positions plus explicitly synthetic model/provider routing protocols.

The numeric checkpoint and score doubles do not prove fitted weights or strength.
The shared fixture retains its declared C2 mana/zone pose, not a full-game claim.
"""
from copy import deepcopy
from hashlib import sha256
import importlib
import importlib.util
import inspect
import json

import pytest

from ai.agent import AIAgent, AIDecision
from game_state.serializers import serialize_match_snapshot
from rules_engine.engine import RulesEngine
from tests.test_training_reference_context import (
    _expanded, _field, _named_values, _paid_two_bolts,
)
from training import environment as environment_module


def _subject():
    assert importlib.util.find_spec('ai.learned_policy') is not None, (
        'Missing opt-in live learned-policy adapter')
    module = importlib.import_module('ai.learned_policy')
    assert callable(getattr(module, 'bind_live_policy', None))
    return module


def _inputs(view, moves, seat):
    function = getattr(environment_module, 'decision_inputs_from_view', None)
    assert callable(function), 'Missing shared actor-view projection without a new Factory'
    return function(view, moves, seat)


def _agent(binding):
    assert 'learned_binding' in inspect.signature(AIAgent).parameters, (
        'Missing explicit trusted binding; no ambient activation is permitted')
    return AIAgent(learned_binding=binding)


def _native(seat):
    environment, actions, _ = _paid_two_bolts(seat, True)
    view, moves = environment._view(seat)
    assert view.ai_information_player == seat
    return environment, actions, view, moves


def _binding(module, mutation=None):
    # Reuse the original numerical protocol fixture, not an alleged trained model.
    from ai import learned_qv
    from tests.test_learned_qv import blank_checkpoint
    contract = {
        'dataset_version': 'mtg.dataset.v2', 'decision_version': 'mtg.decision.v2',
        'action_version': 'mtg.action.v1:', 'feature_version': 'mtg.features.v2',
        'feature_schema_sha256': '9a1a15d9d41e4585bdb69a87150367df8f6f699c7cde98c84cb6cc07e84eaa06',
        'engine_hash': environment_module._engine_hash(),
    }
    payload = blank_checkpoint(learned_qv)
    payload['contract'] = deepcopy(contract)
    payload['provenance']['updates'] = 1
    payload['provenance']['samples'] = 1
    if mutation == 'stale-engine':
        payload['contract']['engine_hash'] = '0' * 64
    elif mutation == 'zero-updates':
        payload['provenance']['updates'] = 0
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    bound = module.bind_live_policy(raw)
    assert bound.checkpoint_sha256 == sha256(raw).hexdigest()
    assert bound.contract == contract
    detached = bound.contract
    detached['engine_hash'] = '0' * 64
    assert bound.contract == contract
    return bound


def _routing(monkeypatch, actions, seat, calls, mode=None):
    from ai import learned_qv

    def proposals(agent, view, moves, player_id, limit):
        assert view.ai_information_player == player_id == seat
        assert 1 <= limit <= 8
        calls.setdefault('provided_moves', []).append(deepcopy(moves))
        if mode == 'empty-proposals':
            return []
        if mode == 'rejected-proposals':
            return [{**deepcopy(actions[seat]),
                     'targets': {'target_stack_id': 'unannounced-protocol-reference'}}]
        if mode == 'missing-required-choice':
            incomplete = deepcopy(actions[seat])
            incomplete.pop('cost_choice')
            return [incomplete]
        return [deepcopy(actions[seat]), deepcopy(actions[3-seat])]

    class RoutingDecision:
        def predict(self, action):
            assert set(action) == {'version', 'root', 'entities'}
            assert action['version'] == 'mtg.features.v2'
            calls.setdefault('action_packs', []).append(deepcopy(action))
            selected = _field(_field(_expanded(action), 'targets'), 'target_stack_id')
            values = _named_values(selected, 'target_player')
            assert values in ([{'kind': 'text', 'value': 'self'}],
                              [{'kind': 'text', 'value': 'opponent'}])
            q = 1.0 if values[0]['value'] == 'self' else -1.0
            return {'q': float('nan') if mode == 'nonfinite' else q, 'v': 0.0}

    def prepare(policy, state):
        assert set(state) == {'version', 'root', 'entities'}
        assert state['version'] == 'mtg.features.v2'
        calls.setdefault('state_packs', []).append(deepcopy(state))
        return RoutingDecision()

    def fallback(agent, view, moves, player_id):
        assert view.ai_information_player == player_id == seat
        calls['fallback'] = calls.get('fallback', 0) + 1
        return AIDecision(deepcopy(actions[3-seat]), 'Protocol heuristic fallback')

    monkeypatch.setattr(AIAgent, '_strategic_top_actions', proposals)
    monkeypatch.setattr(AIAgent, '_choose_action', fallback)
    monkeypatch.setattr(learned_qv.QVPolicy, 'prepare', prepare)


@pytest.mark.parametrize('seat', [1, 2])
def test_shared_projection_matches_actual_environment_observe_prompts_context(seat):
    environment, _, view, moves = _native(seat)
    expected = (environment.observe(seat), environment.prompts(seat),
                environment.decision_context(seat))
    before = environment.snapshot()
    view_before, moves_before = serialize_match_snapshot(view), deepcopy(moves)
    actual = _inputs(view, moves, seat)
    assert actual == expected
    assert actual is not expected
    assert moves == moves_before and serialize_match_snapshot(view) == view_before
    assert environment.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
def test_shared_projection_uses_supplied_moves_without_factory_or_relegalizing(seat, monkeypatch):
    from game_state.state import MatchFactory
    environment, _, view, moves = _native(seat)
    expected = (environment.observe(seat), environment.prompts(seat),
                environment.decision_context(seat))

    def forbidden(*args, **kwargs):
        pytest.fail('Projection must not create a match or recompute legal moves')

    monkeypatch.setattr(MatchFactory, 'from_decks', forbidden)
    monkeypatch.setattr(RulesEngine, 'legal_moves', forbidden)
    assert _inputs(view, moves, seat) == expected
    with pytest.raises(ValueError):
        _inputs(environment._state, moves, seat)


@pytest.mark.parametrize('seat', [1, 2])
def test_shared_projection_ignores_hidden_order_rng_and_private_log(seat):
    environment, _, view, moves = _native(seat)
    expected = _inputs(view, moves, seat)
    for player in environment._state.players.values():
        player.library.reverse()
    environment._state.rng.random()
    environment._state.log.append('PRIVATE-LIVE-ROUTING-CANARY')
    changed_view, changed_moves = environment._view(seat)
    assert _inputs(changed_view, changed_moves, seat) == expected
    observation, _, context = expected
    assert 'hand' not in observation['players'][str(3-seat)]
    assert all('library' not in player for player in observation['players'].values())
    assert set(context) == {'version', 'seat', 'stack'}
    assert 'PRIVATE-LIVE-ROUTING-CANARY' not in json.dumps(expected)


@pytest.mark.parametrize('seat', [1, 2])
def test_none_binding_preserves_heuristic_action_without_model_work(seat, monkeypatch):
    environment, actions, _, moves = _native(seat)
    calls = {}

    def fallback(agent, view, supplied, player_id):
        calls['fallback'] = calls.get('fallback', 0) + 1
        assert view.ai_information_player == player_id == seat
        return AIDecision(deepcopy(actions[3-seat]), 'Unchanged heuristic')

    def forbidden(*args, **kwargs):
        pytest.fail('The default must not generate or score learned candidates')

    monkeypatch.setattr(AIAgent, '_choose_action', fallback)
    monkeypatch.setattr(AIAgent, '_strategic_top_actions', forbidden)
    before = environment.snapshot()
    agent = _agent(None)
    decision = agent.choose_action(environment._state, moves, seat)
    assert decision.action == actions[3-seat] and decision.reasoning == 'Unchanged heuristic'
    assert calls == {'fallback': 1}
    assert environment.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
def test_bound_routing_scores_only_public_features_and_returns_checked_action(seat, monkeypatch):
    module = _subject()
    environment, actions, _, moves = _native(seat)
    binding = _binding(module)
    calls = {}
    _routing(monkeypatch, actions, seat, calls)
    before = environment.snapshot()
    decision = _agent(binding).choose_action(environment._state, moves, seat)
    expected = {**actions[seat], 'from_exile': False,
                'from_library': False, 'from_graveyard': False}
    assert decision.action == expected
    assert calls.get('fallback', 0) == 0
    assert len(calls['state_packs']) == 1 and len(calls['action_packs']) == 2
    assert calls['provided_moves'] == [moves]
    assert environment.snapshot() == before
    environment.lookup(decision.action, seat)
    environment.step(decision.action, seat)
    assert environment.observe(seat)['players'][str(seat)]['mana_pool'].get('U', 0) == 0


@pytest.mark.parametrize('failure', ['empty-proposals', 'rejected-proposals',
                                   'missing-required-choice',
                                   'unsupported-encoding', 'nonfinite',
                                   'stale-engine', 'zero-updates'])
def test_invalid_binding_or_unusable_candidates_preserve_safe_heuristic(failure, monkeypatch):
    module = _subject()
    environment, actions, _, moves = _native(1)
    before = environment.snapshot()
    if failure in {'stale-engine', 'zero-updates'}:
        with pytest.raises(ValueError):
            _binding(module, failure)
        assert environment.snapshot() == before
        return
    binding = _binding(module)
    calls = {}
    _routing(monkeypatch, actions, 1, calls, failure)
    if failure == 'unsupported-encoding':
        from training import decision_frame

        def unsupported(*args, **kwargs):
            raise ValueError('Explicit protocol unsupported encoding')

        monkeypatch.setattr(decision_frame, 'encode_action', unsupported)
    decision = _agent(binding).choose_action(environment._state, moves, 1)
    assert decision.action == actions[2]
    assert calls.get('fallback', 0) == 1
    assert environment.snapshot() == before
    environment.lookup(decision.action, 1)
