"""Fresh frozen schedules/budgets only; does not execute either cohort."""
from copy import deepcopy
import importlib
import importlib.util
from itertools import combinations

import pytest


def subject():
    name='scripts.archetype_plan_v3'
    assert importlib.util.find_spec(name) is not None,'V3 plan admission is missing'
    return importlib.import_module(name)


def plan(kind='pilot'):
    return subject().build_plan('a'*40, f'archetype-{kind}-20261116-v3-unit',kind=kind)


def test_pilot_has_exact_fresh_36_cells_and_combined_budgets():
    module=subject();p=plan();module.validate_plan(p)
    assert len(p['cells'])==36 and len({x['cell_id']for x in p['cells']})==36
    assert p['seeds']==[2026112001,2026112002]
    assert p['policy']['max_cpu_seconds_per_game']==1200 and p['policy']['max_seconds']==1500
    assert p['policy']['difficulty']=='master' and p['policy']['workers']==2
    assert p['trace_policy']['checkpoint_interval']==64
    assert p['trace_policy']['max_bytes']==128*1024**2
    assert p['accepts_matrix_or_strength'] is False and p['statistical_gate_complete'] is False
    assert p['worker_hour_budget']=={'campaign':48,'pilot_cells':15,'health_cells':30,'overhead':3}
    assert module.execution_matrix(p)['decks']==p['source_matrix']['decks']


def test_health_plan_keeps_all_pairs_both_seats_and_one_seed_scope_explicit():
    p=plan('health');subject().validate_plan(p)
    names=sorted(p['source_matrix']['decks']);pairs=set(combinations(names,2))
    assert len(p['cells'])==72 and {(x['deck_a'],x['deck_b'])for x in p['cells']}==pairs
    assert p['seeds']==[2026112101] and p['batch_execution_authorized'] is False
    assert p['policy']['health_gate']['max_resource_limit_cells']==0
    assert p['seed_cluster_interval']=='unavailable_one_independent_seed'
    for a,b in pairs:
        assert {x['deck_a_seat']for x in p['cells']if(x['deck_a'],x['deck_b'])==(a,b)}=={1,2}
    for deck in names:
        seats=[x['deck_a_seat']if x['deck_a']==deck else 3-x['deck_a_seat']
               for x in p['cells']if deck in(x['deck_a'],x['deck_b'])]
        assert seats.count(1)==seats.count(2)==8


@pytest.mark.parametrize('field',['cpu','wall','memory','checkpoint','seed','cell','master','gate','extra'])
def test_admission_refuses_edited_budget_schedule_or_scope(field):
    p=deepcopy(plan())
    if field=='cpu':p['policy']['max_cpu_seconds_per_game']=1201
    elif field=='wall':p['policy']['max_seconds']=True
    elif field=='memory':p['policy']['max_memory_bytes_per_worker']=2147483649
    elif field=='checkpoint':p['trace_policy']['checkpoint_interval']=65
    elif field=='seed':p['seeds'][0]=2026111901
    elif field=='cell':p['cells'].pop()
    elif field=='master':p['policy']['difficulty']='easy'
    elif field=='gate':p['accepts_matrix_or_strength']=True
    else:p['unreviewed']=True
    with pytest.raises(ValueError):subject().validate_plan(p)


def test_old_pilot_full_matrix_and_null_revision_draft_do_not_gain_execution_rights():
    module=subject()
    for bad in ({'schema':3,'revision':None}, {'kind':'pilot','run_id':'archetype-pilot-20261116-v2-unit'},
                {'kind':'matrix','run_id':'archetype-admitted-20261116-v2'}):
        with pytest.raises(ValueError):module.validate_plan(bad)
    for revision in ('main',None,'a'*39):
        with pytest.raises(ValueError):module.build_plan(revision,'archetype-pilot-20261116-v3-unit')


def test_new_run_id_changes_all_cell_identities_and_outputs_are_fresh():
    p=plan();q=subject().build_plan('a'*40,'archetype-pilot-20261116-v3-next')
    assert not({x['cell_id']for x in p['cells']}&{x['cell_id']for x in q['cells']})
    p['policy']['health_gate']['crashes']=99
    assert q['policy']['health_gate']['crashes']==0
    assert not(set(q['seeds'])&{2026111901,2026111902,*range(2026111801,2026111821)})


def test_issued_plan_can_freeze_runtime_while_unbound_preview_is_not_an_execution_admission():
    preview=plan()
    assert 'runtime_sha256' in preview,'V3 plan does not bind its issued runtime'
    assert preview['runtime_sha256'] is None
    issued=subject().build_plan('a'*40,'archetype-pilot-20261116-v3-issued',runtime_sha256='b'*64)
    assert issued['runtime_sha256']=='b'*64
    subject().validate_plan(issued)
    with pytest.raises(ValueError):subject().build_plan('a'*40,'archetype-pilot-20261116-v3-issued',runtime_sha256='bad')


def test_order_fidelity_policy_bumps_trace_format_and_refuses_old_plan_contract():
    p = plan()
    assert p['trace_policy']['schema'] == 4
    assert p['trace_policy']['chain_hash'] == 'sha256_domain_mtg-archetype-v4-record'
    assert p['trace_policy']['cards_order'] == 'explicit_initial_checkpoint_final_lists_and_per_action_digests'
    p['trace_policy']['schema'] = 3
    p['trace_policy']['chain_hash'] = 'sha256_domain_mtg-archetype-v3-record'
    p['trace_policy'].pop('cards_order')
    with pytest.raises(ValueError): subject().validate_plan(p)


def test_trace2_quota_proposal_is_128MiB_without_relaxing_checkpoints_or_time_budgets():
    from scripts.archetype_trace_v3 import MAX_TRACE_BYTES, TraceWriter
    import io
    p = plan()
    assert MAX_TRACE_BYTES == 128*1024**2
    assert p['trace_policy']['max_bytes'] == MAX_TRACE_BYTES
    assert TraceWriter(io.BytesIO()).max_bytes == MAX_TRACE_BYTES
    assert p['trace_policy']['checkpoint_interval'] == 64
    assert p['trace_policy']['extra_checkpoints'] == ['handler_first_every100_last','choice_change','pregame_completion','final']
    assert p['policy']['max_cpu_seconds_per_game'] == 1200
    assert p['policy']['max_seconds'] == 1500 and p['worker_hour_budget']['campaign'] == 48
    p['trace_policy']['max_bytes'] = 64*1024**2
    with pytest.raises(ValueError): subject().validate_plan(p)
    with pytest.raises(ValueError): TraceWriter(io.BytesIO(), max_bytes=MAX_TRACE_BYTES+1)


def test_rerun1_changes_only_limits_and_run_identity():
    module = subject()
    original = plan('health')
    rerun = module.build_plan('a'*40, 'archetype-health-20261116-v3-rerun1', kind='health')
    module.validate_plan(rerun)
    assert rerun['policy']['max_seconds'] == 3000
    assert rerun['policy']['max_cpu_seconds_per_game'] == 2400
    assert {c['cell_id'] for c in rerun['cells']}.isdisjoint(c['cell_id'] for c in original['cells'])
    for field in ('max_seconds', 'max_cpu_seconds_per_game'):
        incorrect = deepcopy(rerun)
        incorrect['policy'][field] = original['policy'][field]
        with pytest.raises(ValueError):
            module.validate_plan(incorrect)
    rerun['policy'] = original['policy']
    for p in (original, rerun):
        del p['run_id']
        for cell in p['cells']:
            del cell['cell_id']
    assert rerun == original
