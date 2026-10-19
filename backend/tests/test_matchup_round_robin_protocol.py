"""Pure protocol projections; scripted outcomes are NOT native AI evidence."""
import ast
import builtins
import copy
import hashlib
import json
import tempfile
import unittest
from collections import Counter, defaultdict
from contextlib import contextmanager
from functools import partial
from pathlib import Path
from types import SimpleNamespace

BACKEND = Path(__file__).resolve().parents[1]


def project(path, namespace=None, names=None):
    tree = ast.parse(path.read_text())
    nodes = [ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0)]
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and (names is None or node.name in names):
            nodes.append(node)
    result = dict(namespace or {})
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), str(path), 'exec'), result)
    return result


def replay_namespace():
    policy = project(BACKEND / 'game_state/series_policy.py')
    namespace = dict(json=json, hashlib=hashlib, Callable=object, **policy)
    namespace = project(BACKEND / 'scripts/regression_matrix_replay.py', namespace,
                        {'run_game', 'run_match', '_timed_stage', '_record_game_evidence'})
    namespace['normalize_log_line'] = lambda line: line.replace('RAW-ID', 'ID')
    return namespace


def roster():
    names = ast.literal_eval(ast.parse((BACKEND / 'decks/builtin_decks.py').read_text()).body[1].value)
    return [{'source': 'builtin', 'name': name, 'mainboard': [dict(quantity=60,
             card_name='Island', oracle_text='{T}: Add {U}.', mana_cost='', type_line='Basic Land — Island')],
             'sideboard': [dict(quantity=1, card_name='Island', oracle_text='{T}: Add {U}.',
                                mana_cost='', type_line='Basic Land — Island')],
             'classification_status': 'resolved', 'archetype': 'Control'} for name in names]


def fake_engine(namespace, *, winner=1, action_error=False):
    player = SimpleNamespace(name='Protocol player', hand=[], battlefield=[], life=20, mana_pool={}, lands_played_this_turn=0)
    state = SimpleNamespace(winner=None, turn=1, step='precombat_main', active_player=1,
        priority_player=1, pregame_pending=False, cards={}, players={1: player, 2: copy.deepcopy(player)},
        stack=[], log=['RAW-ID initial'])
    legal = [{'type': 'cast_spell', 'card_id': 'genuine-fixture'}, {'type': 'pass_priority'}]
    decision = SimpleNamespace(action=legal[0], reasoning='inert decision', knowledge_usage={'seen': 1})
    calls = []
    def checked(old, engine, pid, action):
        calls.append(('checked', old, legal, action))
        if action_error:
            raise ValueError('private error omitted')
        new = copy.deepcopy(old)
        new.log.append('RAW-ID applied')
        new.winner = winner
        return new
    namespace.update(MatchFactory=SimpleNamespace(from_decks=lambda *a, **k: copy.deepcopy(state)),
        RulesEngine=lambda: SimpleNamespace(legal_moves=lambda s, pid: legal),
        AIAgent=lambda **k: SimpleNamespace(choose_action=lambda s, l, pid: decision),
        guess_archetype=lambda d: 'unknown', complete_action=lambda a: dict(a), checked_action=checked)
    return legal, decision, calls


def game_fixture(winner, **extra):
    return dict(winner=winner, turn=2, ticks=1, timeout=winner is None,
                log=['inert fixture'], log_hash='fixture', **extra)


