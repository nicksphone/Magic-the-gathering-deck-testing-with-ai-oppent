"""Baseline-only memo contracts; synthetic controls and canonical native states."""
import ast
from copy import deepcopy
import inspect
from pathlib import Path
import pickle
import random
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ai import pending_effects as p
from game_state.serializers import serialize_match_snapshot


class NativeReferenceNamespace(unittest.TestCase):
    def state(self):
        return SimpleNamespace(turn=1, rng=random.Random(1719))

    def native(self, state, actor=1, policy=None):
        wrapper = getattr(p, '_native_destruction_baseline', None)
        self.assertTrue(callable(wrapper), 'Dedicated native baseline-only wrapper required')
        return wrapper(state, actor, policy)

    def test_generic_then_native_namespaces_do_not_share_values(self):
        state = self.state()
        generic = ('known', None, -99)
        native = ('known', None, 12)
        with p.decision_projection_scope(state, 1), patch.object(p, '_destruction_baseline', return_value=native) as compute:
            self.assertEqual(p._choice_free_projection(state, 1, 'destruction_baseline', None, lambda _: generic, None), generic)
            self.assertEqual(self.native(state), native)
            self.assertEqual(self.native(state), native)
            self.assertEqual(p._choice_free_projection(state, 1, 'destruction_baseline', None, lambda _: self.fail('generic hit lost'), None), generic)
            scope = p._decision_projection.get()[2]
            self.assertIsNot(scope['choice_free_outcomes'][1], scope['native_reference_baselines'][1])
            self.assertEqual(compute.call_count, 1)

    def test_native_then_generic_namespaces_do_not_share_values(self):
        state = self.state()
        with p.decision_projection_scope(state, 1), patch.object(p, '_destruction_baseline', return_value=('known', None, 7)) as native:
            self.assertEqual(self.native(state), ('known', None, 7))
            generic = []
            def compute(_):
                generic.append(1)
                return ('known', None, -7)
            self.assertEqual(p._choice_free_projection(state, 1, 'destruction_baseline', None, compute, None), ('known', None, -7))
            self.assertEqual(self.native(state), ('known', None, 7))
            self.assertEqual(native.call_count, 1)
            self.assertEqual(generic, [1])

    def test_native_never_enters_poisoned_candidate_memo_api(self):
        state = self.state()
        with p.decision_projection_scope(state, 1), patch.object(p, '_choice_free_projection', side_effect=AssertionError('candidate memo forbidden')), patch.object(p, '_destruction_baseline', return_value=('known', None, 1)):
            self.assertEqual(self.native(state), ('known', None, 1))

    def test_unused_non_none_fresh_callbacks_share_baseline(self):
        state = self.state()
        def unused(*_):
            self.fail('No native choice exists in this synthetic baseline')
        with p.decision_projection_scope(state, 1), patch.object(p, '_destruction_baseline', return_value=('known', None, 3)) as compute:
            for _ in range(2):
                self.assertEqual(self.native(state, policy=lambda *args: unused(*args)), ('known', None, 3))
            self.assertEqual(compute.call_count, 1)

    def test_used_callbacks_recompute_and_keep_side_effects(self):
        state = self.state()
        effects = []
        def policy(*args):
            effects.append(args)
            return {'type': 'pass_priority'}
        def baseline(root, actor, callback):
            callback(root, [], actor)
            return ('known', None, 2)
        with p.decision_projection_scope(state, 1), patch.object(p, '_destruction_baseline', side_effect=baseline) as compute:
            self.native(state, policy=policy)
            self.native(state, policy=policy)
            self.assertEqual(compute.call_count, 2)
            self.assertEqual(len(effects), 2)

    def test_root_and_state_rng_mutations_invalidate(self):
        state = self.state()
        with p.decision_projection_scope(state, 1), patch.object(p, '_destruction_baseline', return_value=('known', None, 2)) as compute:
            self.native(state)
            self.native(state)
            self.assertEqual(compute.call_count, 1)
            state.turn += 1
            self.native(state)
            self.assertEqual(compute.call_count, 2)
            state.rng.random()
            self.native(state)
            self.assertEqual(compute.call_count, 3)

    def test_scope_exit_and_reentry_never_share(self):
        state = self.state()
        with patch.object(p, '_destruction_baseline', return_value=('known', None, 2)) as compute:
            with p.decision_projection_scope(state, 1):
                self.native(state)
                self.native(state)
            self.native(state)
            with p.decision_projection_scope(state, 1):
                self.native(state)
            self.assertEqual(compute.call_count, 3)

    def test_wrong_root_or_actor_falls_back_without_reuse(self):
        state = self.state()
        other = self.state()
        with p.decision_projection_scope(state, 1), patch.object(p, '_destruction_baseline', return_value=('known', None, 2)) as compute:
            for root, actor in [(state, 2), (state, 2), (other, 1), (other, 1)]:
                self.native(root, actor)
            self.assertEqual(compute.call_count, 4)

    def test_unpickleable_root_falls_back_every_time(self):
        state = self.state()
        state.unpickleable = lambda: None
        with p.decision_projection_scope(state, 1), patch.object(p, '_destruction_baseline', return_value=('unknown', None, None)) as compute:
            self.assertEqual(self.native(state), ('unknown', None, None))
            self.assertEqual(self.native(state), ('unknown', None, None))
            self.assertEqual(compute.call_count, 2)

    def test_global_rng_change_invalidates_native_only(self):
        state = self.state()
        rng = random.getstate()
        try:
            with p.decision_projection_scope(state, 1), patch.object(p, '_destruction_baseline', return_value=('known', None, 2)) as compute:
                generic_calls = []
                def generic(_):
                    generic_calls.append(1)
                    return 9
                self.assertEqual(p._choice_free_projection(state, 1, 'query', None, generic, None), 9)
                self.native(state)
                random.random()
                self.native(state)
                self.assertEqual(compute.call_count, 2)
                self.assertEqual(p._choice_free_projection(state, 1, 'query', None, generic, None), 9)
                self.assertEqual(generic_calls, [1])
        finally:
            random.setstate(rng)

    def test_global_rng_mutated_during_compute_prevents_store(self):
        state = self.state()
        rng = random.getstate()
        try:
            def baseline(*_):
                random.random()
                return ('known', None, 2)
            with p.decision_projection_scope(state, 1), patch.object(p, '_destruction_baseline', side_effect=baseline) as compute:
                self.native(state)
                self.native(state)
                self.assertEqual(compute.call_count, 2)
        finally:
            random.setstate(rng)

    def test_generic_key_and_fallback_behavior_are_unchanged(self):
        state = self.state()
        with p.decision_projection_scope(state, 1):
            action = {'type': 'pass_priority'}
            self.assertEqual(p._choice_free_projection(state, 1, 'test', action, lambda _: 7, None), 7)
            memo = p._decision_projection.get()[2]['choice_free_outcomes']
            self.assertEqual(memo[0], pickle.dumps(state, protocol=5))
            self.assertEqual(set(memo[1]), {('test', True, '{"type":"pass_priority"}')})
        callback = lambda *_: None
        with patch.object(p, '_destruction_baseline'):
            self.assertIs(p._choice_free_projection(state, 1, 'test', None, lambda policy: policy, callback), callback)

    def test_private_kernel_has_only_two_hardcoded_wrapper_callers(self):
        wrapper = getattr(p, '_native_destruction_baseline', None)
        self.assertTrue(callable(wrapper), 'Dedicated native wrapper required')
        self.assertEqual(list(inspect.signature(wrapper).parameters), ['state', 'player_id', 'policy'])
        tree = ast.parse(Path(p.__file__).read_bytes())
        owners = {}
        for function in tree.body:
            if not isinstance(function, ast.FunctionDef):
                continue
            for call in ast.walk(function):
                if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == '_memoized_projection':
                    owners[function.name] = next(k.value.value for k in call.keywords if k.arg == 'namespace')
        self.assertEqual(owners, {'_choice_free_projection': 'choice_free_outcomes', '_native_destruction_baseline': 'native_reference_baselines'})

    def test_real_native_two_uncached_to_one_scoped_with_unused_policy(self):
        from tests.test_ai_friendly_destruction_continuations import position
        for seat in (1, 2):
            state, *_ = position(seat)
            before = serialize_match_snapshot(state)
            rng = random.getstate()
            native = p._destruction_baseline
            calls = []
            def counted(*args):
                calls.append(1)
                return native(*args)
            def unused(*_):
                self.fail('Unexpected native optional choice')
            with patch.object(p, '_destruction_baseline', counted):
                first = self.native(state, seat, unused)
                second = self.native(state, seat, unused)
                self.assertEqual(first, second)
                self.assertEqual(len(calls), 2)
                calls.clear()
                with p.decision_projection_scope(state, seat):
                    self.assertEqual(self.native(state, seat, lambda *args: unused(*args)), first)
                    self.assertEqual(self.native(state, seat, lambda *args: unused(*args)), first)
                    self.assertEqual(len(calls), 1)
            self.assertEqual(serialize_match_snapshot(state), before)
            self.assertEqual(random.getstate(), rng)


if __name__ == '__main__':
    unittest.main()
