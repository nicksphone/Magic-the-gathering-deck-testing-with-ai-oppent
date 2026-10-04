"""Bounded read-only decision diagnostic. Run ONLY in disposable archived source.

Example: python -m scripts.ai_planning_performance_agent --snapshot INPUT.json
 --output OUT --repeat 3 [--profile] [--duplicates] [--advance 1]
Timing excludes hydration/legal generation/validation; these are reported separately.
Cold means first decision in a fresh process, not a cold OS page cache.
"""
from __future__ import annotations
import argparse
import cProfile
import hashlib
import json
import os
from pathlib import Path
import platform
import pstats
import sys
import time
from collections import Counter


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--snapshot', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--repeat', type=int, default=3)
    p.add_argument('--advance', type=int, default=0, choices=range(0, 5))
    p.add_argument('--profile', action='store_true')
    p.add_argument('--duplicates', action='store_true')
    args = p.parse_args()
    root = Path(__file__).resolve().parents[2]
    if not root.is_relative_to(Path('/home/nick/.hermes/cache/scratch')) or (root / '.git').exists():
        p.error('Use a disposable git-archive source under local Hermes scratch')
    if not 1 <= args.repeat <= 10:
        p.error('repeat must be 1..10')
    args.output.mkdir(parents=True, exist_ok=False)
    from ai.agent import AIAgent
    from ai.deck_analysis import guess_archetype
    from ai import pending_effects
    from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
    from rules_engine.engine import RulesEngine
    from rules_engine.action_validation import checked_action
    from game_state.state import pregame_actor
    raw = json.loads(args.snapshot.read_text())
    state = deserialize_match_snapshot(raw)
    engine = RulesEngine()
    for _ in range(args.advance):
        pid = pregame_actor(state) if state.pregame_pending else state.priority_player
        agent = AIAgent('master', guess_archetype(state.starting_decks[pid]),
                        guess_archetype(state.starting_decks[3-pid]))
        decision = agent.choose_action(state, engine.legal_moves(state, pid), pid)
        state = checked_action(state, engine, pid, decision.action)
    raw = serialize_match_snapshot(state)
    (args.output / 'selected-snapshot.json').write_text(canonical(raw))
    pid = pregame_actor(state) if state.pregame_pending else state.priority_player
    style = guess_archetype(state.starting_decks[pid])
    other = guess_archetype(state.starting_decks[3-pid])
    rows = []
    for index in range(args.repeat):
        state = deserialize_match_snapshot(raw)
        agent = AIAgent('master', style, other)
        before = serialize_match_snapshot(state)
        start = time.perf_counter()
        legal = engine.legal_moves(state, pid)
        legal_wall = time.perf_counter() - start
        assert serialize_match_snapshot(state) == before, 'legal generation mutated source'
        counts = Counter()
        elapsed = Counter()
        examples = {}
        retained_policies = []  # Prevent object-id reuse in diagnostic keys.
        original = pending_effects.friendly_destruction_profit
        def counted(s, player, action, *, own_choice_action=None):
            # Exact serialized state + full announced action, same state object,
            # same bound receiver/function. No hidden identity enters AI ranking.
            # Normalize this production closure by code + retained capture identity
            # AND captured object's current attributes; do not equate fresh lambdas
            # by transient callable id. This is diagnostic, not a cache patch.
            policy = own_choice_action
            retained_policies.append((policy, s))
            captures = tuple(cell.cell_contents for cell in (getattr(policy, '__closure__', None) or ()))
            policy_key = (id(getattr(policy, '__self__', None)),
                          id(getattr(policy, '__func__', getattr(policy, '__code__', policy))),
                          tuple((id(v), digest(vars(v)) if hasattr(v, '__dict__') else canonical(v)) for v in captures))
            key = (id(s), digest(serialize_match_snapshot(s)), player,
                   canonical(action), policy_key)
            counts[key] += 1
            t = time.perf_counter()
            result = original(s, player, action, own_choice_action=policy)
            elapsed[key] += time.perf_counter() - t
            if key in examples:
                assert examples[key]['result'] == result, 'identical projection changed result'
            examples[key] = {'state_sha256': key[1], 'player': player,
                             'action': action, 'policy': getattr(policy, '__qualname__', None),
                             'result': result}
            return result
        if args.duplicates:
            pending_effects.friendly_destruction_profit = counted
        profiler = cProfile.Profile() if args.profile else None
        wall, cpu = time.perf_counter(), time.process_time()
        try:
            if profiler:
                profiler.enable()
            decision = agent.choose_action(state, legal, pid)
        finally:
            if profiler:
                profiler.disable()
            pending_effects.friendly_destruction_profit = original
        cpu = time.process_time() - cpu
        wall = time.perf_counter() - wall
        assert serialize_match_snapshot(state) == before, 'decision mutated source'
        t = time.perf_counter()
        paid = checked_action(state, engine, pid, decision.action)
        checked_wall = time.perf_counter() - t
        assert serialize_match_snapshot(state) == before, 'checked action mutated source'
        row = {'index': index, 'cache': ('advance-warmed' if args.advance else 'process-first') if index == 0 else 'process-warm',
               'wall_s': wall, 'cpu_s': cpu, 'legal_wall_s': legal_wall,
               'checked_wall_s': checked_wall, 'legal_count': len(legal),
               'action': decision.action, 'action_sha256': digest(decision.action),
               'result_sha256': digest(serialize_match_snapshot(paid)),
               'source_sha256': digest(before), 'checked': True, 'unmutated': True}
        if args.duplicates:
            row['projections'] = {'calls': sum(counts.values()), 'unique': len(counts),
                'duplicates': sum(v-1 for v in counts.values()),
                'inner_wall_s': sum(elapsed.values()),
                'groups': [{**examples[k], 'calls': v, 'inner_wall_s': elapsed[k]}
                           for k, v in counts.most_common()]}
        if profiler:
            profiler.dump_stats(str(args.output / f'{index}.prof'))
            with (args.output / f'{index}-profile.txt').open('w') as out:
                pstats.Stats(profiler, stream=out).strip_dirs().sort_stats('cumulative').print_stats(90)
            stats = pstats.Stats(profiler)
            row['profile_functions'] = [{'file': k[0], 'line': k[1], 'function': k[2],
                'primitive_calls': v[0], 'calls': v[1], 'self_s': v[2], 'cumulative_s': v[3]}
                for k, v in stats.stats.items()]
        rows.append(row)
        (args.output / 'results.json').write_text(json.dumps({'python': sys.version,
            'platform': platform.platform(), 'affinity': sorted(os.sched_getaffinity(0)),
            'argv': sys.argv, 'input_sha256': hashlib.sha256(args.snapshot.read_bytes()).hexdigest(),
            'profile': args.profile, 'duplicates': args.duplicates, 'turn': state.turn,
            'step': str(state.step), 'actor': pid, 'archetype': style,
            'opponent_archetype': other, 'boards': {str(k): len(v.battlefield) for k,v in state.players.items()},
            'stack_count': len(state.stack), 'rows': rows}, indent=2))
        print(canonical({k:v for k,v in row.items() if k not in ('profile_functions','projections')}), flush=True)


if __name__ == '__main__':
    main()
