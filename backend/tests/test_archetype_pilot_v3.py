"""Owned stdlib children and authored phase receipts, never measured games."""
import importlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import sys
import threading
from types import SimpleNamespace

import pytest


def subject():
    name='scripts.archetype_pilot_v3'
    assert importlib.util.find_spec(name) is not None,'V3 pilot controller is missing'
    return importlib.import_module(name)


def plan():
    from scripts.archetype_plan_v3 import build_plan
    from scripts.archetype_trace_v3 import digest
    return build_plan('a'*40,'archetype-pilot-20261116-v3-unit-parent',runtime_sha256=digest({'unit_runtime':True}))


def test_wait4_collects_actual_owned_child_cpu_even_on_timeout(tmp_path):
    module=subject()
    good=module.run_process([sys.executable,'-c','sum(range(1000000))'],directory=tmp_path,
        name='good',environment=os.environ.copy(),seconds=3,stop=threading.Event())
    assert good['returncode']==0 and good['waited'] is True
    assert good['cpu_seconds']>0 and good['peak_rss_bytes']>0
    limited=module.run_process([sys.executable,'-c','while True: pass'],directory=tmp_path,
        name='limited',environment=os.environ.copy(),seconds=.08,stop=threading.Event())
    assert limited['termination']=='wall_limit' and limited['waited'] is True
    assert limited['cpu_seconds']>0 and limited['returncode']<0


def test_cancellation_never_launches_another_child(tmp_path):
    module=subject();stop=threading.Event();stop.set()
    result=module.run_process([sys.executable,'-c','raise RuntimeError()'],directory=tmp_path,
        name='never',environment=os.environ.copy(),seconds=1,stop=stop)
    assert result['started'] is False and result['waited'] is False
    assert result['cpu_seconds']==0 and not list(tmp_path.iterdir())


def authored_phase_controller(monkeypatch,*,bad=None,game_cpu=10.6,verify_cpu=20.25):
    """Only the child/source/runtime boundary is authored; real parent is tested."""
    module=subject()
    from scripts.archetype_matrix_pilot import publish,file_sha
    from scripts.archetype_trace_v3 import digest
    from scripts.archetype_worker_v3 import ProgressRecorder,request_identity
    clock=[100.0];requests=[]
    monkeypatch.setattr(module,'boot_time',lambda:clock[0])
    monkeypatch.setattr(module,'host_offset',lambda:0.)
    monkeypatch.setattr(module,'verify_sources',lambda source:None)
    monkeypatch.setattr(module,'runtime_identity',lambda:{'unit_runtime':True})
    def child(command,*,directory,name,environment,seconds,stop):
        req=json.loads(Path(command[-1]).read_text());requests.append(req)
        actual=game_cpu if name=='game' else verify_cpu
        identity=request_identity(req);trace=directory/'trace.jsonl'
        truth={'status':'resolved','winner':1,'termination':'life','accepted_actions':1,'turn':3}
        if name=='game':
            from scripts.archetype_trace_v3 import TraceWriter
            with trace.open('wb')as stream:
                writer=TraceWriter(stream)
                writer.emit({'kind':'initial','identity':identity})
                writer.emit({'kind':'action','step':0})
                writer.emit({'kind':'final','outcome':truth})
        clock[0]+=max(15,actual+1)
        if bad=='crash' and name=='verify':
            return {'started':True,'waited':True,'returncode':-signal.SIGSEGV,
                    'termination':None,'cpu_seconds':actual,'peak_rss_bytes':1024}
        partial=bad in ('cpu_kill','cpu_kill_count') and name=='game'
        reported=actual-1 if partial else actual-.01
        usage={'category_seconds':{'setup':.5},'category_calls':{'setup':1},
               'process_cpu_seconds':reported,'unattributed_cpu_seconds':reported-.5}
        ProgressRecorder(directory,name,identity,SimpleNamespace(snapshot=lambda:usage)).update(
            2,json.loads(trace.read_bytes().splitlines()[-1])['record_sha256'],trace.stat().st_size,
            2 if bad=='cpu_kill_count'else 1,force=True)
        if name=='verify'and bad in ('progress_hash','progress_bytes'):
            path=directory/f'{name}-progress.json';receipt=json.loads(path.read_text())
            if bad=='progress_hash':receipt['last_record_sha256']='0'*64
            else:receipt['trace_bytes']-=1
            path.write_text(json.dumps(receipt))
        result={'schema':3,'mode':name,'cell_id':req['cell']['cell_id'],'identity':identity,
                'controls':{'affinity':[req['cpu']],'memory_bytes':req['memory_bytes'],
                            'cpu_soft_seconds':req['cpu_seconds']},
                'cpu_seconds':reported,'cpu_usage':usage,'peak_rss_bytes':1024,'seconds':actual}
        if name=='game':
            result.update(outcome=dict(truth),trace_sha256=file_sha(trace))
            if bad=='winner':result['outcome']['winner']=2
        else:
            result.update(replay={'matched':True,'actions':1,'status':'resolved','restart_roundtrips':1,'outcome':truth},
                handler_boundaries=[{'step':0}],handler_checks_performed=True,replay_seconds=1.)
        rc=0
        if bad=='diverge' and name=='verify':rc=1;result['error']='replay_divergence'
        if bad=='bool_cpu':result['cpu_seconds']=True
        if not partial and not(bad=='missing_result' and name=='verify'):
            publish(directory/f'{name}-result.json',result)
        return {'started':True,'waited':True,'returncode':-signal.SIGXCPU if partial else rc,
                'termination':None,'cpu_seconds':actual,'peak_rss_bytes':1024}
    monkeypatch.setattr(module,'run_process',child)
    source={'root':str(module.BACKEND.parent),'revision':'a'*40,
            'files':{'backend/scripts/archetype_worker_v3.py':file_sha(module.BACKEND/'scripts/archetype_worker_v3.py')}}
    return module,requests,source


