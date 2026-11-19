"""Authored orchestration boundaries; never launches the health game schedule."""
from copy import deepcopy
import importlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import threading

import pytest

from scripts.archetype_plan_v3 import build_plan
from scripts.archetype_trace_v3 import digest


def subject():
    name='scripts.archetype_health_v3'
    assert importlib.util.find_spec(name) is not None,'Dedicated health entry is missing'
    return importlib.import_module(name)


def plan(suffix='unit-health'):
    return build_plan('a'*40,f'archetype-health-20261116-v3-{suffix}',kind='health',
                      runtime_sha256=digest({'unit_runtime':True}))


def rows(p):
    return [{'cell_id':c['cell_id'],'status':'resolved','winner':1,'termination':'life',
             'seconds':100.,'cpu_seconds':90.,'trace_bytes':1000,'replay_seconds':20.,
             'parity_checked':True,'run_invalid':False,'cpu_attribution_complete':True,
             'child_handles_reaped':True}for c in p['cells']]



def bytecode_off(monkeypatch):
    """The controller/worker guards require -B; CI invokes pytest without it, so tests that call
    main() in-process model the flag explicitly (subprocess tests pass real flags)."""
    import types
    monkeypatch.setattr(sys,'flags',types.SimpleNamespace(optimize=0,dont_write_bytecode=1))


def test_health_report_is_health_only_and_one_limited_cell_fails_without_losing_accounting():
    m=subject();p=plan();r=rows(p)
    good=m.health_report(r,p)
    assert good['complete'] is True and good['health_passed'] is True
    assert good['accepts_matrix_or_strength'] is False and good['statistical_gate_complete'] is False
    assert all(good[k] is None for k in ('forecast_1440_worker_hours','forecast_72_worker_hours','forecast_trace_bytes'))
    r[1].update(status='timeout',termination='cpu_limit',winner=None,parity_checked=False)
    bad=m.health_report(r,p)
    assert bad['complete'] is True and bad['usable'] is False and bad['health_passed'] is False
    assert bad['statuses']=={'resolved':71,'timeout':1}
    for invalid in (r[:-1],[r[0]]*72):
        if len(invalid)==72:
            with pytest.raises(ValueError):m.health_report(invalid,p)
        else:assert m.health_report(invalid,p)['complete'] is False


@pytest.mark.parametrize('field',['parity_checked','cpu_attribution_complete','child_handles_reaped'])
def test_missing_health_evidence_cannot_pass(field):
    m=subject();p=plan();r=rows(p);r[-1][field]=False
    assert m.health_report(r,p)['health_passed'] is False


def test_health_budget_reserves_next_two_slot_horizon_and_preserves_both_caps():
    m=subject();b=m.HealthBudget(started=100.,prior_charged_seconds=17310.,prior_health_charged_seconds=0.)
    assert b.can_launch(now=101.,unstarted=72,pending_deadlines=[])
    assert b.charged_seconds(200.)==200 and b.remaining_campaign_seconds(200.)==172800-17310-200
    assert b.can_launch(now=52600.,unstarted=1,pending_deadlines=[]) is False
    assert b.exceeded(54100.) is True
    # Previous health attempts consume the same30h allocation, even with a new ID.
    used=m.HealthBudget(started=100.,prior_charged_seconds=120000.,prior_health_charged_seconds=107000.)
    assert used.can_launch(now=100.,unstarted=72,pending_deadlines=[]) is False
    campaign=m.HealthBudget(started=100.,prior_charged_seconds=172000.,prior_health_charged_seconds=0.)
    assert campaign.can_launch(now=100.,unstarted=1,pending_deadlines=[]) is False
    # In-flight deadline must be covered too; never reserve just the next worker's CPU.
    assert not b.can_launch(now=100.,unstarted=1,pending_deadlines=[100000.])


