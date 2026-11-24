"""Issue and run a pre-registered same-deck AI strength experiment."""
import argparse
from collections import Counter
from functools import partial
import json
import math
from pathlib import Path
import random
import subprocess
import sys

from scripts import archetype_pilot_v3 as pilot
from scripts.archetype_plan_v3 import (
    STRENGTH_CAMPAIGN_ID, STRENGTH_OPPONENTS, STRENGTH_RERUN2_ID,
    STRENGTH_RUN_ID, build_plan, strength_campaign_hours, validate_plan,
)
from scripts.archetype_trace_v3 import digest, load_json


class StrengthBudget(pilot.SlotBudget):
    shutdown_reserve_seconds = 60

    def __init__(self, *, started, prior_charged_seconds, wall_seconds, run_id=STRENGTH_RUN_ID):
        super().__init__(started=started, prior_charged_seconds=prior_charged_seconds)
        self.wall_seconds = wall_seconds
        self.campaign_seconds = strength_campaign_hours(run_id) * 3600

    def exceeded(self, now):
        return self.remaining_campaign_seconds(now) <= self.shutdown_reserve_seconds

    def can_launch(self, *, now, unstarted, pending_deadlines):
        horizon = max(self.wall_seconds, *(max(0., t-now) for t in pending_deadlines), 0.)
        return self.remaining_campaign_seconds(now) >= 2*horizon + self.shutdown_reserve_seconds


def _score(cell, row):
    if not row or row.get('run_invalid') is not False or row.get('parity_checked') is not True:
        return None
    if (row.get('cpu_attribution_complete') is not True or row.get('child_handles_reaped') is not True
            or not pilot._number(row.get('cpu_seconds'))):
        return None
    winner = row.get('winner')
    if row.get('status') == 'draw' and winner is None:
        return .5
    if row.get('status') == 'resolved' and type(winner) is int and winner in (1, 2):
        return float(winner == cell['deck_a_seat'])
    return None


def _summary(scores):
    resolved = [s for s in scores if s is not None]
    total, missing = len(scores), len(scores) - len(resolved)
    points = sum(resolved)
    return {'score': points/len(resolved) if resolved else None, 'resolved': len(resolved),
            'unresolved': missing, 'score_bounds': [points/total, (points+missing)/total]}


def _interval(blocks, *, seed, replicates):
    """Resample matched seed clusters and propagate unresolved score extremes."""
    rng = random.Random(seed)
    lower, upper = [], []
    totals = [(sum(x for x in b if x is not None), b.count(None)) for b in blocks]
    denominator = sum(map(len, blocks))
    for _ in range(replicates):
        sample = rng.choices(totals, k=len(totals))
        points = sum(x for x, _ in sample)
        lower.append(points/denominator)
        upper.append((points+sum(n for _, n in sample))/denominator)
    lower.sort()
    upper.sort()
    return [lower[math.ceil(.025*replicates)-1], upper[math.ceil(.975*replicates)-1]]


def strength_report(rows, plan):
    validate_plan(plan)
    if plan['kind'] != 'strength':
        raise ValueError('Strength report requires its frozen schedule')
    cells = plan['cells']
    by_id = {r['cell_id']: r for r in rows}
    expected = {c['cell_id'] for c in cells}
    if len(by_id) != len(rows) or not by_id.keys() <= expected:
        raise ValueError('Duplicate or undeclared strength result')
    complete = by_id.keys() == expected and all(r.get('run_invalid') is False for r in rows)
    comparisons = {}
    for opponent in STRENGTH_OPPONENTS:
        cohort = [c for c in cells if c['opponent'] == opponent]
        scores = {c['cell_id']: _score(c, by_id.get(c['cell_id'])) for c in cohort}
        blocks = [[scores[c['cell_id']] for c in cohort if c['seed'] == seed]
                  for seed in plan['seeds']]
        result = _summary(list(scores.values()))
        result['ci_95'] = _interval(blocks, seed=plan['policy']['bootstrap_seed'],
                                    replicates=plan['policy']['bootstrap_replicates'])
        result['deck_scores'] = {
            name: _summary([scores[c['cell_id']] for c in cohort if c['deck_a'] == name])
            for name in sorted(plan['source_matrix']['decks'])}
        gate = plan['strength_gate'][opponent]
        if opponent == 'master':
            # The mirror swaps labels only. On the same physical seed it should
            # produce complementary scores, even if one seat always wins.
            mirrors = [list(scores[c['cell_id']] for c in cohort
                            if c['deck_a'] == name and c['seed'] == seed)
                       for name in result['deck_scores'] for seed in plan['seeds']]
            result['passed'] = (all(None not in pair and sum(pair) == 1 for pair in mirrors)
                                and result['ci_95'][0] <= gate['ci_contains'] <= result['ci_95'][1])
        else:
            result['passed'] = (result['score_bounds'][0] >= gate.get('score_lower', 0)
                                and result['ci_95'][0] > gate['ci_lower_strict'])
        comparisons[opponent] = result
    children_closed = all(r.get('child_handles_reaped') is True and pilot._number(r.get('cpu_seconds'))
                          for r in rows)
    passed = complete and children_closed and all(r['passed'] for r in comparisons.values())
    return {'scheduled': len(cells), 'accounted': len(rows), 'complete': complete,
            'usable': passed, 'strength_passed': passed, 'campaign_id': STRENGTH_CAMPAIGN_ID,
            'statuses': dict(sorted(Counter(r['status'] for r in rows).items())),
            'trace_bytes': sum(r['trace_bytes'] for r in rows), 'comparisons': comparisons,
            'statistical_gate_complete': False, 'accepts_matrix_or_strength': False}


def run_strength(plan, directory):
    budget_factory = partial(StrengthBudget, run_id=plan.get('run_id') if type(plan) is dict else None)
    return pilot._admit_run(plan, directory, kind='strength', budget_factory=budget_factory,
                            reporter=strength_report, prefix='STRENGTH')


def main(argv=None):
    if sys.flags.optimize or not sys.flags.dont_write_bytecode:
        raise SystemExit('Run v3 strength without optimization and with -B')
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    make = commands.add_parser('plan')
    make.add_argument('output', type=Path)
    make.add_argument('--run-id', choices=(STRENGTH_RUN_ID, STRENGTH_RERUN2_ID), default=STRENGTH_RUN_ID)
    run = commands.add_parser('run')
    run.add_argument('plan', type=Path)
    run.add_argument('output', type=Path)
    run.add_argument('--execute-strength', action='store_true', required=True)
    args = parser.parse_args(argv)
    if args.command == 'plan':
        root = pilot.BACKEND.parent
        if (not args.output.is_absolute() or args.output.resolve() != args.output
                or args.output.is_relative_to(root)):
            raise ValueError('Private plan output outside checkout required')
        revision = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
        pilot.source_identity(revision)
        plan = build_plan(revision, args.run_id, kind='strength',
                          runtime_sha256=digest(pilot.runtime_identity()))
        pilot.publish(args.output, plan)
        return 0
    with args.plan.open('rb') as stream:
        data = stream.read(4*1024*1024+1)
    if len(data) > 4*1024*1024:
        raise ValueError('Strength plan exceeds its bound')
    report = run_strength(load_json(data), args.output)
    print(json.dumps({key:report[key] for key in ('complete','strength_passed','accounted','statuses')}))
    return 0 if report['strength_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