def test_cell_shares_actual_cpu_and_wall_across_both_phases(tmp_path,monkeypatch):
    module,requests,source=authored_phase_controller(monkeypatch)
    p=plan();stop=threading.Event()
    row=module.run_cell(p,p['cells'][0],tmp_path/'cell',cpu=min(os.sched_getaffinity(0)),
        source=source,runtime={'unit_runtime':True},stop=stop)
    assert [r['mode']for r in requests]==['game','verify']
    assert requests[0]['cpu_seconds']==1200 and requests[1]['cpu_seconds']==1189
    assert requests[0]['wall_seconds']==1500 and requests[1]['wall_seconds']==1485
    assert row['status']=='resolved' and row['winner']==1 and row['parity_checked'] is True
    assert row['cpu_seconds']==pytest.approx(30.85) and row['cpu_attribution_complete'] is True
    assert not stop.is_set()


@pytest.mark.parametrize('bad',['diverge','crash','missing_result','bool_cpu','winner','progress_hash','progress_bytes'])
def test_failed_or_unbound_verifier_never_preserves_a_game_win(tmp_path,monkeypatch,bad):
    module,requests,source=authored_phase_controller(monkeypatch,bad=bad)
    p=plan();row=module.run_cell(p,p['cells'][0],tmp_path/'cell',cpu=min(os.sched_getaffinity(0)),
        source=source,runtime={'unit_runtime':True},stop=threading.Event())
    assert row['status']!='resolved' and row['winner'] is None and row['parity_checked'] is False


def test_actual_combined_cpu_overrun_is_not_hidden_by_smaller_worker_receipts(tmp_path,monkeypatch):
    module,requests,source=authored_phase_controller(monkeypatch,game_cpu=1199,verify_cpu=1.1)
    p=plan();row=module.run_cell(p,p['cells'][0],tmp_path/'cell',cpu=min(os.sched_getaffinity(0)),
        source=source,runtime={'unit_runtime':True},stop=threading.Event())
    assert requests[1]['cpu_seconds']==1
    assert row['status']=='timeout' and row['termination']=='cpu_limit' and row['winner'] is None
    assert row['cpu_seconds']==pytest.approx(1200.1)


