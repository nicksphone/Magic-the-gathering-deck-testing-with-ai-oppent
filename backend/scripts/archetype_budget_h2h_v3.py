"""Prepare and explicitly run the pre-registered Master budget comparison."""
import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys

from scripts import archetype_pilot_v3 as pilot
from scripts.archetype_plan_v3 import (
    BUDGET_H2H_CAMPAIGN_HOURS, BUDGET_H2H_KIND as KIND, BUDGET_H2H_RUN_ID as RUN_ID,
    BUDGET_H2H_PAUSE as PAUSE, budget_schedule_digest as schedule_digest, build_plan, validate_plan,
)
from scripts.archetype_strength_v3 import _interval, _score, _summary
from scripts.archetype_trace_v3 import digest, load_json
from scripts.archetype_worker_v3 import budget_totals


class Budget(pilot.SlotBudget):
    reserved_health_seconds = 0
    campaign_seconds = BUDGET_H2H_CAMPAIGN_HOURS * 3600

    def __init__(self, *, started, prior_charged_seconds, wall_seconds, workers):
        super().__init__(started=started, prior_charged_seconds=prior_charged_seconds, workers=workers)
        self.wall_seconds = wall_seconds

    def exceeded(self, now):
        return self.remaining_campaign_seconds(now) <= 60

    def can_launch(self, *, now, unstarted, pending_deadlines):
        horizon = max(self.wall_seconds, *(max(0, deadline - now) for deadline in pending_deadlines), 0)
        return self.remaining_campaign_seconds(now) >= self.workers * horizon + 60


def _valid_terminal(row):
    if (row.get('run_invalid') is not False or row.get('child_handles_reaped') is not True
            or not pilot._number(row.get('cpu_seconds'))):
        return False
    status = row.get('status')
    if status == 'timeout':
        return row.get('winner') is None and row.get('termination') in {
            'cpu_limit', 'wall_limit', 'memory_limit', 'trace_limit'}
    if row.get('parity_checked') is not True or row.get('cpu_attribution_complete') is not True:
        return False
    if status in {'resolved', 'draw'}:
        return status == 'resolved' and type(row.get('winner')) is int and row['winner'] in (1, 2) or (
            status == 'draw' and row.get('winner') is None)
    return (row.get('winner') is None and
            (status == row.get('termination') and status in {'tick_limit', 'turn_limit'}
             or status == 'error' and row.get('termination') == PAUSE))


def report(rows, plan):
    validate_plan(plan)
    if plan['kind'] != KIND:
        raise ValueError('Budget comparison requires its own frozen schedule')
    cells = plan['cells']
    by_id = {row['cell_id']: row for row in rows}
    expected = {cell['cell_id'] for cell in cells}
    if len(by_id) != len(rows) or not by_id.keys() <= expected:
        raise ValueError('Duplicate or undeclared budget result')
    complete = by_id.keys() == expected and all(map(_valid_terminal, rows))
    scores = {}
    seed_groups, decks = {}, {}
    for cell in cells:
        identity = cell['cell_id']
        row = by_id.get(identity)
        score = _score(cell, row) if row is not None and _valid_terminal(row) else None
        scores[identity] = score
        seed_groups.setdefault(cell['seed'], []).append(score)
        decks.setdefault(cell['deck_a'], []).append(score)
    comparison = _summary(list(scores.values()))
    comparison['ci_95'] = _interval(list(seed_groups.values()),
                                   seed=plan['policy']['bootstrap_seed'],
                                   replicates=plan['policy']['bootstrap_replicates'])
    comparison['decks'] = {name: _summary(values) for name, values in sorted(decks.items())}
    gate = plan['budget_gate']
    passed = bool(complete and comparison['score_bounds'][0] >= gate['score_lower']
                  and comparison['ci_95'][0] > gate['ci_lower_strict'])
    totals = budget_totals()
    telemetry_cells = 0
    for row in rows:
        stages = row.get('stages', ())
        evidence = stages[-1]['result'].get('budget_decisions') if (
            row.get('parity_checked') is True and len(stages) == 2) else None
        if evidence is None:
            continue
        telemetry_cells += 1
        for role, target in totals.items():
            source = evidence[role]
            for key in ('decisions', 'retained_available', 'cpu_seconds', 'wall_seconds'):
                target[key] += source[key]
            for reason in target['cutoffs']:
                target['cutoffs'][reason] += source['cutoffs'][reason]
    return {'scheduled': len(cells), 'accounted': len(rows), 'complete': complete, 'usable': passed,
            'budget_passed': passed, 'comparison': comparison, 'campaign_id': plan['campaign_id'],
            'statuses': dict(sorted(Counter(PAUSE if row['termination'] == PAUSE else row['status']
                                            for row in rows).items())),
            'pauses': sum(row['termination'] == PAUSE for row in rows),
            'decision_telemetry_by_policy': totals, 'decision_telemetry_verified_cells': telemetry_cells,
            'trace_bytes': sum(row['trace_bytes'] for row in rows),
            'accepts_matrix_or_strength': False}


def run_budget_comparison(plan, directory):
    return pilot._admit_run(plan, directory, kind=KIND, budget_factory=Budget,
                           reporter=report, prefix='BUDGET-H2H')


def main(argv=None):
    if sys.flags.optimize or not sys.flags.dont_write_bytecode:
        raise SystemExit('Run v3 budget comparison without optimization and with -B')
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    issue = commands.add_parser('plan')
    issue.add_argument('output', type=Path)
    run = commands.add_parser('run')
    run.add_argument('plan', type=Path)
    run.add_argument('output', type=Path)
    run.add_argument('--execute-budget-head-to-head', action='store_true', required=True)
    args = parser.parse_args(argv)
    from persistence.job_retention import local_path

    root = pilot.BACKEND.parent
    if args.command == 'plan':
        if (not args.output.is_absolute() or args.output.resolve() != args.output
                or args.output.is_relative_to(root)):
            raise ValueError('Private plan output outside checkout required')
        rev = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
        pilot.source_identity(rev)
        pilot.publish(local_path(args.output, existing=False), build_plan(rev, RUN_ID, kind=KIND,
                                             runtime_sha256=digest(pilot.runtime_identity())))
        return 0
    plan_path = local_path(args.plan)
    if plan_path.is_relative_to(root):
        raise ValueError('Private plan input outside checkout required')
    with plan_path.open('rb') as stream:
        data = stream.read(4 * 1024 * 1024 + 1)
    if len(data) > 4 * 1024 * 1024:
        raise ValueError('Budget comparison plan exceeds its bound')
    outcome = run_budget_comparison(load_json(data), args.output)
    print(json.dumps({key: outcome[key] for key in ('complete', 'budget_passed', 'accounted', 'statuses', 'pauses')}))
    return 0 if outcome['budget_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
