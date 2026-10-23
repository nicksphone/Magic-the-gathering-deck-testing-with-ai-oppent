"""Count genuine rule bodies; preserve wire bytes and fresh snapshot results."""
from contextlib import contextmanager
import pickle
import sys
from unittest import TestCase
from unittest.mock import patch

from ai.agent import AIAgent
from analytics import decision_quality as trace
from rules_engine import continuous
from rules_engine.engine import RulesEngine
from rules_engine.query_context import query_cache, rule_query_scope
from tests.test_trace_snapshot_single_query import scene, legacy_snapshot, wire_json


@contextmanager
def source_scans():
    target = continuous._continuous_sources.__wrapped__.__code__
    snapshot = trace._battlefield_snapshot.__code__
    calls = []
    previous = sys.getprofile()

    def observe(frame, event, value):
        if event == 'call' and frame.f_code is target:
            parent = frame.f_back
            while parent is not None and parent.f_code is not snapshot:
                parent = parent.f_back
            if parent is not None:
                calls.append(1)

    sys.setprofile(observe)
    try:
        yield calls
    finally:
        sys.setprofile(previous)


class SnapshotQueryScope(TestCase):
    def test_output_list_alias_probe_does_not_change_cache_or_state(self):
        state = scene()
        before = pickle.dumps(state, protocol=5)
        with rule_query_scope(state):
            first = trace._battlefield_snapshot(state, 1)
            # Deliberate output-container probe, not a Magic type/keyword.
            first[0]['types'].append('audit-alias-probe')
            first[0]['keywords'].append('audit-alias-probe')
            second = trace._battlefield_snapshot(state, 1)
            self.assertNotIn('audit-alias-probe', second[0]['types'])
            self.assertNotIn('audit-alias-probe', second[0]['keywords'])
        self.assertEqual(pickle.dumps(state, protocol=5), before)

    def test_nested_scope_keeps_the_existing_owner_cache(self):
        state = scene()
        self.assertIsNone(query_cache(state))
        with rule_query_scope(state):
            outer = query_cache(state)
            trace._battlefield_snapshot(state, 1)
            self.assertIs(query_cache(state), outer)
        self.assertIsNone(query_cache(state))

    def test_exception_restores_own_and_nested_context(self):
        state = scene()
        self.assertIsNone(query_cache(state))
        with patch.object(trace, 'effective_types', side_effect=RuntimeError('query-probe')):
            with self.assertRaisesRegex(RuntimeError, 'query-probe'):
                trace._battlefield_snapshot(state, 1)
        self.assertIsNone(query_cache(state))
        with rule_query_scope(state):
            outer = query_cache(state)
            with patch.object(trace, 'effective_types', side_effect=RuntimeError('query-probe')):
                with self.assertRaisesRegex(RuntimeError, 'query-probe'):
                    trace._battlefield_snapshot(state, 1)
            self.assertIs(query_cache(state), outer)
        self.assertIsNone(query_cache(state))

    def test_empty_boards_do_not_scan_sources(self):
        state = scene(empty=True)
        before = pickle.dumps(state, protocol=5)
        with source_scans() as calls:
            self.assertEqual([trace._battlefield_snapshot(state, pid) for pid in (1, 2)], [[], []])
        self.assertEqual(calls, [])
        self.assertEqual(pickle.dumps(state, protocol=5), before)

    def test_two_seat_rows_share_sources_only_within_each_snapshot(self):
        state = scene()
        expected = [legacy_snapshot(state, pid) for pid in (1, 2)]
        before = pickle.dumps(state, protocol=5)
        with source_scans() as calls:
            observed = [trace._battlefield_snapshot(state, pid) for pid in (1, 2)]
        self.assertEqual(wire_json(observed), wire_json(expected))
        self.assertEqual(pickle.dumps(state, protocol=5), before)
        self.assertEqual(len(calls), 2)

    def test_fresh_counters_are_not_reused_across_snapshots(self):
        state = scene()
        count = 0
        rows = []
        for bonus in (0, 3):
            state.cards['bear'].counters['+1/+1'] = bonus
            state.cards['elf'].counters['__eot_toughness'] = bonus
            expected = [legacy_snapshot(state, pid) for pid in (1, 2)]
            before = pickle.dumps(state, protocol=5)
            with source_scans() as calls:
                observed = [trace._battlefield_snapshot(state, pid) for pid in (1, 2)]
            self.assertEqual(wire_json(observed), wire_json(expected))
            self.assertEqual(pickle.dumps(state, protocol=5), before)
            count += len(calls)
            rows.append(observed)
        self.assertNotEqual(rows[0], rows[1])
        self.assertEqual(count, 4)

    def test_complete_trace_wire_and_knowledge_usage_remain_exact(self):
        state = scene()
        legal = RulesEngine().legal_moves(state, 1)
        decision = AIAgent('strong').choose_action(state, legal, 1)
        before = pickle.dumps((state, legal), protocol=5)
        args = (state, 1, legal, decision.action, decision.reasoning)
        with patch.object(trace, '_battlefield_snapshot', legacy_snapshot):
            expected = trace.build_trace_payload(*args, knowledge_usage=decision.knowledge_usage)
        with source_scans() as calls:
            observed = trace.build_trace_payload(*args, knowledge_usage=decision.knowledge_usage)
        self.assertEqual(wire_json(observed), wire_json(expected))
        self.assertEqual(pickle.dumps((state, legal), protocol=5), before)
        self.assertEqual(len(calls), 2)