def test_killed_worker_keeps_actual_total_and_partial_attribution_without_credit(tmp_path,monkeypatch):
    module,requests,source=authored_phase_controller(monkeypatch,bad='cpu_kill',game_cpu=5.4)
    p=plan();row=module.run_cell(p,p['cells'][0],tmp_path/'cell',cpu=min(os.sched_getaffinity(0)),
        source=source,runtime={'unit_runtime':True},stop=threading.Event())
    assert len(requests)==1 and row['cpu_seconds']==pytest.approx(5.4)
    assert row['cpu_attribution_complete'] is False and row['accepted_actions_partial']==1
    assert row['accepted_actions'] is None and row['winner'] is None and row['parity_checked'] is False


def test_killed_worker_progress_cannot_claim_more_actions_than_its_trace_prefix(tmp_path,monkeypatch):
    module,requests,source=authored_phase_controller(monkeypatch,bad='cpu_kill_count',game_cpu=5.4)
    p=plan();row=module.run_cell(p,p['cells'][0],tmp_path/'cell',cpu=min(os.sched_getaffinity(0)),
        source=source,runtime={'unit_runtime':True},stop=threading.Event())
    assert row['cpu_seconds']==pytest.approx(5.4) and row['accepted_actions_partial'] is None


def report_rows(p):
    return [{'cell_id':cell['cell_id'],'status':'resolved','winner':1,'termination':'life',
             'seconds':100.,'cpu_seconds':90.,'peak_rss_bytes':100,'trace_bytes':1000,
             'replay_seconds':20.,'parity_checked':True,'run_invalid':False,
             'cpu_attribution_complete':True,'child_handles_reaped':True}for cell in p['cells']]


def test_only_completed_games_with_verification_can_produce_a_forecast():
    module=subject();p=plan();rows=report_rows(p)
    report=module.pilot_report(rows,p)
    assert report['complete'] is True and report['usable'] is True
    assert report['forecast_1440_worker_hours']==40
    assert report['accepts_matrix_or_strength'] is False
    rows[0].update(status='timeout',winner=None,parity_checked=False)
    report=module.pilot_report(rows,p)
    assert report['complete'] is True and report['usable'] is False
    assert report['forecast_1440_worker_hours'] is None and report['forecast_trace_bytes'] is None
    with pytest.raises(ValueError):module.pilot_report([rows[0]]*36,p)


def test_slot_budget_reserves_unstarted_cells_and_health_cohort():
    module=subject();budget=module.SlotBudget(started=100.)
    assert budget.can_launch(now=100.,unstarted=36,pending_deadlines=[])
    assert not budget.can_launch(now=5600.,unstarted=36,pending_deadlines=[])
    assert budget.charged_seconds(200.)==200
    assert budget.remaining_campaign_seconds(200.)==48*3600-200
    assert budget.reserved_health_seconds==30*3600


def test_health_plan_cannot_be_launched_even_if_all_its_metadata_is_valid(tmp_path):
    module=subject()
    from scripts.archetype_plan_v3 import build_plan
    p=build_plan('a'*40,'archetype-health-20261116-v3-unit',kind='health')
    with pytest.raises(ValueError):module.run_pilot(p,tmp_path/'must-not-exist')
    assert not(tmp_path/'must-not-exist').exists()


def controller_boundary(monkeypatch,tmp_path):
    module=subject()
    monkeypatch.setattr(module,'source_identity',lambda revision:{'revision':revision,'authored_source_boundary':True})
    monkeypatch.setattr(module,'verify_sources',lambda source:None)
    monkeypatch.setattr(module,'runtime_identity',lambda:{'unit_runtime':True})
    monkeypatch.setattr(module.os,'sched_getaffinity',lambda pid:{0,1,2})
    monkeypatch.setattr(module,'available_memory',lambda:10*1024**3)
    monkeypatch.setattr(module,'STATE_ROOT',tmp_path/'controller-state',raising=False)
    return module


