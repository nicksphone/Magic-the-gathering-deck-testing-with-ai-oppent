"""Native history-isolation protocol; no model construction or inference."""
from copy import deepcopy
import copyreg
import pickle
import unittest
from unittest.mock import patch

from ai import agent as a, pending_effects as p, learned_policy as lp, learned_qv as qv


class NativePlannerIsolation(unittest.TestCase):
    def factory(self, owner):
        self.assertTrue(hasattr(a, '_native_planner_snapshot'), 'native snapshot factory missing')
        return a._native_planner_snapshot(owner)

    def test_genuine_counter_history_is_frozen_and_fresh_in_both_seats(self):
        from tests.test_ai_friendly_destruction_continuations import position
        for seat in (1, 2):
            state, *_ = position(seat)
            before = pickle.dumps(state, protocol=5)
            owner = a.AIAgent('master', 'Aristocrats')
            spawn = self.factory(owner)
            first, second = spawn(), spawn()
            method = '_should_force_conversion_after_repeated_main_pass'
            self.assertFalse(getattr(first, method)(state, seat))
            self.assertFalse(getattr(second, method)(state, seat))
            self.assertTrue(getattr(first, method)(state, seat))
            self.assertEqual(owner._main_pass_signature_counts, {})
            self.assertEqual(sorted(first._main_pass_signature_counts.values()), [2])
            self.assertEqual(sorted(second._main_pass_signature_counts.values()), [1])
            self.assertEqual(pickle.dumps(state, protocol=5), before)

    def test_snapshot_does_not_follow_later_owner_counter_mutations(self):
        from tests.test_ai_friendly_destruction_continuations import position
        state, *_ = position(1)
        owner = a.AIAgent('master')
        self.assertFalse(owner._should_force_conversion_after_repeated_main_pass(state, 1))
        spawn = self.factory(owner)
        owner._main_pass_signature_counts.clear()
        first = spawn()
        self.assertTrue(first._should_force_conversion_after_repeated_main_pass(state, 1))
        self.assertEqual(owner._main_pass_signature_counts, {})
        self.assertEqual(sorted(spawn()._main_pass_signature_counts.values()), [1])

    def test_no_constructor_state_or_model_copy_engine_and_binding_shared(self):
        from ai.learned_policy import LivePolicyBinding
        from ai.learned_qv import QVPolicy
        owner = a.AIAgent('master')
        policy = object.__new__(QVPolicy)
        policy._payload = {}  # Native API carrier only, no weights or inference.
        binding = LivePolicyBinding(policy, '0' * 64, ())
        owner.learned_binding = binding
        spawn = self.factory(owner)
        with patch.object(a.AIAgent, '__init__', side_effect=AssertionError('constructor')):
            with patch.object(a.copy, 'deepcopy', side_effect=AssertionError('deepcopy')):
                first, second = spawn(), spawn()
        self.assertIs(first.engine, owner.engine)
        self.assertIs(first.learned_binding, binding)
        self.assertIsNot(first.__dict__, owner.__dict__)
        self.assertIsNot(first._main_pass_signature_counts, second._main_pass_signature_counts)

    def test_unknown_or_overridden_owners_fall_back(self):
        owner = a.AIAgent('master')
        self.assertIsNotNone(self.factory(owner))
        for key, value in [('choose_action', lambda *_: None), ('_rank_moves', lambda *_: []),
                           ('unknown_hook', object()), ('_main_pass_signature_counts', []),
                           ('matchup_profile', object()), ('learned_binding', object())]:
            fresh = a.AIAgent('master')
            setattr(fresh, key, value)
            self.assertIsNone(self.factory(fresh), key)
        class Child(a.AIAgent):
            pass
        self.assertIsNone(self.factory(Child('master')))
        owner.engine.custom_hook = object()
        self.assertIsNone(self.factory(owner))
        del owner.engine.custom_hook
        with patch.object(a.AIAgent, 'choose_action', lambda *_: None):
            self.assertIsNone(self.factory(owner))
        with patch.object(a.AIAgent, '_should_force_conversion_after_repeated_main_pass', lambda *_: False):
            self.assertIsNone(self.factory(owner))
        with patch.object(a.RulesEngine, 'legal_moves', lambda *_: []):
            self.assertIsNone(self.factory(owner))
        with patch.object(p, 'friendly_destruction_profit', lambda *_: False):
            self.assertIsNone(self.factory(owner))
        with patch.object(a.AIAgent, '__getattr__', lambda *_: None, create=True):
            self.assertIsNone(self.factory(owner))
        class Counts(dict):
            pass
        owner._main_pass_signature_counts = Counts()
        self.assertIsNone(self.factory(owner))
        owner._main_pass_signature_counts = {('unknown',): []}
        self.assertIsNone(self.factory(owner))

    def test_materialization_uses_isolated_callback_not_real_owner(self):
        from tests.test_ai_friendly_destruction_continuations import position
        state, murder, *_ = position(1)
        owner = a.AIAgent('master', 'Aristocrats')
        move = next(x for x in owner.engine.legal_moves(state, 1)
                    if x.get('type') == 'cast_spell' and x.get('card_id') == murder)
        original = p.unproductive_destroy_targets
        calls = []
        def observe(*args, **kwargs):
            calls.append(kwargs['_native_shared_baseline'])
            own = kwargs['own_choice_action']
            planners = [cell.cell_contents for cell in own.__closure__ or ()]
            self.assertNotIn(owner, planners)
            return original(*args, **kwargs)
        before = deepcopy(owner._main_pass_signature_counts)
        with patch.object(p, 'unproductive_destroy_targets', observe):
            chosen = owner._materialize_action(state, deepcopy(move), 1)
        self.assertFalse(chosen.get('_invalid_ai_choice', False))
        self.assertEqual(calls, [True])
        self.assertEqual(owner._main_pass_signature_counts, before)