def test_health_controller_runs_exact_72_authored_cells_and_registry_carries_pilot(tmp_path,monkeypatch):
    from test_archetype_pilot_v3 import controller_boundary
    from scripts.archetype_registry_v3 import claim_run
    m=subject();core=controller_boundary(monkeypatch,tmp_path);p=plan()
    with claim_run(core.STATE_ROOT,run_id='archetype-pilot-20261116-v3-old',plan_sha256='a'*64,
                   revision='a'*40,runtime_sha256=digest({'unit_runtime':True}),output=str(tmp_path/'old'))as c:
        c.finish(charged_worker_seconds=17310.,report_sha256=None)
    authored={x['cell_id']:x for x in rows(p)};seen=[];roles=[]
    lock=threading.Lock();barrier=threading.Barrier(2,timeout=5);active=0;peak=0
    def cell(plan,cell,directory,**kw):
        nonlocal active,peak
        with lock:active+=1;peak=max(peak,active);seen.append(cell['cell_id']);roles.append(kw['kind'])
        barrier.wait()
        with lock:active-=1
        return authored[cell['cell_id']]
    monkeypatch.setattr(core,'run_cell',cell)
    report=m.run_health(p,tmp_path/'health')
    assert len(seen)==72 and set(seen)==set(authored) and peak==2 and set(roles)=={'health'}
    assert report['complete'] is True and report['health_passed'] is True
    assert report['charged_campaign_worker_seconds']>=17310 and report['charged_health_worker_seconds']>0
    assert (tmp_path/'health/HEALTH-COMPLETE.json').exists()
    assert not(tmp_path/'health/PILOT-COMPLETE.json').exists()
    ledger=json.loads((core.STATE_ROOT/'active.json').read_text())
    assert ledger['kind']=='health' and ledger['child_handles_reaped'] is True
    with pytest.raises(FileExistsError):m.run_health(p,tmp_path/'other')


@pytest.mark.parametrize('bad',['pilot','unbound','edited_seed','edited_limit','edited_scope'])
def test_health_refuses_role_or_plan_drift_before_source_or_output(tmp_path,monkeypatch,bad):
    from scripts import archetype_pilot_v3 as core
    m=subject();p=plan()
    if bad=='pilot':p=build_plan('a'*40,'archetype-pilot-20261116-v3-wrong',runtime_sha256='b'*64)
    elif bad=='unbound':p['runtime_sha256']=None
    elif bad=='edited_seed':p['seeds'][0]=2026112001
    elif bad=='edited_limit':p['policy']['max_cpu_seconds_per_game']=1201
    else:p['cells'].pop()
    def never(*a,**k):raise AssertionError('Source reached before admission')
    monkeypatch.setattr(core,'source_identity',never)
    with pytest.raises(ValueError):m.run_health(p,tmp_path/'none')
    assert not(tmp_path/'none').exists()


@pytest.mark.parametrize('failure',['budget','postprocessing','unknown_child','divergence'])
def test_health_failures_are_incomplete_or_unhealthy_and_never_accept(tmp_path,monkeypatch,failure):
    from test_archetype_pilot_v3 import controller_boundary
    m=subject();core=controller_boundary(monkeypatch,tmp_path);p=plan();clock=[100.]
    monkeypatch.setattr(core,'boot_time',lambda:clock[0]);monkeypatch.setattr(core,'host_offset',lambda:0.)
    data={r['cell_id']:r for r in rows(p)};seen=[]
    def cell(plan,cell,*args,**kw):
        seen.append(cell['cell_id']);row=deepcopy(data[cell['cell_id']])
        if failure=='unknown_child':
            kw['stop'].set();row.update(child_handles_reaped=False,cpu_seconds=None,run_invalid=True)
        if failure=='divergence':
            kw['stop'].set();row.update(status='replay_divergence',parity_checked=False,winner=None,run_invalid=True)
        return row
    monkeypatch.setattr(core,'run_cell',cell)
    if failure=='budget':monkeypatch.setattr(m.HealthBudget,'can_launch',lambda *a,**k:False)
    if failure=='postprocessing':monkeypatch.setattr(core,'verify_sources',lambda source:clock.__setitem__(0,54101.))
    report=m.run_health(p,tmp_path/'health')
    assert report['health_passed'] is False and report['usable'] is False and report['complete'] is False
    assert report['accepts_matrix_or_strength'] is False
    if failure=='budget':assert seen==[] and report['budget_refused'] is True
    if failure=='postprocessing':assert report['budget_refused'] is True
    ledger=json.loads((core.STATE_ROOT/'active.json').read_text())
    assert ledger['state']==('running' if failure=='unknown_child' else 'closed')
    assert (tmp_path/'health/HEALTH-INCOMPLETE.json').exists()