def test_controller_accounts_exact_36_authored_cells_with_two_slots_and_no_resume(tmp_path,monkeypatch):
    module=controller_boundary(monkeypatch,tmp_path)
    assert callable(getattr(module,'run_pilot',None)),'V3 pilot orchestration is missing'
    p=plan();lock=threading.Lock();barrier=threading.Barrier(2,timeout=5)
    seen=[];active=0;peak=0
    by_id={row['cell_id']:row for row in report_rows(p)}
    def authored(plan,cell,directory,**kwargs):
        nonlocal active,peak
        with lock:active+=1;peak=max(peak,active);seen.append(cell['cell_id'])
        barrier.wait()
        with lock:active-=1
        return by_id[cell['cell_id']]
    monkeypatch.setattr(module,'run_cell',authored)
    report=module.run_pilot(p,tmp_path/'pilot')
    assert peak==2 and len(seen)==36 and set(seen)==set(by_id)
    assert report['complete'] is True and report['usable'] is True
    assert report['reserved_health_worker_seconds']==30*3600
    assert report['remaining_campaign_worker_seconds']<=48*3600
    assert (tmp_path/'pilot/PILOT-COMPLETE.json').exists()
    with pytest.raises(FileExistsError):module.run_pilot(p,tmp_path/'pilot')


def test_campaign_budget_refusal_does_not_start_a_partial_schedule(tmp_path,monkeypatch):
    module=controller_boundary(monkeypatch,tmp_path)
    assert callable(getattr(module,'run_pilot',None)),'V3 pilot orchestration is missing'
    monkeypatch.setattr(module.SlotBudget,'can_launch',lambda *a,**k:False)
    seen=[];monkeypatch.setattr(module,'run_cell',lambda *a,**k:seen.append(True))
    report=module.run_pilot(plan(),tmp_path/'pilot')
    assert seen==[] and report['complete'] is False and report['usable'] is False
    assert report['forecast_1440_worker_hours'] is None
    assert (tmp_path/'pilot/PILOT-INCOMPLETE.json').exists()


def test_unbound_runtime_preview_is_refused_before_source_admission_or_writes(tmp_path,monkeypatch):
    module=subject()
    assert callable(getattr(module,'run_pilot',None)),'V3 pilot orchestration is missing'
    from scripts.archetype_plan_v3 import build_plan
    p=build_plan('a'*40,'archetype-pilot-20261116-v3-preview')
    def wrong(revision):raise AssertionError('source admission must not run for an unissued preview')
    monkeypatch.setattr(module,'source_identity',wrong)
    with pytest.raises(ValueError):module.run_pilot(p,tmp_path/'must-not-exist')
    assert not(tmp_path/'must-not-exist').exists()


def test_controller_exception_does_not_fabricate_zero_actual_child_cpu(tmp_path,monkeypatch):
    module,requests,source=authored_phase_controller(monkeypatch)
    def failed(*args,**kwargs):raise OSError('authored observer failure')
    monkeypatch.setattr(module,'run_process',failed)
    p=plan();row=module.run_cell(p,p['cells'][0],tmp_path/'cell',cpu=min(os.sched_getaffinity(0)),
        source=source,runtime={'unit_runtime':True},stop=threading.Event())
    assert row['run_invalid'] is True and row['winner'] is None
    assert row['cpu_seconds'] is None and row['cpu_attribution_complete'] is False


@pytest.mark.parametrize('status',['timeout','tick_limit','turn_limit','error','replay_divergence'])
def test_accounted_but_unhealthy_cells_never_generate_completed_game_forecasts(status):
    module=subject();p=plan();rows=report_rows(p)
    for row in rows:row.update(status=status,winner=None,parity_checked=False)
    report=module.pilot_report(rows,p)
    assert report['complete'] is True and report['usable'] is False
    assert report['forecast_1440_worker_hours'] is None and report['forecast_trace_bytes'] is None


def test_cli_refuses_optimization_before_reading_plan(tmp_path):
    import subprocess
    subject()
    code='''import sys
from scripts.archetype_pilot_v3 import main
raise SystemExit(main(['run',sys.argv[1],sys.argv[2],'--execute-pilot']))
'''
    result=subprocess.run([sys.executable,'-O','-B','-c',code,str(tmp_path/'missing.json'),str(tmp_path/'out')],
        cwd=Path(__file__).parents[1],capture_output=True,text=True,timeout=5)
    assert result.returncode!=0 and 'Run v3 pilot' in result.stderr
    assert 'FileNotFoundError' not in result.stderr and not(tmp_path/'out').exists()


