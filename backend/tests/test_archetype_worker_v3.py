"""Worker limits and partial progress; no pilot/game cohort is launched."""
import importlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


def subject():
    name='scripts.archetype_worker_v3'
    assert importlib.util.find_spec(name) is not None,'V3 worker/progress is missing'
    return importlib.import_module(name)


def test_raised_limits_validate_exact_types_before_any_process_changes():
    module=subject();cpus=sorted(os.sched_getaffinity(0));cpu=cpus[0]
    module.validate_limits(cpu,1200,2147483648)
    for c,s,m in ((True,1200,2147483648),(max(cpus)+1,1200,2147483648),
                  (cpu,True,2147483648),(cpu,1201,2147483648),(cpu,0,2147483648),
                  (cpu,1200,True)):
        with pytest.raises(ValueError):module.validate_limits(c,s,m)
    assert sorted(os.sched_getaffinity(0))==cpus


def test_real_raised_limit_in_fresh_process_without_launching_a_game():
    subject();cpu=min(os.sched_getaffinity(0))
    code='''import json,resource,sys
from scripts.archetype_worker_v3 import apply_limits
x=apply_limits(int(sys.argv[1]),1200,2147483648)
x['hard']=resource.getrlimit(resource.RLIMIT_CPU)[1]
print(json.dumps(x))
'''
    result=subprocess.run([sys.executable,'-B','-c',code,str(cpu)],
        cwd=Path(__file__).parents[1],text=True,capture_output=True,timeout=5)
    assert result.returncode==0,result.stderr
    record=json.loads(result.stdout)
    assert record=={'affinity':[cpu],'memory_bytes':2147483648,'cpu_soft_seconds':1200,'hard':1201}


def test_atomic_progress_binds_last_complete_trace_record_and_actual_cpu(tmp_path):
    from scripts.archetype_trace_v3 import CpuAccounting, TraceWriter
    module=subject();accounting=CpuAccounting();identity={'cell_id':'a'*64,'plan_sha256':'b'*64}
    recorder=module.ProgressRecorder(tmp_path,'game',identity,accounting)
    stream=io.BytesIO();writer=TraceWriter(stream)
    writer.emit({'kind':'initial'})
    recorder.update(writer.sequence-1,writer.last_digest,writer.total_bytes,0,force=True)
    first=(tmp_path/'game-progress.json').read_bytes()
    for i in range(16):writer.emit({'kind':'action','step':i})
    recorder.update(writer.sequence-1,writer.last_digest,writer.total_bytes,16,force=True)
    receipt=module.read_progress(tmp_path/'game-progress.json',identity,'game')
    assert receipt['accepted_actions']==16 and receipt['last_sequence']==16
    assert receipt['last_record_sha256']==writer.last_digest and receipt['trace_bytes']==len(stream.getvalue())
    assert receipt['cpu_usage']['process_cpu_seconds']>=0
    assert receipt['complete_game_or_verification'] is False
    assert (tmp_path/'game-progress.json').read_bytes()!=first
    assert (tmp_path/'game-progress.json').stat().st_mode&0o777==0o600
    assert (tmp_path/'game-progress.json').stat().st_nlink==1
    assert not(tmp_path/'game-progress.new').exists()
    with pytest.raises(ValueError):module.read_progress(tmp_path/'game-progress.json',{'cell_id':'wrong'},'game')
    with pytest.raises(ValueError):recorder.update(0,writer.last_digest,writer.total_bytes,0,force=True)


@pytest.mark.parametrize('bad',['bool_count','negative_cpu','missing_identity','duplicate_key'])
def test_partial_receipts_refuse_invalid_counters_or_binding(tmp_path,bad):
    from scripts.archetype_trace_v3 import CpuAccounting
    module=subject();identity={'cell_id':'a'*64}
    recorder=module.ProgressRecorder(tmp_path,'game',identity,CpuAccounting())
    recorder.update(0,'b'*64,100,0,force=True)
    path=tmp_path/'game-progress.json';row=json.loads(path.read_text())
    if bad=='bool_count':row['accepted_actions']=False
    elif bad=='negative_cpu':row['cpu_usage']['process_cpu_seconds']=-1
    elif bad=='missing_identity':row['identity']={}
    else:
        path.write_text(path.read_text().replace('{','{"mode":"game",',1))
    if bad!='duplicate_key':path.write_text(json.dumps(row))
    with pytest.raises(ValueError):module.read_progress(path,identity,'game')


def test_import_remains_definition_only_without_ai_app_or_database(tmp_path):
    subject()
    code='''import json,sys
import scripts.archetype_worker_v3
print(json.dumps({x:x in sys.modules for x in ('main','ai.agent','persistence.db')}))
'''
    result=subprocess.run([sys.executable,'-B','-c',code],cwd=tmp_path,
        env={**os.environ,'PYTHONPATH':str(Path(__file__).parents[1])},text=True,capture_output=True,timeout=5)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)=={'main':False,'ai.agent':False,'persistence.db':False}
    assert not list(tmp_path.iterdir())


def phase_inputs():
    from card_data.seed_cards import seed_card_payload
    from types import SimpleNamespace
    rows=[{**seed_card_payload('Island'),'card_name':'Island','quantity':60}]
    cell={'cell_id':'c'*64,'seed':8877}
    policy={'max_ticks':4,'max_turns':100}
    identity={'cell_id':cell['cell_id'],'plan_sha256':'d'*64}
    choose=lambda state,moves,actor:SimpleNamespace(action={'type':'keep_hand'if state.pregame_pending else 'pass_priority'},reasoning='unit worker')
    return [rows,rows],cell,policy,identity,choose