@pytest.mark.parametrize(('suffix','cpu','wall'),[('unit-health',1200,1500),('rerun1',2400,3000)])
def test_health_real_parent_shares_phase_budgets_and_binds_the_health_worker(tmp_path,monkeypatch,suffix,cpu,wall):
    from test_archetype_pilot_v3 import authored_phase_controller
    subject();core,requests,source=authored_phase_controller(monkeypatch)
    original=core.run_process;commands=[]
    def observed(command,**kwargs):
        commands.append(command);return original(command,**kwargs)
    monkeypatch.setattr(core,'run_process',observed)
    from scripts.archetype_matrix_pilot import file_sha
    source['files']['backend/scripts/archetype_health_worker_v3.py']=file_sha(core.BACKEND/'scripts/archetype_health_worker_v3.py')
    p=plan(suffix)
    row=core.run_cell(p,p['cells'][0],tmp_path/'cell',cpu=min(os.sched_getaffinity(0)),
                      source=source,runtime={'unit_runtime':True},stop=threading.Event(),kind='health')
    assert [q['mode']for q in requests]==['game','verify']
    assert [q['cpu_seconds']for q in requests]==[cpu,cpu-11]
    assert [q['wall_seconds']for q in requests]==[wall,wall-15]
    assert row['status']=='resolved' and row['parity_checked'] is True
    assert all(c[3]=='scripts.archetype_health_worker_v3' for c in commands)


@pytest.mark.parametrize(('suffix','cpu','wall'),[('unit-health',1200,1500),('rerun1',2400,3000)])
def test_health_worker_admission_is_distinct_from_default_pilot_and_checks_both_source_files(tmp_path,monkeypatch,suffix,cpu,wall):
    subject()
    from scripts import archetype_worker_v3 as worker
    from scripts import archetype_health_worker_v3 as health_worker
    from scripts.archetype_matrix_pilot import file_sha
    root=Path(worker.__file__).resolve().parents[2];p=plan(suffix)
    req={'schema':3,'mode':'game','plan':p,'cell':p['cells'][0],'cpu':min(os.sched_getaffinity(0)),
         'cpu_seconds':cpu,'wall_seconds':wall,'memory_bytes':2147483648,'runtime_sha256':p['runtime_sha256'],
         'source':{'root':str(root),'revision':p['revision'],'files':{str(Path(m.__file__).resolve().relative_to(root)):file_sha(m.__file__)for m in (worker,health_worker)}},
         'trace_sha256':None,'accepted_actions':None}
    with pytest.raises(ValueError):worker.validate_request(req)
    worker.validate_request(req,kind='health')
    for limit in ('cpu_seconds', 'wall_seconds'):
        wrong = {**req, limit: req[limit] + 1}
        with pytest.raises(ValueError):
            worker.validate_request(wrong,kind='health')
    class LimitBoundary(BaseException):pass
    def limits(*args):raise LimitBoundary
    monkeypatch.setattr(worker,'apply_limits',limits)
    path=tmp_path/'authored-worker-request.json';path.write_text(json.dumps(req))
    bytecode_off(monkeypatch)
    with pytest.raises(ValueError):worker.main([str(path)])
    with pytest.raises(LimitBoundary):health_worker.main([str(path)])
    wrong=deepcopy(req);wrong['source']['files'].pop('backend/scripts/archetype_health_worker_v3.py')
    with pytest.raises(ValueError):worker.validate_request(wrong,kind='health')
    wrong=deepcopy(req);wrong['cell']['cell_id']='b'*64
    with pytest.raises(ValueError):worker.validate_request(wrong,kind='health')


@pytest.mark.parametrize('flags',[['-O','-B'],['-OO','-B'],[]])
def test_health_cli_runtime_guard_precedes_plan_read(tmp_path,flags):
    subject()
    result=subprocess.run([sys.executable,*flags,'-m','scripts.archetype_health_v3',
        'run',str(tmp_path/'missing'),str(tmp_path/'out'),'--execute-health'],
        cwd=Path(__file__).parents[1],capture_output=True,text=True,timeout=5)
    assert result.returncode!=0 and 'Run v3 health' in result.stderr
    assert 'FileNotFoundError' not in result.stderr and not list(tmp_path.iterdir())


def test_run_only_cli_requires_explicit_flag_and_never_creates_a_plan(tmp_path,monkeypatch):
    m=subject();seen=[];p=tmp_path/'plan.json';p.write_text(json.dumps(plan()))
    def run(value,out):
        seen.append((value,out));return {'complete':True,'health_passed':False,'accounted':72,
                                        'statuses':{'resolved':71,'timeout':1},'accepts_matrix_or_strength':False}
    monkeypatch.setattr(m,'run_health',run)
    bytecode_off(monkeypatch)
    with pytest.raises(SystemExit):m.main(['run',str(p),str(tmp_path/'out')])
    with pytest.raises(SystemExit):m.main(['plan','new-id',str(tmp_path/'new-plan')])
    assert seen==[] and not(tmp_path/'new-plan').exists()
    assert m.main(['run',str(p),str(tmp_path/'out'),'--execute-health'])==1
    assert len(seen)==1 and seen[0][0]==plan() and seen[0][1]==tmp_path/'out'