class RoundRobinProtocolTests(unittest.TestCase):
    def setUp(self):
        self.replay = replay_namespace()
        path = BACKEND / 'scripts/matchup_round_robin.py'
        self.runner = {'__file__': str(path), '__name__': 'task31_runner_projection',
                       '__builtins__': dict(vars(builtins))}
        if path.exists():
            exec(compile(path.read_text(), str(path), 'exec'), self.runner)
        if 'source_binding' in (self.runner.get('run_round_robin').__kwdefaults__ or {}):
            # Explicit protocol-only epoch; all actual backend file bytes are bound.
            # This synthetic commit label is NOT an executed/public game certificate.
            files = self.runner['collect_source_manifest'](BACKEND)
            binding = dict(schema_version=1, source_base_commit='a' * 40, backend_files=files,
                           backend_sha256=self.runner['digest'](files))
            self.runner['run_round_robin'] = partial(self.runner['run_round_robin'], source_binding=binding)

    def require(self, name):
        self.assertTrue(callable(self.runner.get(name)), 'Missing approved runner API: ' + name)
        return self.runner[name]

    def test_01_full_schedule_and_finite_roster(self):
        schedule = self.require('build_schedule')
        rows = roster()
        before = copy.deepcopy(rows)
        result = schedule(rows, [3, 7])
        self.assertEqual(len(result), 220)
        self.assertEqual(result, schedule(list(reversed(rows)), [3, 7]))
        self.assertEqual(rows, before)
        for bad in (rows[:-1], rows + [copy.deepcopy(rows[0])], rows + [dict(rows[0], name='foreign')]):
            with self.assertRaises(ValueError):
                schedule(bad, [3])

    def test_02_typed_seed_content_and_export(self):
        make = self.require('make_export')
        load = self.require('validate_export')
        schedule = self.require('build_schedule')
        rows = roster()
        export = make(rows, corpus_sha256='a' * 64)
        self.assertEqual(load(export), sorted(rows, key=lambda x: x['name']))
        changed = copy.deepcopy(rows)
        changed[0]['sideboard'][0]['quantity'] = 2
        self.assertNotEqual(export['decks_sha256'], make(changed, corpus_sha256='a' * 64)['decks_sha256'])
        bad = copy.deepcopy(export)
        bad['decks'][0]['mainboard'][0]['quantity'] = True
        with self.assertRaises(ValueError):
            load(bad)
        for tokens in ([True], [1.0], [-1], [1, 1], []):
            with self.assertRaises(ValueError):
                schedule(rows, tokens)
        for key in ('corpus_sha256', 'builtin_sha256', 'source_commit'):
            bad = copy.deepcopy(export)
            bad[key] = 'wrong'
            with self.assertRaises(ValueError):
                load(bad)

    def test_03_mirror_mapping_and_loser_starts(self):
        rows = self.require('build_schedule')(roster(), [8])
        self.assertEqual(rows[0]['root_seed'], rows[1]['root_seed'])
        self.assertEqual(rows[0]['seat_one'], rows[1]['seat_two'])
        self.assertEqual(rows[0]['seat_two'], rows[1]['seat_one'])
        winners, starts = iter([1, 0, 2, 1]), []
        def play(*args, starting_player):
            starts.append(starting_player)
            return game_fixture(next(winners))
        self.assertIn('game_runner', self.replay['run_match'].__kwdefaults__)
        result = self.replay['run_match']([], [], 10, 'strong', 10, 3, game_runner=play)
        self.assertEqual(starts, [1, 2, 2, 1])
        self.assertEqual([g['seed'] for g in result['games']], [10, 11, 12, 13])
        self.assertEqual(result['winner'], 1)

    def test_04_decisive_series_and_early_stop(self):
        self.assertIn('game_runner', self.replay['run_match'].__kwdefaults__)
        for winners, score in (([1, 1], {'deck_a': 2, 'deck_b': 0}), ([1, 2, 1], {'deck_a': 2, 'deck_b': 1})):
            calls = []
            def play(*args, **kwargs):
                calls.append(args[2])
                return game_fixture(winners[len(calls) - 1])
            result = self.replay['run_match']([], [], 3, 'strong', 10, 3, game_runner=play)
            self.assertEqual(result['wins'], score)
            self.assertEqual(calls, list(range(3, 3 + len(winners))))

    def test_05_six_draws_never_fabricate_series_winner(self):
        self.assertIn('game_runner', self.replay['run_match'].__kwdefaults__)
        result = self.replay['run_match']([], [], 2, 'strong', 10, 3, game_runner=lambda *a, **k: game_fixture(0))
        self.assertEqual(result['games_played'], 6)
        self.assertEqual(result['wins'], {'deck_a': 0, 'deck_b': 0})
        self.assertIsNone(result['winner'])
        self.assertTrue(result['draw_cap_reached'])
        self.assertEqual([g['starting_player'] for g in result['games']], [1] * 6)

    def test_06_unfinished_and_errors_stop_at_actual_slot(self):
        self.assertIn('game_runner', self.replay['run_match'].__kwdefaults__)
        for partial in (game_fixture(None), dict(game_fixture(None), timeout=False),
                        game_fixture(1, stop_reason='resource_limit'), game_fixture(1, stop_reason='evidence_error')):
            calls = []
            def play(*a, **k):
                calls.append(a[2])
                return copy.deepcopy(partial)
            result = self.replay['run_match']([], [], 4, 'strong', 10, 3, game_runner=play)
            self.assertEqual(calls, [4])
            self.assertIsNone(result['winner'])
            self.assertEqual(len(result['games']), 1)

    def test_07_nonempty_fixed_inventory_conservation(self):
        schedule = self.require('build_schedule')
        boards = roster()
        row = schedule(boards, [0])[0]
        check = self.require('check_fixed_boards')
        before = copy.deepcopy(boards)
        check(before, boards)
        self.assertEqual(row['sideboard_mode'], 'fixed_no_swaps')
        for kind in ('mainboard', 'sideboard'):
            bad = copy.deepcopy(boards)
            bad[0][kind][0]['quantity'] += 1
            with self.assertRaises(ValueError):
                check(before, bad)
        for quantity in (True, -1, 0, 1.0):
            bad = copy.deepcopy(boards)
            bad[0]['sideboard'][0]['quantity'] = quantity
            with self.assertRaises(ValueError):
                schedule(bad, [0])

    def test_08_actual_function_trace_forwarding_before_candidate(self):
        fn = self.replay['run_game']
        self.assertIn('trace_builder', fn.__kwdefaults__)
        legal, decision, calls = fake_engine(self.replay)
        observed = []
        def trace(state, pid, moves, action, received):
            self.assertIs(moves, legal)
            self.assertIs(received, decision)
            self.assertEqual(calls, [])
            observed.append((state, action))
            return {'trace': True, 'pid': pid, 'action': action, 'reasoning': received.reasoning}
        result = fn([], [], 1, 'strong', 1, trace_builder=trace)
        self.assertEqual(len(observed), 1)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][3], legal[0])
        self.assertEqual(sum(line.startswith('AI TRACE ') for line in result['log']), 1)

    def test_09_raw_channel_sink_return_cannot_override_outcome(self):
        fn = self.replay['run_game']
        self.assertIn('record_game', fn.__kwdefaults__)
        fake_engine(self.replay)
        seen = []
        def record(result, raw):
            seen.append((copy.deepcopy(result), list(raw)))
            result['winner'] = 2
            return {'winner': 2}  # Not a valid durable receipt.
        result = fn([], [], 1, 'strong', 1, record_game=record)
        self.assertEqual(result['winner'], 1)
        self.assertIn('RAW-ID', seen[0][1][0])
        self.assertNotIn('RAW-ID', result['log'][0])
        self.assertEqual(result['stop_reason'], 'evidence_error')
        fake_engine(self.replay, action_error=True)
        partial = []
        result = fn([], [], 1, 'strong', 1, record_game=lambda r, raw: partial.append((r, raw)))
        self.assertIsNone(result['winner'])
        self.assertEqual(partial[0][1], ['RAW-ID initial'])
        self.assertEqual(result['stop_reason'], 'action_error')

    def test_10_wilson_series_units_zero_sample_null(self):
        summarize = self.require('summarize_pair')
        rows = [dict(deck_a_seat=1, winner=1, status='resolved'),
                dict(deck_a_seat=2, winner=1, status='resolved'),
                dict(deck_a_seat=1, winner=None, status='draw_cap'),
                dict(deck_a_seat=1, winner=None, status='timeout')]
        seen = []
        def wilson(wins, total):
            seen.append((wins, total))
            return {'wins': wins, 'games': total, 'low': 9.45, 'high': 90.55}
        result = summarize(rows, wilson=wilson)
        self.assertEqual(result['wins_a'], 1)
        self.assertEqual(result['wins_b'], 1)
        self.assertEqual(result['win_rate_ci']['deck_a']['unit'], 'percent')
        self.assertEqual(seen, [(1, 2), (1, 2)])
        self.assertEqual(result['unresolved'], {'draw_cap': 1, 'timeout': 1})
        self.assertIsNone(summarize(rows[2:], wilson=wilson)['win_rate_ci'])
        self.assertEqual(seen, [(1, 2), (1, 2)])

    def test_11_quality_mapping_missing_evidence_null(self):
        quality = self.require('quality_for_pair')
        metric = 'bad_blocks'
        summary = {'counts': {'1': {metric: 3}, '2': {metric: 0}},
                   'availability': {'1': {metric: True}, '2': {metric: False}}}
        rows = [dict(deck_a_seat=2, games=[{'quality': summary, 'evidence_complete': True}])]
        self.assertEqual(quality(rows, metrics=(metric,))['deck_a'][metric], None)
        self.assertEqual(quality(rows, metrics=(metric,))['deck_b'][metric], 3)
        rows[0]['games'][0]['evidence_complete'] = False
        self.assertIsNone(quality(rows, metrics=(metric,))['deck_b'][metric])
        self.assertIsNone(quality([], metrics=(metric,))['deck_a'][metric])

    def test_12_legacy_default_parity_and_budget_continuity(self):
        fn = self.replay['run_game']
        self.assertIn('budget', fn.__kwdefaults__)
        legacy_path = BACKEND / 'tests/fixtures/task31/replay_defaults.py.txt'
        self.assertEqual(hashlib.sha256(legacy_path.read_bytes()).hexdigest(),
                         '59530b9795e15aa3aeb3eb075029c630a07bd0c71fccd74a3a4a1c6794caa149')
        old = project(legacy_path, self.replay,
                      {'run_game', 'run_match'})
        fake_engine(self.replay)
        old.update({k: v for k, v in self.replay.items() if k not in ('run_game', 'run_match')})
        self.assertEqual(fn([], [], 1, 'strong', 1), old['run_game']([], [], 1, 'strong', 1))
        budget = SimpleNamespace(deadline=123, starts=[], accepts=[], before_clone=lambda: None,
            begin_game=lambda log: budget.starts.append(tuple(log)),
            accept_candidate=lambda prior, new, trace: (budget.accepts.append(trace), new.log.insert(len(prior.log), trace)))
        for _ in range(2):
            fake_engine(self.replay)
            fn([], [], 1, 'strong', 1, budget=budget)
        self.assertEqual(len(budget.starts), 2)
        self.assertEqual(budget.deadline, 123)
        self.assertEqual(len(budget.accepts), 2)

    def composition(self):
        """Exact function route with explicit INERT import bindings, not backend load."""
        import builtins
        from analytics.resource_budget import ResourceBudget, RESOURCE_LIMITS
        quality = project(BACKEND / 'analytics/decision_quality.py', dict(json=json, copy=copy,
            Counter=Counter, defaultdict=defaultdict))
        quality['DECISION_QUALITY_METRICS'] = quality['_TRACE_METRICS'] = (
            'missed_land_drops', 'unused_mana_passes', 'lethal_misses', 'bad_blocks', 'stall_streaks', 'redundant_removal_casts')
        service = project(BACKEND / 'analytics/service.py', {'contextmanager': contextmanager}, names={'AnalyticsService'})
        legal, decision, calls = fake_engine(self.replay)
        def trace(state, pid, moves, action, reasoning, **kwargs):
            self.assertIs(moves, legal)
            self.assertEqual(reasoning, decision.reasoning)
            self.assertIs(kwargs['knowledge_usage'], decision.knowledge_usage)
            return dict(trace=True, pid=pid, turn=1, step='precombat_main', action=action,
                        legal_non_pass=True, legal_has_land=False, mana_pool={},
                        stall_actionable_options=False, bad_blocks=0, redundant_removal_casts=None)
        bindings = {
            'analytics.resource_budget': SimpleNamespace(ResourceBudget=ResourceBudget, RESOURCE_LIMITS=RESOURCE_LIMITS),
            'scripts.regression_matrix_replay': SimpleNamespace(run_game=self.replay['run_game'], run_match=self.replay['run_match'],
                contextual_trace=builtins.__import__('scripts.regression_matrix_replay', fromlist=['contextual_trace']).contextual_trace),
            'analytics.decision_quality': SimpleNamespace(build_trace_payload=trace,
                summarize_trace_rows=quality['summarize_trace_rows'], DECISION_QUALITY_METRICS=quality['_TRACE_METRICS']),
            'analytics.service': SimpleNamespace(AnalyticsService=service['AnalyticsService']),
        }
        real_import = builtins.__import__
        def imports(name, globals=None, locals=None, fromlist=(), level=0):
            return bindings[name] if name in bindings else real_import(name, globals, locals, fromlist, level)
        self.runner['__builtins__']['__import__'] = imports
        # Canonical admission is deliberately an inert fixture, not a claim these
        # all-Island test decks implement the shipped eleven builtin inventories.
        self.runner['admit_execution_rows'] = lambda rows: self.assertEqual(len(rows), 11)
        return RESOURCE_LIMITS, calls

    def test_13_complete_callable_route_real_projected_series(self):
        execute = self.require('run_round_robin')
        limits, calls = self.composition()
        export = self.runner['make_export'](roster(), corpus_sha256='a' * 64)
        with tempfile.TemporaryDirectory() as temporary:
            result = execute(export, [0], difficulty='strong', max_ticks=1, limits=dict(limits),
                             private_directory=Path(temporary) / 'private')
            self.assertEqual(result['attempted_series'], 110)
            self.assertTrue(result['complete'])
            self.assertEqual(len(calls), 220)
            self.assertEqual(len(list(Path(temporary).rglob('game-*.json'))), 220)
            for row in result['series']:
                self.assertEqual(len(row['games']), 2)
                self.assertEqual([g['seed'] for g in row['games']], [row['root_seed'], row['root_seed'] + 1])
            self.assertEqual(result['pairs'][0]['wins_a'], 1)
            self.assertEqual(result['pairs'][0]['wins_b'], 1)
            self.assertIsNone(result['pairs'][0]['decision_quality_a']['bad_blocks'])
            self.assertNotIn('RAW-ID', json.dumps(result))

    def test_14_partial_constructor_after_first_game_retains_delivery(self):
        execute = self.require('run_round_robin')
        limits, calls = self.composition()
        original = self.replay['MatchFactory'].from_decks
        starts = []
        def factory(*args, **kwargs):
            starts.append(kwargs['seed'])
            if len(starts) == 2:
                raise ValueError('inert constructor interruption')
            return original(*args, **kwargs)
        self.replay['MatchFactory'] = SimpleNamespace(from_decks=factory)
        with tempfile.TemporaryDirectory() as temporary:
            result = execute(self.runner['make_export'](roster(), corpus_sha256='a' * 64), [0],
                difficulty='strong', max_ticks=1, limits=dict(limits), private_directory=Path(temporary) / 'private')
            self.assertFalse(result['complete'])
            self.assertEqual(len(result['series'][0]['games']), 1)
            self.assertEqual(result['series'][0]['games'][0]['winner'], 1)
            self.assertEqual(len(list(Path(temporary).rglob('game-*.json'))), 1)
            self.assertIsNone(result['series'][0]['winner'])
            self.assertEqual(result['not_run_series'], 109)

    def test_15_writer_failure_partial_status_and_no_retry(self):
        execute = self.require('run_round_robin')
        limits, calls = self.composition()
        attempts = []
        def fail(*args):
            attempts.append(True)
            raise OSError('inert writer failure')
        self.runner['write_private_game'] = fail
        with tempfile.TemporaryDirectory() as temporary:
            result = execute(self.runner['make_export'](roster(), corpus_sha256='a' * 64), [0],
                difficulty='strong', max_ticks=1, limits=dict(limits), private_directory=Path(temporary) / 'private')
            self.assertFalse(result['complete'])
            self.assertEqual(attempts, [True])
            self.assertEqual(len(calls), 1)
            game = result['series'][0]['games'][0]
            self.assertEqual(game['winner'], 1)
            self.assertFalse(game['evidence_complete'])
            self.assertEqual(result['series'][0]['status'], 'evidence_error')
            self.assertTrue(all(value is None for value in result['pairs'][0]['decision_quality_a'].values()))

    def test_16_actual_budget_stop_preserves_raw_and_no_checked_action(self):
        fn = self.replay['run_game']
        self.assertIn('record_game', fn.__kwdefaults__)
        from analytics.resource_budget import ResourceBudget, RESOURCE_LIMITS
        fake_engine(self.replay)
        captured = []
        budget = ResourceBudget(dict(RESOURCE_LIMITS), clock=lambda: 0)
        budget.deadline = 0
        result = fn([], [], 1, 'strong', 1, budget=budget,
                    record_game=lambda result, raw: captured.append((result, raw)))
        self.assertEqual(result['stop_reason'], 'resource_limit')
        self.assertEqual(result['ticks'], 0)
        self.assertEqual(captured[0][1], ['RAW-ID initial'])
        self.assertEqual(budget.batch_entries, 0)

    def test_17_trace_budget_preflight_precedes_serialization(self):
        fn = self.replay['run_game']
        self.assertIn('trace_builder', fn.__kwdefaults__)
        fake_engine(self.replay)
        real_json = self.replay['json']
        dumps = []
        self.replay['json'] = SimpleNamespace(dumps=lambda *args, **kwargs: (dumps.append(args), real_json.dumps(*args, **kwargs))[1])
        class Budget:
            def begin_game(self, log):
                pass
            def before_clone(self):
                pass
            def trace_inputs(self, *args):
                self_test.assertEqual(dumps, [])
                raise ValueError('inert stop before serialization')
        self_test = self
        with self.assertRaises(ValueError):
            fn([], [], 1, 'strong', 1, budget=Budget(), trace_builder=lambda *a: {})

    def test_18_sink_receipt_readback_and_exclusive_preservation(self):
        writer = self.require('write_private_game')
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            raw = ['public fake log']
            receipt = writer(directory, 1, game_fixture(0), raw)
            self.assertEqual(receipt['raw_sha256'], hashlib.sha256(json.dumps(raw, separators=(',', ':')).encode()).hexdigest())
            saved = (directory / receipt['reference']).read_bytes()
            self.assertEqual(receipt['record_sha256'], hashlib.sha256(saved).hexdigest())
            with self.assertRaises(FileExistsError):
                writer(directory, 1, game_fixture(2), ['substitution'])
            self.assertEqual((directory / receipt['reference']).read_bytes(), saved)

    def test_19_default_path_full_recovered_original_ast(self):
        path = BACKEND / 'scripts/regression_matrix_replay.py'
        old = ast.parse((BACKEND / 'tests/fixtures/task31/replay_defaults.py.txt').read_text())
        new = ast.parse(path.read_text())
        originals = {n.name: n for n in old.body if isinstance(n, ast.FunctionDef)}
        functions = {n.name: n for n in new.body if isinstance(n, ast.FunctionDef)}
        game = copy.deepcopy(functions['run_game'])
        game.args.kwonlyargs = game.args.kwonlyargs[:-3]
        game.args.kw_defaults = game.args.kw_defaults[:-3]
        # Verify the exact opt-in metadata additions before restoring the old AST.
        self.assertEqual(ast.dump(game.body[1]), ast.dump(ast.parse(
            "if record_game is not None:\n    import time\n    game_started = time.monotonic()"
        ).body[0]))
        game.body.pop(1)
        self.assertEqual(ast.dump(game.body[7]), ast.dump(ast.parse(
            "resource_limit_dimension = None"
        ).body[0]))
        game.body.pop(7)
        metadata_wrapper = next(n for n in game.body if isinstance(n, ast.Try))
        self.assertEqual(ast.dump(metadata_wrapper.handlers[0].body[-1]), ast.dump(ast.parse(
            "if type(exc) is SimulationResourceLimit:\n"
            "    dimension = getattr(exc, 'dimension', None)\n"
            "    if type(dimension) is str and dimension in (\n"
            "        'deadline', 'game_log', 'game_log_entries', 'batch_log', 'batch_log_entries',\n"
            "        'trace_scalar', 'trace_nodes', 'trace_depth', 'trace_entry', 'action_log',\n"
            "    ):\n        resource_limit_dimension = dimension"
        ).body[0]))
        metadata_wrapper.handlers[0].body.pop()
        elapsed_index = game.body.index(metadata_wrapper) + 1
        self.assertEqual(ast.dump(game.body[elapsed_index]), ast.dump(ast.parse(
            "if record_game is not None:\n    game_elapsed_seconds = time.monotonic() - game_started"
        ).body[0]))
        game.body.pop(elapsed_index)
        self.assertEqual(ast.dump(game.body[-2]), ast.dump(ast.parse(
            "if record_game is not None:\n"
            "    result.update(resource_limit_dimension=resource_limit_dimension,\n"
            "                  game_elapsed_seconds=game_elapsed_seconds)\n"
            "    _record_game_evidence(result, state.log, record_game)"
        ).body[0]))
        game.body[-2].body.pop(0)
        # Remove the opt-in budget/error wrapper, retaining its original body.
        wrapper = next(n for n in game.body if isinstance(n, ast.Try))
        prefix = game.body[:game.body.index(wrapper)]
        prefix = [n for n in prefix if not (isinstance(n, ast.Assign) and
                   any(isinstance(t, ast.Name) and t.id in ('ticks', 'stop_reason') for t in n.targets))]
        work = wrapper.body[1:]  # Exact new begin_game conditional is tested separately.
        loop = next(n for n in work if isinstance(n, ast.While))
        loop.body.pop(0)  # New before_clone conditional.
        loop.body = [n for n in loop.body if not (isinstance(n, ast.Assign) and
                     any(isinstance(t, ast.Name) and t.id == 'decision' for t in n.targets))]
        branch = next(n for n in loop.body if isinstance(n, ast.If) and isinstance(n.test, ast.UnaryOp))
        original_choice = next(n for n in originals['run_game'].body if isinstance(n, ast.While)).body[3]
        branch.orelse[-1].value = copy.deepcopy(original_choice.orelse[-1].value)
        # The removed assignment's call must equal the old action's exact call.
        original_call = original_choice.orelse[-1].value.value
        # Compare the call in the actual unedited candidate AST, before dropping it.
        raw_loop = next(n for n in functions['run_game'].body if isinstance(n, ast.Try)).body[-1]
        raw_choice = next(n for n in raw_loop.body if isinstance(n, ast.If) and isinstance(n.test, ast.UnaryOp))
        self.assertEqual(ast.dump(raw_choice.orelse[-2].value), ast.dump(original_call))
        self.assertEqual(ast.dump(raw_choice.orelse[-1].value),
                         ast.dump(ast.Attribute(value=ast.Name(id='decision', ctx=ast.Load()), attr='action', ctx=ast.Load())))
        branch.orelse.pop(-2)
        trace_index = next(i for i, n in enumerate(loop.body) if isinstance(n, ast.If)
                           and isinstance(n.test, ast.Compare) and isinstance(n.test.left, ast.Name)
                           and n.test.left.id == 'trace_builder')
        loop.body[trace_index:trace_index+1] = loop.body[trace_index].orelse
        insertion = next(i for i, n in enumerate(loop.body) if isinstance(n, ast.If)
                         and isinstance(n.test, ast.Compare) and isinstance(n.test.left, ast.Name)
                         and n.test.left.id == 'budget')
        loop.body[insertion:insertion+1] = loop.body[insertion].body
        tail = game.body[game.body.index(wrapper)+1:]
        result = next(n for n in tail if isinstance(n, ast.Assign) and n.targets[0].id == 'result')
        game.body = prefix + work + tail[:tail.index(result)] + [ast.Return(value=result.value)]
        self.assertEqual(ast.dump(game), ast.dump(originals['run_game']))
        match = copy.deepcopy(functions['run_match'])
        match.args.kwonlyargs = match.args.kwonlyargs[:-1]
        match.args.kw_defaults = match.args.kw_defaults[:-1]
        loop = next(n for n in match.body if isinstance(n, ast.For))
        assignment = next(n for n in loop.body if isinstance(n, ast.Assign) and n.targets[0].id == 'game')
        assignment.value.func = ast.Name(id='run_game', ctx=ast.Load())
        stop = next(n for n in loop.body if isinstance(n, ast.If) and isinstance(n.test, ast.BoolOp))
        stop.test = stop.test.values[0]
        self.assertEqual(ast.dump(match), ast.dump(originals['run_match']))

    def test_20_real_budget_cumulative_across_games(self):
        fn = self.replay['run_game']
        self.assertIn('budget', fn.__kwdefaults__)
        from analytics.resource_budget import ResourceBudget, RESOURCE_LIMITS
        budget = ResourceBudget(dict(RESOURCE_LIMITS), clock=lambda: 0)
        deadline = budget.deadline
        records = []
        def record(result, raw):
            encoded = json.dumps(raw, separators=(',', ':')).encode()
            records.append(raw)
            return dict(reference='game-01.json', complete=True, bytes=len(encoded), raw_sha256=hashlib.sha256(encoded).hexdigest())
        for _ in range(2):
            fake_engine(self.replay)
            fn([], [], 1, 'strong', 1, budget=budget, record_game=record)
        self.assertEqual(budget.deadline, deadline)
        self.assertEqual(budget.batch_entries, 6)
        self.assertEqual(budget.game_entries, 3)
        self.assertEqual(len(records), 2)

    def test_21_unknown_classification_remains_unknown(self):
        rows = roster()
        rows[0].update(classification_status='unknown', archetype='unknown')
        export = self.require('make_export')(rows, corpus_sha256='a' * 64)
        admitted = self.runner['validate_export'](export)
        self.assertEqual(next(row for row in admitted if row['name'] == rows[0]['name'])['archetype'], 'unknown')
        self.assertEqual(len(self.runner['build_schedule'](admitted, [0])), 110)

    def test_22_cli_default_plans_without_game_import(self):
        main = self.require('main')
        import sys
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            export = self.runner['make_export'](roster(), corpus_sha256='a' * 64)
            (root / 'input.json').write_text(json.dumps(export))
            original = sys.argv
            try:
                sys.argv = ['matchup', '--deck-export', str(root/'input.json'), '--seed-token', '5', '--output', str(root/'plan.json')]
                self.assertEqual(main(), 0)
            finally:
                sys.argv = original
            result = json.loads((root / 'plan.json').read_text())
            self.assertEqual(result['status'], 'planned_not_executed')
            self.assertEqual(result['planned_series'], 110)
            self.assertEqual(result['planned_pairs'], 55)

    def test_23_receipt_extras_never_escape_into_summary(self):
        fn = self.replay['run_game']
        self.assertIn('record_game', fn.__kwdefaults__)
        fake_engine(self.replay)
        def record(result, raw):
            data = json.dumps(raw, separators=(',', ':')).encode()
            return dict(complete=True, bytes=len(data), raw_sha256=hashlib.sha256(data).hexdigest(),
                        reference='game-01.json', private_payload={'hand': 'secret'}, record_sha256='ignored')
        result = fn([], [], 1, 'strong', 1, record_game=record)
        self.assertEqual(set(result['evidence']), {'complete', 'bytes', 'raw_sha256', 'reference'})
        self.assertNotIn('secret', json.dumps(result))
        self.assertEqual(result['winner'], 1)

    def test_24_receipt_reference_path_and_typed_fields_fail_closed(self):
        fn = self.replay['run_game']
        self.assertIn('record_game', fn.__kwdefaults__)
        for bad in ({'reference': '/private/game-01.json'}, {'reference': '../game-01.json'},
                    {'reference': 'payload-secret.json'}, {'complete': 1}, {'bytes': True}, {'raw_sha256': 'foreign'}):
            fake_engine(self.replay)
            def record(result, raw):
                data = json.dumps(raw, separators=(',', ':')).encode()
                return dict(dict(complete=True, bytes=len(data), raw_sha256=hashlib.sha256(data).hexdigest(),
                                 reference='game-01.json'), **bad)
            result = fn([], [], 1, 'strong', 1, record_game=record)
            self.assertEqual(result['winner'], 1)
            self.assertIn('stop_reason', result)
            self.assertEqual(result['stop_reason'], 'evidence_error')
            self.assertIsNone(result['evidence'])