def test_real_bounded_game_and_replay_phases_bind_trace_and_partial_progress(tmp_path):
    from scripts.archetype_trace_v3 import CpuAccounting
    module=subject();args,cell,policy,identity,choose=phase_inputs()
    assert callable(getattr(module,'game_phase',None)),'V3 game phase is missing'
    game=module.game_phase(args,cell,policy,identity,tmp_path,CpuAccounting(),choose=choose)
    assert game['outcome']['accepted_actions']==4 and game['outcome']['status']=='tick_limit'
    progress=module.read_progress(tmp_path/'game-progress.json',identity,'game')
    assert progress['accepted_actions']==4 and progress['complete_game_or_verification'] is False
    observed=[]
    def boundary(first,row):
        observed.append(row['step']);return {'step':row['step'],'kind':'authored_unit_boundary_not_HTTP'}
    verify_accounting=CpuAccounting()
    replay=module.verify_phase(args,cell,policy,identity,tmp_path,verify_accounting,
        accepted_actions=4,trace_sha256=game['trace_sha256'],boundary=boundary)
    assert replay['replay']['matched'] is True and replay['replay']['restart_roundtrips']==4
    assert observed==[0,3] and [r['step']for r in replay['handler_boundaries']]==[0,3]
    assert verify_accounting.calls['handler_check']==2
    progress=module.read_progress(tmp_path/'verify-progress.json',identity,'verify')
    assert progress['accepted_actions']==4 and progress['last_sequence']==5
    assert progress['complete_game_or_verification'] is False


@pytest.mark.parametrize('bad',['trace_sha','identity','policy','actions_bool'])
def test_verify_phase_refuses_binding_drift_before_progress_publication(tmp_path,bad):
    from scripts.archetype_trace_v3 import CpuAccounting
    module=subject();args,cell,policy,identity,choose=phase_inputs()
    assert callable(getattr(module,'game_phase',None)),'V3 game phase is missing'
    game=module.game_phase(args,cell,policy,identity,tmp_path,CpuAccounting(),choose=choose)
    sha=game['trace_sha256'];actions=4
    if bad=='trace_sha':sha='0'*64
    elif bad=='identity':identity={**identity,'plan_sha256':'0'*64}
    elif bad=='policy':policy={**policy,'max_ticks':5}
    else:actions=True
    with pytest.raises(ValueError):module.verify_phase(args,cell,policy,identity,tmp_path,CpuAccounting(),
        accepted_actions=actions,trace_sha256=sha)
    assert not(tmp_path/'verify-progress.json').exists()


def test_game_phase_enforces_quota_and_exclusive_trace_without_retry(tmp_path):
    from scripts.archetype_trace_v3 import CpuAccounting,TraceLimit
    module=subject();args,cell,policy,identity,choose=phase_inputs()
    assert callable(getattr(module,'game_phase',None)),'V3 game phase is missing'
    with pytest.raises(TraceLimit):module.game_phase(args,cell,policy,identity,tmp_path,CpuAccounting(),
        choose=choose,trace_max_bytes=64)
    assert (tmp_path/'trace.jsonl').read_bytes()==b''
    with pytest.raises(FileExistsError):module.game_phase(args,cell,policy,identity,tmp_path,CpuAccounting(),choose=choose)
    assert (tmp_path/'trace.jsonl').read_bytes()==b''


def request():
    import hashlib
    from scripts.archetype_plan_v3 import build_plan
    module=subject();source=Path(module.__file__).resolve();root=source.parents[2]
    plan=build_plan('a'*40,'archetype-pilot-20261116-v3-unit-worker',runtime_sha256='a'*64)
    return {'schema':3,'mode':'game','plan':plan,'cell':plan['cells'][0],
        'cpu':min(os.sched_getaffinity(0)),'cpu_seconds':1200,'wall_seconds':1500.,
        'memory_bytes':2147483648,'runtime_sha256':'a'*64,
        'source':{'root':str(root),'revision':'a'*40,
                  'files':{str(source.relative_to(root)):hashlib.sha256(source.read_bytes()).hexdigest()}},
        'trace_sha256':None,'accepted_actions':None}


@pytest.mark.parametrize('bad',['health','wall_bool','wall_large','mode','cell','source','sha','game_counter','extra'])
def test_worker_request_admits_only_exact_pilot_cell_before_resource_changes(bad):
    module=subject()
    assert callable(getattr(module,'validate_request',None)),'V3 worker request admission is missing'
    row=request();module.validate_request(row)
    if bad=='health':
        from scripts.archetype_plan_v3 import build_plan
        row['plan']=build_plan('a'*40,'archetype-health-20261116-v3-unit-worker',kind='health')
        row['cell']=row['plan']['cells'][0]
    elif bad=='wall_bool':row['wall_seconds']=True
    elif bad=='wall_large':row['wall_seconds']=1501
    elif bad=='mode':row['mode']='unknown'
    elif bad=='cell':row['cell']={**row['cell'],'seed':2026111901}
    elif bad=='source':row['source']['files']={}
    elif bad=='sha':row['runtime_sha256']='missing'
    elif bad=='game_counter':row['accepted_actions']=1
    else:row['extra']=True
    with pytest.raises(ValueError):module.validate_request(row)


def test_worker_cli_refuses_optimization_before_reading_request(tmp_path):
    subject()
    code='''import sys
from scripts.archetype_worker_v3 import main
raise SystemExit(main([sys.argv[1]]))
'''
    missing=tmp_path/'must-not-read.json'
    for opt in ('-O','-OO'):
        result=subprocess.run([sys.executable,opt,'-B','-c',code,str(missing)],
            cwd=Path(__file__).parents[1],text=True,capture_output=True,timeout=5)
        assert result.returncode!=0 and 'Run v3 worker' in result.stderr
        assert 'FileNotFoundError' not in result.stderr