def test_postprocessing_budget_overrun_cannot_keep_a_usable_report(tmp_path,monkeypatch):
    module=controller_boundary(monkeypatch,tmp_path);clock=[100.]
    monkeypatch.setattr(module,'boot_time',lambda:clock[0]);monkeypatch.setattr(module,'host_offset',lambda:0.)
    p=plan();rows={r['cell_id']:r for r in report_rows(p)}
    monkeypatch.setattr(module,'run_cell',lambda plan,cell,*args,**kwargs:rows[cell['cell_id']])
    def slow_postprocessing(source):clock[0]=32501.
    monkeypatch.setattr(module,'verify_sources',slow_postprocessing)
    report=module.run_pilot(p,tmp_path/'pilot')
    assert report['budget_refused'] is True and report['complete'] is False and report['usable'] is False
    assert report['forecast_1440_worker_hours'] is None


def test_same_issued_plan_cannot_reset_campaign_by_using_a_new_output(tmp_path,monkeypatch):
    module=controller_boundary(monkeypatch,tmp_path)
    p=plan();rows={r['cell_id']:r for r in report_rows(p)};seen=[]
    def authored(plan,cell,*args,**kwargs):
        seen.append(cell['cell_id']);return rows[cell['cell_id']]
    monkeypatch.setattr(module,'run_cell',authored)
    assert module.run_pilot(p,tmp_path/'first')['complete'] is True
    with pytest.raises(FileExistsError):module.run_pilot(p,tmp_path/'different-output')
    assert len(seen)==36


def test_second_phase_observer_exception_keeps_total_cpu_and_closure_unproven(tmp_path,monkeypatch):
    module,requests,source=authored_phase_controller(monkeypatch)
    child=module.run_process
    def failed(command,**kwargs):
        if kwargs['name']=='verify':raise OSError('authored second phase observer failure')
        return child(command,**kwargs)
    monkeypatch.setattr(module,'run_process',failed)
    p=plan();row=module.run_cell(p,p['cells'][0],tmp_path/'cell',cpu=min(os.sched_getaffinity(0)),
        source=source,runtime={'unit_runtime':True},stop=threading.Event())
    assert row['run_invalid']is True and row['winner']is None
    assert row['cpu_seconds']is None and row['cpu_attribution_complete']is False
    assert [s['mode']for s in row['stages']]==['game','verify']
    assert row['stages'][-1]['waited']is False


def test_prior_campaign_charges_reduce_new_id_admission_and_remaining_budget():
    module=subject();budget=module.SlotBudget(started=100.)
    budget.prior_charged_seconds=4*3600
    assert not budget.can_launch(now=100.,unstarted=36,pending_deadlines=[])
    assert budget.remaining_campaign_seconds(100.)==44*3600


def test_new_run_id_cannot_discard_charges_carried_from_a_previous_pilot(tmp_path,monkeypatch):
    module=controller_boundary(monkeypatch,tmp_path)
    from scripts.archetype_registry_v3 import claim_run
    from scripts.archetype_trace_v3 import digest
    with claim_run(module.STATE_ROOT,run_id='archetype-pilot-20261116-v3-previous',plan_sha256='a'*64,
                   revision='a'*40,runtime_sha256=digest({'unit_runtime':True}),output=str(tmp_path/'previous'))as claim:
        claim.finish(charged_worker_seconds=4*3600,report_sha256=None)
    seen=[];monkeypatch.setattr(module,'run_cell',lambda *a,**k:seen.append(True))
    report=module.run_pilot(plan(),tmp_path/'next')
    assert seen==[] and report['budget_refused']is True and report['complete']is False
    assert report['charged_campaign_worker_seconds']>=4*3600
    assert report['remaining_campaign_worker_seconds']<=44*3600


def test_unproven_cell_attempt_does_not_close_the_registry(tmp_path,monkeypatch):
    module=controller_boundary(monkeypatch,tmp_path)
    p=plan();rows={r['cell_id']:r for r in report_rows(p)}
    def unknown(plan,cell,*args,**kwargs):
        kwargs['stop'].set()
        return {**rows[cell['cell_id']],'run_invalid':True,'cpu_seconds':None,
                'child_handles_reaped':False,'cpu_attribution_complete':False}
    monkeypatch.setattr(module,'run_cell',unknown)
    report=module.run_pilot(p,tmp_path/'unknown')
    assert report['complete']is False and report['usable']is False
    assert json.loads((module.STATE_ROOT/'active.json').read_text())['state']=='running'
