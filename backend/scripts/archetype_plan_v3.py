"""Fresh v3 pre-registration; health-plan creation never authorizes its run."""
from copy import deepcopy
from itertools import combinations
from pathlib import Path
import re

from scripts.archetype_matrix_plan import build_plan as build_source_matrix
from scripts.archetype_trace_v3 import CHECKPOINT_INTERVAL, MAX_TRACE_BYTES, digest, is_sha

MAX_CPU_SECONDS = 1200
MAX_WALL_SECONDS = 1500
MEMORY_BYTES = 2147483648
PILOT_SEEDS = (2026112001, 2026112002)
HEALTH_SEEDS = (2026112101,)


def build_plan(revision, run_id, *, kind='pilot', builtin_source=None, runtime_sha256=None):
    if type(kind) is not str or kind not in ('pilot','health'):
        raise ValueError('Only v3 pilot or separately admitted health plans exist')
    pattern = f'archetype-{kind}-20261116-v3-[A-Za-z0-9-]{{1,48}}'
    if type(run_id) is not str or re.fullmatch(pattern, run_id) is None:
        raise ValueError('A fresh role-specific v3 run ID is required')
    if runtime_sha256 is not None and not is_sha(runtime_sha256):
        raise ValueError('Exact issued runtime digest required')
    source = ((Path(__file__).resolve().parents[1]/'decks/builtin_decks.py').read_text()
              if builtin_source is None else builtin_source)
    if type(revision) is not str or re.fullmatch('[0-9a-f]{40}',revision) is None:
        raise ValueError('A complete measured revision is required')
    matrix = build_source_matrix(revision, source)
    names = sorted(matrix['decks'])
    pairs = ([tuple(sorted((name,names[(i+1)%len(names)]))) for i,name in enumerate(names)]
             if kind=='pilot' else list(combinations(names,2)))
    seeds = PILOT_SEEDS if kind=='pilot' else HEALTH_SEEDS
    cells = []
    for a,b in pairs:
        for seed in seeds:
            for seat in (1,2):
                fields = {'deck_a':a,'deck_b':b,'seed':seed,'deck_a_seat':seat}
                cells.append({'cell_id':digest({'run_id':run_id,'kind':kind,**fields}),**fields})
    policy = deepcopy(matrix['policy'])
    policy.update(max_seconds=MAX_WALL_SECONDS, max_cpu_seconds_per_game=MAX_CPU_SECONDS)
    policy['health_gate']['max_resource_limit_cells'] = 0
    trace = {'schema':3,'checkpoint_interval':CHECKPOINT_INTERVAL,'max_bytes':MAX_TRACE_BYTES,
             'progress_interval':16,'state_hash':'sha256_canonical_complete_snapshot',
             'chain_hash':'sha256_domain_mtg-archetype-v3-record',
             'extra_checkpoints':['handler_first_every100_last','choice_change','pregame_completion','final'],
             'sequential_replay_every_action':True,'serde_every_action':True,
             'ai_mutation_check':True,'quota_overflow':'trace_limit_incomplete_no_truncation'}
    return {'schema':3,'kind':kind,'run_id':run_id,'revision':revision,'runtime_sha256':runtime_sha256,
            'source_matrix_sha256':digest(matrix),'source_matrix':matrix,
            'seeds':list(seeds),'cells':cells,'policy':policy,'trace_policy':trace,
            'worker_hour_budget':{'campaign':48,'pilot_cells':15,'health_cells':30,'overhead':3},
            'batch_execution_authorized':False,'accepts_matrix_or_strength':False,
            'statistical_gate_complete':False,
            'scope':'adjacent_pairs_two_seeds_both_seats' if kind=='pilot' else 'all36_pairs_one_seed_both_seats_health_only',
            'seed_cluster_interval':'not_matrix_acceptance' if kind=='pilot' else 'unavailable_one_independent_seed'}


def validate_plan(plan):
    if type(plan) is not dict:
        raise ValueError('Complete v3 plan required')
    try:
        expected = build_plan(plan['revision'],plan['run_id'],kind=plan['kind'],
                              runtime_sha256=plan['runtime_sha256'])
        if digest(plan) != digest(expected):
            raise ValueError('V3 schedule, source, budget or scope changed')
    except (KeyError, TypeError) as exc:
        raise ValueError('Complete frozen v3 plan required') from exc


def execution_matrix(plan):
    validate_plan(plan)
    # This v2 source matrix is lineage/deck authority only. Its old budget and
    # cells are never used to execute v3; active budgets live in plan['policy'].
    return deepcopy(plan['source_matrix'])