NATIVE_BINDING = lp.LivePolicyBinding
NATIVE_POLICY = qv.QVPolicy


class NativeProviderBoundary(unittest.TestCase):
    def owner(self, policy=None):
        if policy is None:
            policy = object.__new__(NATIVE_POLICY)
            policy._payload = {}  # Shape-only carrier, deliberately no model payload.
        owner = a.AIAgent('master')
        owner.learned_binding = NATIVE_BINDING(policy, '0' * 64, ())
        return owner

    def test_native_api_carrier_remains_eligible_and_binding_shared(self):
        owner = self.owner()
        spawn = a._native_planner_snapshot(owner)
        self.assertIsNotNone(spawn)
        self.assertIs(spawn().learned_binding, owner.learned_binding)

    def test_custom_provider_inside_exact_binding_rejected_without_calling_it(self):
        calls = []
        class CustomProvider:
            def prepare(self, state):
                calls.append(state)
                raise AssertionError('Provider must not be invoked by the gate')
        self.assertIsNone(a._native_planner_snapshot(self.owner(CustomProvider())))
        self.assertEqual(calls, [])

    def test_exact_native_policy_instance_overrides_rejected(self):
        calls = []
        def custom(*args, **kwargs):
            calls.append(args)
            raise AssertionError('No provider method execution')
        for name in ('prepare', 'predict', '_encode', '_linear'):
            with self.subTest(name=name):
                owner = self.owner()
                setattr(owner.learned_binding._policy, name, custom)
                self.assertIsNone(a._native_planner_snapshot(owner))
        self.assertEqual(calls, [])

    def test_native_policy_class_method_overrides_rejected(self):
        owner = self.owner()
        for name in ('prepare', 'predict', '_encode', '_linear'):
            with self.subTest(name=name), patch.object(NATIVE_POLICY, name, lambda *_: None):
                self.assertIsNone(a._native_planner_snapshot(owner))

    def test_binding_descriptor_and_getattribute_overrides_rejected(self):
        owner = self.owner()
        def forbidden(*_):
            raise AssertionError('Overridden binding attribute hook executed')
        with patch.object(NATIVE_BINDING, '_policy', property(forbidden)):
            self.assertIsNone(a._native_planner_snapshot(owner))
        with patch.object(NATIVE_BINDING, '__getattribute__', forbidden, create=True):
            self.assertIsNone(a._native_planner_snapshot(owner))

    def test_prepared_decision_class_and_factory_alias_overrides_rejected(self):
        owner = self.owner()
        with patch.object(qv.QVDecision, 'predict', lambda *_: None):
            self.assertIsNone(a._native_planner_snapshot(owner))
        with patch.object(qv.QVDecision, '__getattribute__', lambda *_: None, create=True):
            self.assertIsNone(a._native_planner_snapshot(owner))
        with patch.object(qv, 'QVDecision', object):
            self.assertIsNone(a._native_planner_snapshot(owner))

    def test_policy_module_aliases_rejected(self):
        owner = self.owner()
        for module, name in ((qv, 'QVPolicy'), (lp, 'QVPolicy'), (lp, 'LivePolicyBinding')):
            with self.subTest(module=module.__name__, name=name), patch.object(module, name, object):
                self.assertIsNone(a._native_planner_snapshot(owner))

    def test_policy_subclass_and_extra_state_rejected(self):
        class Child(NATIVE_POLICY):
            pass
        child = object.__new__(Child)
        child._payload = {}
        self.assertIsNone(a._native_planner_snapshot(self.owner(child)))
        owner = self.owner()
        owner.learned_binding._policy.provider_cache = {}
        self.assertIsNone(a._native_planner_snapshot(owner))

    def test_missing_native_binding_slots_or_policy_payload_fall_back(self):
        full = self.owner().learned_binding
        for missing in ('_policy', 'checkpoint_sha256', '_contract'):
            with self.subTest(missing=missing):
                binding = object.__new__(NATIVE_BINDING)
                for name in ('_policy', 'checkpoint_sha256', '_contract'):
                    if name != missing:
                        object.__setattr__(binding, name, getattr(full, name))
                owner = a.AIAgent('master')
                owner.learned_binding = binding
                self.assertIsNone(a._native_planner_snapshot(owner))
        self.assertIsNone(a._native_planner_snapshot(self.owner(object.__new__(NATIVE_POLICY))))

    def test_real_pickle_roundtrip_keeps_native_planner_eligible(self):
        owner = self.owner()
        self.assertIsNotNone(a._native_planner_snapshot(owner))
        restored = pickle.loads(pickle.dumps(vars(owner), protocol=5))
        self.assertIsNotNone(a._native_planner_snapshot(owner))
        restored_owner = a.AIAgent('master')
        restored_owner.__dict__ = restored
        self.assertIsNotNone(a._native_planner_snapshot(restored_owner))

    def test_standard_copyreg_caches_for_all_native_classes_remain_eligible(self):
        owner = self.owner()
        for cls in (a.AIAgent, a.RulesEngine, NATIVE_BINDING, NATIVE_POLICY, qv.QVDecision):
            copyreg._slotnames(cls)
        self.assertIsNotNone(a._native_planner_snapshot(owner))

    def test_malformed_slot_caches_keep_the_generic_fallback(self):
        class ListSubclass(list):
            pass
        owner = self.owner()
        for cls in (a.AIAgent, a.RulesEngine, NATIVE_BINDING, NATIVE_POLICY, qv.QVDecision):
            for cache in (None, (), ['unexpected'], ListSubclass()):
                with self.subTest(cls=cls.__name__, cache=type(cache).__name__):
                    with patch.object(cls, '__slotnames__', cache, create=True):
                        self.assertIsNone(a._native_planner_snapshot(owner))

    def test_raw_class_layout_is_checked_before_getattribute_descriptor_lookup(self):
        calls = []
        class Descriptor:
            def __get__(self, instance, owner):
                calls.append(owner)
                raise AssertionError('Custom class descriptor must not execute')
        owner = self.owner()
        for cls in (NATIVE_BINDING, NATIVE_POLICY, qv.QVDecision):
            with self.subTest(cls=cls.__name__):
                with patch.object(cls, '__getattribute__', Descriptor(), create=True):
                    self.assertFalse(a._native_learned_provider(owner.learned_binding))
        self.assertEqual(calls, [])

    def test_rebound_planner_class_aliases_keep_the_generic_fallback(self):
        owner = a.AIAgent('master')
        for name in ('AIAgent', 'RulesEngine'):
            with self.subTest(name=name), patch.object(a, name, object()):
                self.assertIsNone(a._native_planner_snapshot(owner))