def test_one_timeout_in_full_authored_schedule_keeps_accounting_complete_and_fails_health(tmp_path,monkeypatch):
    from test_archetype_pilot_v3 import controller_boundary
    m=subject();core=controller_boundary(monkeypatch,tmp_path);p=plan();data={r['cell_id']:r for r in rows(p)}
    data[p['cells'][1]['cell_id']].update(status='timeout',termination='cpu_limit',winner=None,
                                        parity_checked=False,cpu_attribution_complete=False)
    monkeypatch.setattr(core,'run_cell',lambda p,c,*a,**k:data[c['cell_id']])
    report=m.run_health(p,tmp_path/'health')
    assert report['complete'] is True and report['health_passed'] is False and report['usable'] is False
    assert report['statuses']=={'resolved':71,'timeout':1} and report['accounted']==72
    assert (tmp_path/'health/HEALTH-COMPLETE.json').exists()
    assert json.loads((core.STATE_ROOT/'active.json').read_text())['state']=='closed'


def test_health_import_is_definition_only_and_has_no_app_or_ai_side_effects(tmp_path):
    subject()
    code="import json,sys;import scripts.archetype_health_v3,scripts.archetype_health_worker_v3;print(json.dumps({n:n in sys.modules for n in ('main','ai.agent','persistence.db')}))"
    result=subprocess.run([sys.executable,'-B','-c',code],cwd=tmp_path,
                          env={**os.environ,'PYTHONPATH':str(Path(__file__).parents[1])},
                          capture_output=True,text=True,timeout=5)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)=={'main':False,'ai.agent':False,'persistence.db':False}
    assert not list(tmp_path.iterdir())


def test_slow_final_publication_cannot_return_success_past_health_cap(tmp_path,monkeypatch):
    from test_archetype_pilot_v3 import controller_boundary
    m=subject();core=controller_boundary(monkeypatch,tmp_path);p=plan();clock=[100.]
    monkeypatch.setattr(core,'boot_time',lambda:clock[0]);monkeypatch.setattr(core,'host_offset',lambda:0.)
    data={r['cell_id']:r for r in rows(p)}
    monkeypatch.setattr(core,'run_cell',lambda p,c,*a,**k:data[c['cell_id']])
    publish=core.publish
    def slow_publish(path,value):
        publish(path,value)
        if path.name=='HEALTH-COMPLETE.json':clock[0]=54101.
    monkeypatch.setattr(core,'publish',slow_publish)
    with pytest.raises(ValueError,match='budget exceeded during final publication'):
        m.run_health(p,tmp_path/'health')
    ledger=json.loads((core.STATE_ROOT/'active.json').read_text())
    assert ledger['state']=='closed' and ledger['health_budget_exceeded'] is True
    assert ledger['charged_health_worker_seconds']==108002


@pytest.mark.parametrize('flags',[['-O','-B'],['-OO','-B'],[]])
def test_health_worker_runtime_guard_precedes_request_read(tmp_path,flags):
    subject()
    result=subprocess.run([sys.executable,*flags,'-m','scripts.archetype_health_worker_v3',str(tmp_path/'missing')],
        cwd=Path(__file__).parents[1],capture_output=True,text=True,timeout=5)
    assert result.returncode!=0 and 'Run v3 health worker' in result.stderr
    assert 'FileNotFoundError' not in result.stderr and not list(tmp_path.iterdir())


def test_rerun_budget_checks_both_slots_at_the_increased_horizon():
    b = subject().HealthBudget(started=0., prior_charged_seconds=39799.,
                               prior_health_charged_seconds=22489., wall_seconds=3000)
    assert b.remaining_seconds(0.) == 85511.
    assert b.can_launch(now=0., unstarted=72, pending_deadlines=[])
    edge = (85511.-6060.)/2
    assert b.can_launch(now=edge, unstarted=1, pending_deadlines=[])
    assert not b.can_launch(now=edge+.5, unstarted=1, pending_deadlines=[])
