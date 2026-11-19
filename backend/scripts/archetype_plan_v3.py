"""Fresh v3 pre-registration; health-plan creation never authorizes its run."""
from copy import deepcopy
from itertools import combinations
from pathlib import Path
import re

from scripts.archetype_matrix_plan import build_plan as build_source_matrix
from scripts.archetype_trace_v3 import CHECKPOINT_INTERVAL, MAX_TRACE_BYTES, TRACE_SCHEMA, digest, is_sha

STANDARD_CPU_SECONDS = 1200
STANDARD_WALL_SECONDS = 1500
MAX_CPU_SECONDS = 2400
MAX_WALL_SECONDS = 3000
HEALTH_RERUN_ID = 'archetype-health-20261116-v3-rerun1'
MEMORY_BYTES = 2147483648
PILOT_SEEDS = (2026112001, 2026112002)
HEALTH_SEEDS = (2026112101,)
LEGACY_CAMPAIGN_HOURS = 48
STRENGTH_CAMPAIGN_HOURS = 120
STRENGTH_CAMPAIGN_ID = 'mtg-archetype-strength-20261122'
STRENGTH_RUN_ID = 'archetype-strength-20261122-v3-main1'
STRENGTH_SEEDS = tuple(range(2026112201, 2026112210))
STRENGTH_OPPONENTS = ('random', 'casual', 'strong', 'master')
STRENGTH_CHECKPOINT_INTERVAL = 256
STRENGTH_TRACE_BYTES = 23 * 1024**2
STRENGTH_BOOTSTRAP_REPLICATES = 2000
STRENGTH_BOOTSTRAP_SEED = 271828


def valid_run_id(kind, run_id):
    if type(kind) is not str or type(run_id) is not str:
        return False
    if kind == 'strength':
        return run_id == STRENGTH_RUN_ID
    return kind in ('pilot', 'health') and re.fullmatch(
        f'archetype-{kind}-20261116-v3-[A-Za-z0-9-]{{1,48}}', run_id) is not None


def build_plan(revision, run_id, *, kind='pilot', builtin_source=None, runtime_sha256=None):
    if not valid_run_id(kind, run_id):
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
    strength = kind == 'strength'
    opponents = STRENGTH_OPPONENTS if strength else (None,)
    if strength:
        pairs = [(name, name) for name in names]
        seeds = STRENGTH_SEEDS
    cells = []
    # Interleave baselines within each mirrored seed pair to avoid censoring
    # every observation for a baseline when budget or a host failure stops a run.
    for a,b in pairs:
        for seed in seeds:
            for opponent in opponents:
                for seat in (1,2):
                    fields = {'deck_a':a,'deck_b':b,'seed':seed,'deck_a_seat':seat}
                    if strength:
                        fields['opponent'] = opponent
                    cells.append({'cell_id':digest({'run_id':run_id,'kind':kind,**fields}),**fields})
    policy = deepcopy(matrix['policy'])
    rerun = strength or (kind == 'health' and run_id == HEALTH_RERUN_ID)
    policy.update(max_seconds=MAX_WALL_SECONDS if rerun else STANDARD_WALL_SECONDS,
                  max_cpu_seconds_per_game=MAX_CPU_SECONDS if rerun else STANDARD_CPU_SECONDS)
    policy['health_gate']['max_resource_limit_cells'] = 0
    trace = {'schema':TRACE_SCHEMA,'checkpoint_interval':CHECKPOINT_INTERVAL,'max_bytes':MAX_TRACE_BYTES,
             'progress_interval':16,'state_hash':'sha256_canonical_complete_snapshot',
             'chain_hash':'sha256_domain_mtg-archetype-v4-record',
             'cards_order':'explicit_initial_checkpoint_final_lists_and_per_action_digests',
             'extra_checkpoints':['handler_first_every100_last','choice_change','pregame_completion','final'],
             'sequential_replay_every_action':True,'serde_every_action':True,
             'ai_mutation_check':True,'quota_overflow':'trace_limit_incomplete_no_truncation'}
    if strength:
        del policy['health_gate']
        policy['random_baseline'] = 'uniform_unique_checked_offer_completions_v1'
        policy['snapshot_checkpoint_interval'] = STRENGTH_CHECKPOINT_INTERVAL
        policy['bootstrap_replicates'] = STRENGTH_BOOTSTRAP_REPLICATES
        policy['bootstrap_seed'] = STRENGTH_BOOTSTRAP_SEED
        trace.update(checkpoint_interval=STRENGTH_CHECKPOINT_INTERVAL,
                     max_bytes=STRENGTH_TRACE_BYTES, extra_checkpoints=['final'])
    plan = {'schema':3,'kind':kind,'run_id':run_id,'revision':revision,'runtime_sha256':runtime_sha256,
            'source_matrix_sha256':digest(matrix),'source_matrix':matrix,
            'seeds':list(seeds),'cells':cells,'policy':policy,'trace_policy':trace,
            'worker_hour_budget':{'campaign':LEGACY_CAMPAIGN_HOURS,'pilot_cells':15,'health_cells':30,'overhead':3},
            'batch_execution_authorized':False,'accepts_matrix_or_strength':False,
            'statistical_gate_complete':False,
            'scope':'adjacent_pairs_two_seeds_both_seats' if kind=='pilot' else 'all36_pairs_one_seed_both_seats_health_only',
            'seed_cluster_interval':'not_matrix_acceptance' if kind=='pilot' else 'unavailable_one_independent_seed'}
    if strength:
        plan.update(campaign_id=STRENGTH_CAMPAIGN_ID,
                    scope='same_deck_candidate_master_mirrored_seats',
                    seed_cluster_interval='seed_clusters_across_decks_keep_mirrors_intact',
                    strength_gate={'random':{'score_lower':0.80,'ci_lower_strict':0.65},
                                   'casual':{'score_lower':0.80,'ci_lower_strict':0.65},
                                   'strong':{'ci_lower_strict':0.50},
                                   'master':{'ci_contains':0.50,'complete_symmetric_mirrors':True}})
        plan['worker_hour_budget']['campaign'] = STRENGTH_CAMPAIGN_HOURS
    return plan


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
