"""Separate 72-cell all-pair health entry; never statistical or strength acceptance."""
import json
from pathlib import Path
import sys

from scripts import archetype_pilot_v3 as pilot
from scripts.archetype_plan_v3 import STANDARD_WALL_SECONDS
from scripts.archetype_trace_v3 import load_json


class HealthBudget(pilot.SlotBudget):
    """Same two-slot charging, cumulative30h health and48h campaign ceilings."""
    shutdown_reserve_seconds=60.  # worker-slot seconds; not a per-cell extension

    def __init__(self,*,started,prior_charged_seconds=0.,prior_health_charged_seconds=0.,
                 wall_seconds=STANDARD_WALL_SECONDS):
        if (not pilot._number(prior_charged_seconds) or not pilot._number(prior_health_charged_seconds)
                or prior_health_charged_seconds>prior_charged_seconds):
            raise ValueError('Invalid carried health/campaign charges')
        super().__init__(started=started,prior_charged_seconds=prior_charged_seconds)
        self.prior_health_charged_seconds=prior_health_charged_seconds
        self.wall_seconds=wall_seconds

    def remaining_health_seconds(self,now):
        return max(0.,self.reserved_health_seconds-self.prior_health_charged_seconds-self.charged_seconds(now))

    def remaining_seconds(self,now):
        return min(self.remaining_health_seconds(now),self.remaining_campaign_seconds(now))

    def exceeded(self,now):
        return self.remaining_seconds(now)<=self.shutdown_reserve_seconds

    def can_launch(self,*,now,unstarted,pending_deadlines):
        # Both slots stay charged even with one worker idle. Cover the longest
        # next/in-flight wall horizon, not all72 worst cases plus zero overhead.
        horizon=max([self.wall_seconds,*[max(0.,d-now)for d in pending_deadlines]])
        return self.remaining_seconds(now)>=2*horizon+self.shutdown_reserve_seconds


def health_report(rows,plan):
    if plan.get('kind')!='health':
        raise ValueError('Health report requires a health schedule')
    report=pilot.pilot_report(rows,plan)
    report.update(health_passed=report['usable'],health_only=True,
                  forecast_reason='health_only_not_statistical_forecast')
    for key in ('forecast_1440_worker_hours','forecast_72_worker_hours','forecast_trace_bytes'):
        report[key]=None
    return report


def run_health(plan,directory):
    return pilot._admit_run(plan,directory,kind='health',budget_factory=HealthBudget,
                            reporter=health_report,prefix='HEALTH')


def main(argv=None):
    if sys.flags.optimize or not sys.flags.dont_write_bytecode:
        raise SystemExit('Run v3 health without optimization and with -B')
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('run',))
    parser.add_argument('plan',type=Path);parser.add_argument('output',type=Path)
    parser.add_argument('--execute-health',action='store_true',required=True)
    args=parser.parse_args(argv)
    with args.plan.open('rb')as stream:data=stream.read(4*1024*1024+1)
    if len(data)>4*1024*1024:
        raise ValueError('Health plan exceeds its bound')
    report=run_health(load_json(data),args.output)
    print(json.dumps({key:report[key]for key in ('complete','health_passed','accounted','statuses','accepts_matrix_or_strength')}))
    return 0 if report['health_passed']else 1


if __name__=='__main__':
    raise SystemExit(main())
