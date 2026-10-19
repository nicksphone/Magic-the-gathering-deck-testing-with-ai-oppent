"""Source-projected replay metadata controls, not native game qualification."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import random
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from analytics.resource_budget import ResourceBudget, RESOURCE_LIMITS, SimulationResourceLimit


BACKEND = Path(__file__).resolve().parents[1]
DIMENSIONS = (
    'deadline', 'game_log', 'game_log_entries', 'batch_log', 'batch_log_entries',
    'trace_scalar', 'trace_nodes', 'trace_depth', 'trace_entry', 'action_log',
)


def replay():
    path = BACKEND / 'scripts/regression_matrix_replay.py'
    tree = ast.parse(path.read_text())
    nodes = [ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0)]
    nodes += [node for node in tree.body if isinstance(node, ast.FunctionDef)
              and node.name in {'run_game', '_timed_stage', '_record_game_evidence'}]
    namespace = dict(hashlib=hashlib, json=json)
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
                 str(path), 'exec'), namespace)
    return namespace


class ResourceMetadataTests(unittest.TestCase):
    def setUp(self):
        self.api = replay()
        self.now = 0.0
        self.events = []
        self.delivered = []
        self.failure = None
        player = SimpleNamespace(hand=[], battlefield=[], mana_pool={}, life=20,
                                 lands_played_this_turn=0)
        self.state = SimpleNamespace(winner=None, turn=1, step='main',
            priority_player=1, active_player=1, pregame_pending=False,
            players={1: player, 2: copy.deepcopy(player)}, cards={}, stack=[], log=['initial'])

        def factory(*args, **kwargs):
            self.events.append(('factory', kwargs['seed']))
            self.now += 2
            return copy.deepcopy(self.state)

        def begin(log):
            self.now += 3
            if self.failure is not None:
                raise self.failure

        def rules():
            self.now += 1
            return SimpleNamespace(legal_moves=lambda *args: [{'type': 'pass_priority'}])

        def agent(**kwargs):
            self.now += 1
            return SimpleNamespace(choose_action=lambda *args:
                SimpleNamespace(action={'type': 'pass_priority'}))

        def checked(state, engine, pid, action):
            self.events.append(('boundary_double', pid, action))
            self.now += 5
            candidate = copy.deepcopy(state)
            candidate.winner = 1
            candidate.log.append('applied')
            return candidate

        def accept(previous, candidate, line):
            candidate.log.insert(len(previous.log), line)

        def normalize(line):
            self.events.append(('normalize',))
            self.now += 11
            return line

        self.budget = SimpleNamespace(begin_game=begin, before_clone=lambda: None,
                                     accept_candidate=accept)
        self.api.update(MatchFactory=SimpleNamespace(from_decks=factory), RulesEngine=rules,
            AIAgent=agent, guess_archetype=lambda deck: 'unknown', complete_action=lambda action: action,
            checked_action=checked, normalize_log_line=normalize)

    def clock(self):
        self.events.append(('clock',))
        return self.now

    def writer(self, result, raw):
        self.events.append(('writer',))
        self.now += 100
        self.delivered.append(copy.deepcopy(result))
        encoded = json.dumps(raw, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode()
        return dict(complete=True, bytes=len(encoded), raw_sha256=hashlib.sha256(encoded).hexdigest(),
                    reference='game-01.json')

    def run_game(self, *, writer=True, budget=None, max_ticks=1):
        with patch('time.monotonic', self.clock):
            return self.api['run_game']([], [], 73, 'strong', max_ticks,
                budget=self.budget if budget is None else budget,
                record_game=self.writer if writer else None)

    def assert_metadata(self, result, dimension, elapsed):
        self.assertIn('resource_limit_dimension', result)
        self.assertIn('game_elapsed_seconds', result)
        self.assertEqual(result['resource_limit_dimension'], dimension)
        self.assertEqual(result['game_elapsed_seconds'], elapsed)
        self.assertEqual(self.delivered[-1]['resource_limit_dimension'], dimension)
        self.assertEqual(self.delivered[-1]['game_elapsed_seconds'], elapsed)

    def test_all_ten_known_dimensions_are_recorded_without_exception_args(self):
        for dimension in DIMENSIONS:
            with self.subTest(dimension=dimension):
                self.setUp()
                self.failure = SimulationResourceLimit(dimension)
                self.failure.args = (object(),)
                result = self.run_game()
                self.assertEqual(result['stop_reason'], 'resource_limit')
                self.assertIsNone(result['winner'])
                self.assert_metadata(result, dimension, 5.0)

    def test_unknown_dimension_is_null_not_exception_text(self):
        self.failure = SimulationResourceLimit('PRIVATE_SENTINEL')
        result = self.run_game()
        self.assert_metadata(result, None, 5.0)
        self.assertNotIn('PRIVATE_SENTINEL', json.dumps(result))

    def test_malformed_or_missing_dimension_is_null(self):
        class StringSubclass(str):
            def __eq__(self, other):
                raise AssertionError('Malformed dimension must not be compared')

        for value in (None, True, 1, [], {}, StringSubclass('deadline')):
            with self.subTest(kind=type(value).__name__):
                self.setUp()
                self.failure = SimulationResourceLimit('deadline')
                self.failure.dimension = value
                self.assert_metadata(self.run_game(), None, 5.0)
        self.setUp()
        self.failure = SimulationResourceLimit('deadline')
        del self.failure.dimension
        self.assert_metadata(self.run_game(), None, 5.0)

    def test_subclass_is_null_but_original_stop_routing_is_preserved(self):
        class Child(SimulationResourceLimit):
            @property
            def dimension(self):
                raise AssertionError('Subclass metadata must not be read')

            @dimension.setter
            def dimension(self, value):
                pass

        self.failure = Child('deadline')
        result = self.run_game()
        self.assertEqual(result['stop_reason'], 'resource_limit')
        self.assert_metadata(result, None, 5.0)

    def test_ordinary_error_never_reads_dimension_or_renders_message(self):
        class Other(ValueError):
            @property
            def dimension(self):
                raise AssertionError('Foreign error metadata must not be read')

            def __str__(self):
                raise AssertionError('Exception messages must not be rendered')

        self.failure = Other('PRIVATE_SENTINEL')
        result = self.run_game()
        self.assertEqual(result['stop_reason'], 'action_error')
        self.assert_metadata(result, None, 5.0)

    def test_success_clock_includes_factory_excludes_normalizing_and_writer(self):
        before_rng = random.getstate()
        result = self.run_game()
        self.assert_metadata(result, None, 13.0)
        self.assertEqual(self.events[:2], [('clock',), ('factory', 73)])
        last_clock = max(index for index, event in enumerate(self.events) if event == ('clock',))
        self.assertEqual(self.events[last_clock + 1], ('normalize',))
        self.assertEqual(sum(event == ('clock',) for event in self.events), 2)
        self.assertEqual(result['winner'], 1)
        self.assertFalse(result['timeout'])
        self.assertEqual(result['ticks'], 1)
        self.assertEqual(result['starting_player'], 1)
        self.assertEqual(result['log_hash'], hashlib.sha256('\n'.join(result['log']).encode()).hexdigest())
        self.assertEqual(result['log'][0], 'initial')
        self.assertEqual(result['log'][-1], 'applied')
        self.assertNotIn('stop_reason', result)
        self.assertEqual(random.getstate(), before_rng)

    def test_tick_cap_stays_timeout_not_resource_limit(self):
        result = self.run_game(max_ticks=0)
        self.assert_metadata(result, None, 8.0)
        self.assertTrue(result['timeout'])
        self.assertEqual(result['ticks'], 0)
        self.assertNotIn('stop_reason', result)

    def test_no_writer_has_original_fields_and_no_clock_calls(self):
        result = self.run_game(writer=False)
        self.assertEqual(set(result), {'winner', 'turn', 'ticks', 'log_hash', 'log', 'timeout', 'starting_player'})
        self.assertNotIn(('clock',), self.events)

    def test_no_writer_reraises_same_exception_without_clock(self):
        self.failure = SimulationResourceLimit('deadline')
        try:
            self.run_game(writer=False)
        except SimulationResourceLimit as exc:
            self.assertIs(exc, self.failure)
        else:
            self.fail('Original exception was swallowed')
        self.assertNotIn(('clock',), self.events)
        self.assertEqual(self.delivered, [])

    def test_genuine_budget_failures_record_the_actual_dimension(self):
        for dimension, override in (
            ('deadline', dict(deadline_seconds=0)),
            ('game_log', dict(game_log_utf8_bytes=0)),
            ('game_log_entries', dict(game_log_entries=0)),
            ('batch_log', dict(batch_log_utf8_bytes=0)),
            ('batch_log_entries', dict(batch_log_entries=0)),
        ):
            with self.subTest(dimension=dimension):
                self.setUp()
                budget = ResourceBudget(dict(RESOURCE_LIMITS, **override), clock=lambda: 0)
                limits = dict(budget.limits)
                deadline = budget.deadline
                result = self.run_game(budget=budget)
                self.assert_metadata(result, dimension, 2.0)
                self.assertEqual(budget.limits, limits)
                self.assertEqual(budget.deadline, deadline)


if __name__ == '__main__':
    unittest.main()
