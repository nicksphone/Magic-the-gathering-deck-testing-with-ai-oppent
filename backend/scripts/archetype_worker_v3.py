"""V3 worker limits and durable partial CPU receipts; no game runs on import."""
import math
import os
from pathlib import Path
import resource
import signal
import sys
import time

from scripts.archetype_plan_v3 import (
    BUDGET_H2H_KIND, BUDGET_H2H_RUN_ID, EXTENDED_TRACE_RUN_IDS, MAX_CPU_SECONDS,
    MEMORY_BYTES, STRENGTH_RERUN2_CPU_SECONDS, validate_plan,
)
from scripts.archetype_trace_v3 import MAX_TRACE_BYTES, TRACE_SCHEMA, CpuAccounting, TraceLimit, canonical, digest, is_sha, load_json


def validate_limits(cpu, cpu_seconds, memory_bytes, *, run_id=None):
    ceiling = STRENGTH_RERUN2_CPU_SECONDS if run_id in EXTENDED_TRACE_RUN_IDS else MAX_CPU_SECONDS
    if (type(cpu) is not int or cpu not in os.sched_getaffinity(0)
            or type(cpu_seconds) is not int or not 1 <= cpu_seconds <= ceiling
            or type(memory_bytes) is not int or memory_bytes != MEMORY_BYTES):
        raise ValueError('Invalid v3 worker limits')


def apply_limits(cpu, cpu_seconds, memory_bytes, *, run_id=None):
    validate_limits(cpu,cpu_seconds,memory_bytes,run_id=run_id)
    os.sched_setaffinity(0,{cpu})
    resource.setrlimit(resource.RLIMIT_AS,(memory_bytes,memory_bytes))
    resource.setrlimit(resource.RLIMIT_CPU,(cpu_seconds,cpu_seconds+1))
    signal.signal(signal.SIGXCPU,signal.SIG_DFL)
    return {'affinity':sorted(os.sched_getaffinity(0)),
            'memory_bytes':resource.getrlimit(resource.RLIMIT_AS)[0],
            'cpu_soft_seconds':resource.getrlimit(resource.RLIMIT_CPU)[0]}


def _atomic_progress(path,value):
    data=canonical(value)+b'\n'
    if len(data)>16384:
        raise ValueError('Progress receipt is unexpectedly large')
    temporary=path.with_suffix('.new')
    fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as stream:
        stream.write(data);stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,path)
    parent=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:
        os.fsync(parent)
    finally:
        os.close(parent)


class ProgressRecorder:
    def __init__(self,directory,mode,identity,accounting):
        if type(mode) is not str or mode not in ('game','verify') or type(identity) is not dict:
            raise ValueError('Invalid progress identity')
        self.path=Path(directory)/f'{mode}-progress.json'
        self.mode,self.identity,self.accounting=mode,load_json(canonical(identity)),accounting
        self.last_sequence,self.last_actions,self.last_bytes=-1,0,0

    def update(self,sequence,sha,trace_bytes,accepted_actions,*,force=False):
        if (type(sequence) is not int or sequence<0 or sequence<self.last_sequence or not is_sha(sha)
                or type(trace_bytes) is not int or not self.last_bytes<=trace_bytes<=MAX_TRACE_BYTES
                or type(accepted_actions) is not int or not self.last_actions<=accepted_actions<=10000
                or type(force) is not bool):
            raise ValueError('Progress counters or binding differ')
        self.last_sequence,self.last_actions,self.last_bytes=sequence,accepted_actions,trace_bytes
        if not(force or sequence==0 or accepted_actions%16==0):
            return
        row={'schema':3,'mode':self.mode,'identity':self.identity,'last_sequence':sequence,
             'last_record_sha256':sha,'trace_bytes':trace_bytes,'accepted_actions':accepted_actions,
             'cpu_usage':self.accounting.snapshot(),'complete_game_or_verification':False}
        _atomic_progress(self.path,row)


def read_progress(path,identity,mode):
    with Path(path).open('rb') as stream:
        data=stream.read(16385)
    if len(data)>16384:
        raise ValueError('Progress receipt exceeds its bound')
    row=load_json(data)
    keys={'schema','mode','identity','last_sequence','last_record_sha256','trace_bytes',
          'accepted_actions','cpu_usage','complete_game_or_verification'}
    if (type(row) is not dict or set(row)!=keys or type(row['schema']) is not int or row['schema']!=3
            or row['mode']!=mode or digest(row['identity'])!=digest(identity)
            or type(row['last_sequence']) is not int or not 0<=row['last_sequence']<=10002
            or not is_sha(row['last_record_sha256']) or type(row['trace_bytes']) is not int
            or not 0<row['trace_bytes']<=MAX_TRACE_BYTES
            or type(row['accepted_actions']) is not int or not 0<=row['accepted_actions']<=10000
            or row['complete_game_or_verification'] is not False):
        raise ValueError('Invalid partial progress receipt')
    validate_cpu_usage(row['cpu_usage'])
    return row


def validate_cpu_usage(cpu):
    if type(cpu) is not dict or set(cpu)!={'category_seconds','category_calls','process_cpu_seconds','unattributed_cpu_seconds'}:
        raise ValueError('Invalid partial CPU fields')
    seconds,calls=cpu['category_seconds'],cpu['category_calls']
    if (type(seconds) is not dict or type(calls) is not dict or set(seconds)!=set(calls)
            or any(type(k) is not str for k in seconds)
            or any(type(v) is not int or v<0 for v in calls.values())):
        raise ValueError('Invalid partial CPU categories')
    numbers=[*seconds.values(),cpu['process_cpu_seconds'],cpu['unattributed_cpu_seconds']]
    if any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in numbers):
        raise ValueError('Invalid partial CPU measurement')
    if sum(seconds.values())>cpu['process_cpu_seconds']+1e-6:
        raise ValueError('Partial CPU categories overlap or exceed process CPU')


def budget_totals():
    return {role: {'decisions': 0, 'retained_available': 0, 'cpu_seconds': 0.,
                   'wall_seconds': 0., 'cutoffs': {'deadline': 0, 'node limit': 0}}
            for role in ('budgeted', 'unlimited')}


def count_budget_decision(totals, row, budgeted_seat):
    observation = row.get('budget_decision')
    if observation is None:
        return
    target = totals['budgeted' if row['actor'] == budgeted_seat else 'unlimited']
    target['decisions'] += 1
    target['retained_available'] += int(observation['retained'])
    target['cpu_seconds'] += observation['cpu_seconds']
    target['wall_seconds'] += row['decision_seconds']
    if observation['cutoff'] is not None:
        target['cutoffs'][observation['cutoff']] += 1


def game_phase(decks,cell,policy,identity,directory,accounting,*,choose=None,
               trace_max_bytes=MAX_TRACE_BYTES):
    from scripts.archetype_game_v3 import play_game
    from scripts.archetype_matrix_pilot import file_sha
    from scripts.archetype_trace_v3 import TraceWriter
    directory=Path(directory)
    recorder=ProgressRecorder(directory,'game',identity,accounting)
    trace=directory/'trace.jsonl'
    fd=os.open(trace,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    accepted=0
    totals = budget_totals() if policy.get('strength_run_id') == BUDGET_H2H_RUN_ID else None
    with os.fdopen(fd,'wb') as stream:
        writer=TraceWriter(stream,max_bytes=trace_max_bytes,accounting=accounting)
        def emit(row):
            nonlocal accepted
            writer.emit(row)
            accepted+=row['kind']=='action'
            if totals is not None:
                count_budget_decision(totals, row, identity['budgeted_seat'])
            force=row['kind'] in ('initial','rejected','decision_pause','final') or 'checkpoint' in row
            if force or accepted%16==0:
                with accounting.measure('trace_sync'):
                    os.fsync(stream.fileno())
            recorder.update(writer.sequence-1,writer.last_digest,writer.total_bytes,accepted,force=force)
        outcome=play_game(*decks,seed=cell['seed'],game_id=cell['cell_id'],policy=policy,
            identity=identity,emit=emit,accounting=accounting,choose=choose)
        os.fsync(stream.fileno())
    if outcome['accepted_actions']!=accepted:
        raise ValueError('Game and fully written action accounting differ')
    result = {'outcome':outcome,'trace_sha256':file_sha(trace),'trace_bytes':writer.total_bytes}
    if totals is not None:
        result['budget_decisions'] = totals
    return result


def verify_phase(decks,cell,policy,identity,directory,accounting,*,accepted_actions,
                 trace_sha256,boundary=None,trace_max_bytes=MAX_TRACE_BYTES):
    from scripts.archetype_game_v3 import replay_trace
    from scripts.archetype_matrix_pilot import file_sha
    from scripts.archetype_matrix_worker import selected_steps
    from scripts.archetype_trace_v3 import read_records
    directory=Path(directory);trace=directory/'trace.jsonl'
    if (type(accepted_actions) is not int or not 0<=accepted_actions<=policy['max_ticks']
            or not is_sha(trace_sha256) or file_sha(trace)!=trace_sha256):
        raise ValueError('Verification trace/counter binding differs')
    with trace.open('rb') as stream:
        first=next(read_records(stream,max_bytes=trace_max_bytes))
    expected={'identity':identity,'schema':TRACE_SCHEMA,'deck_a':decks[0],'deck_b':decks[1],
              'seed':cell['seed'],'game_id':cell['cell_id'],'policy':policy}
    if any(digest(first.get(k))!=digest(v)for k,v in expected.items()):
        raise ValueError('Verification header differs from admitted cell')
    recorder=ProgressRecorder(directory,'verify',identity,accounting)
    selected=selected_steps(accepted_actions);checks=[];last={}
    totals = budget_totals() if policy.get('strength_run_id') == BUDGET_H2H_RUN_ID else None
    with trace.open('rb') as stream:
        def records():
            for row in read_records(stream,max_bytes=trace_max_bytes):
                last.update(row=row,bytes=stream.tell())
                yield row
                if totals is not None:
                    count_budget_decision(totals, row, identity['budgeted_seat'])
        def check(first,row):
            with accounting.measure('handler_check'):
                checks.append(boundary(first,row))
        def observe(row):
            recorder.update(row['sequence'],row['record_sha256'],last['bytes'],row['step']+1,
                            force='checkpoint' in row)
        replay=replay_trace(records(),boundary=check if boundary is not None else None,
                            boundary_steps=selected,on_step=observe,accounting=accounting)
        if replay['actions']!=accepted_actions:
            raise ValueError('Verification action count differs')
        recorder.update(last['row']['sequence'],last['row']['record_sha256'],last['bytes'],
                        accepted_actions,force=True)
    if file_sha(trace)!=trace_sha256:
        raise ValueError('Verification input changed')
    if boundary is not None and {row.get('step')for row in checks}!=selected:
        raise ValueError('Selected handler checks are incomplete')
    result = {'replay':replay,'handler_boundaries':checks,'handler_checks_performed':boundary is not None}
    if totals is not None:
        result['budget_decisions'] = totals
    return result


def validate_request(request,*,kind='pilot'):
    from scripts.archetype_matrix_pilot import file_sha
    fields={'schema','mode','plan','cell','cpu','cpu_seconds','wall_seconds','memory_bytes',
            'runtime_sha256','source','trace_sha256','accepted_actions'}
    if (type(request) is not dict or set(request)!=fields
            or type(request['schema']) is not int or request['schema']!=3
            or type(request['mode']) is not str or request['mode'] not in ('game','verify')):
        raise ValueError('Invalid v3 worker request')
    plan=request['plan'];validate_plan(plan)
    if (type(kind)is not str or kind not in ('pilot','health','strength', BUDGET_H2H_KIND) or plan['kind']!=kind
            or not is_sha(plan['runtime_sha256'])
            or request['runtime_sha256']!=plan['runtime_sha256']
            or not any(digest(request['cell'])==digest(x)for x in plan['cells'])):
        raise ValueError('Only an exact newly registered role-bound cell may execute')
    validate_limits(request['cpu'],request['cpu_seconds'],request['memory_bytes'],run_id=plan['run_id'])
    if request['cpu_seconds'] > plan['policy']['max_cpu_seconds_per_game']:
        raise ValueError('Invalid remaining v3 CPU budget')
    seconds=request['wall_seconds']
    if type(seconds) not in (int,float) or not 0<seconds<=plan['policy']['max_seconds']:
        raise ValueError('Invalid remaining v3 wall budget')
    source=request['source'];root=Path(__file__).resolve().parents[2]
    relative=str(Path(__file__).resolve().relative_to(root))
    if (type(source) is not dict or set(source)!={'root','revision','files'}
            or source['root']!=str(root) or source['revision']!=plan['revision']
            or type(source['files']) is not dict
            or source['files'].get(relative)!=file_sha(__file__)
            or not is_sha(request['runtime_sha256'])):
        raise ValueError('V3 worker source/runtime binding differs')
    if kind != 'pilot':
        role_file=root/f'backend/scripts/archetype_{kind}_worker_v3.py'
        if source['files'].get(str(role_file.relative_to(root)))!=file_sha(role_file):
            raise ValueError(f'{kind.capitalize()} worker source binding differs')
    if request['mode']=='game':
        if request['trace_sha256'] is not None or request['accepted_actions'] is not None:
            raise ValueError('Game request cannot assert a previous outcome')
    elif (not is_sha(request['trace_sha256']) or type(request['accepted_actions']) is not int
          or not 0<=request['accepted_actions']<=plan['policy']['max_ticks']):
        raise ValueError('Verification must bind the completed game trace')


def request_identity(request):
    identity = {'cell_id':request['cell']['cell_id'],'plan_sha256':digest(request['plan']),
            'source_sha256':digest(request['source']),'runtime_sha256':request['runtime_sha256'],
            'trace_schema':TRACE_SCHEMA}
    if request['plan']['kind'] == BUDGET_H2H_KIND:
        identity['budgeted_seat'] = request['cell']['deck_a_seat']
    return identity


def main(argv=None,*,kind='pilot'):
    if sys.flags.optimize or not sys.flags.dont_write_bytecode:
        raise SystemExit('Run v3 worker without optimization and with -B')
    args=sys.argv[1:] if argv is None else argv
    if len(args)!=1:
        raise ValueError('One private worker request path is required')
    request_path=Path(args[0]).resolve(strict=True)
    with request_path.open('rb') as stream:
        data=stream.read(4*1024*1024+1)
    if len(data)>4*1024*1024:
        raise ValueError('Worker request exceeds its bound')
    request=load_json(data);validate_request(request,kind=kind)
    run_id=request['plan']['run_id']
    rerun_limits = {'run_id': run_id} if run_id in EXTENDED_TRACE_RUN_IDS else {}
    controls=apply_limits(request['cpu'],request['cpu_seconds'],request['memory_bytes'],**rerun_limits)
    signal.signal(signal.SIGALRM,signal.SIG_DFL)
    signal.setitimer(signal.ITIMER_REAL,request['wall_seconds'])
    os.umask(0o077)
    mode=request['mode'];directory=request_path.parent
    database=directory/'handler.db' if mode=='verify' else None
    if database is not None:
        os.environ['MTG_DATABASE_PATH']=str(database)
    from scripts.archetype_matrix_worker import configure_cache,install_guard
    install_guard(database)
    from scripts.archetype_matrix_pilot import publish,runtime_identity,verify_sources
    from scripts.archetype_plan_v3 import execution_matrix
    from scripts.archetype_game_v3 import TraceDivergence,admit_decks,cell_decks
    accounting=CpuAccounting();started=time.monotonic()
    identity=request_identity(request)
    result={'schema':3,'mode':mode,'cell_id':request['cell']['cell_id'],
            'identity':identity,'controls':controls}
    rc=0
    try:
        verify_sources(request['source'])
        if digest(runtime_identity())!=request['runtime_sha256']:
            raise ValueError('Runtime changed before phase')
        configure_cache(directory/'offline-cache')
        decks=cell_decks(admit_decks(execution_matrix(request['plan'])),request['cell'])
        # Absolute process CPU includes interpreter/bootstrap and all admission.
        accounting.seconds['setup']=time.process_time();accounting.calls['setup']=1
        trace_options = {}
        if kind in ('strength', BUDGET_H2H_KIND):
            trace_options['trace_max_bytes'] = request['plan']['trace_policy']['max_bytes']
        if mode=='game':
            chooser = {}
            if kind == 'strength':
                from scripts.archetype_strength_worker_v3 import choose_for_cell
                chooser['choose'] = choose_for_cell(decks, request['cell'])
            elif kind == BUDGET_H2H_KIND:
                from scripts.archetype_budget_h2h_worker_v3 import choose_for_cell
                chooser['choose'] = choose_for_cell(decks, request['cell'])
            result.update(game_phase(decks,request['cell'],request['plan']['policy'],identity,
                                     directory,accounting,**trace_options,**chooser))
        else:
            from scripts.archetype_handler_v3 import HandlerChecks
            verify_started=time.monotonic()
            with HandlerChecks(database) as handler:
                result.update(verify_phase(decks,request['cell'],request['plan']['policy'],identity,
                    directory,accounting,accepted_actions=request['accepted_actions'],
                    trace_sha256=request['trace_sha256'],boundary=handler,**trace_options))
            result['replay_seconds']=time.monotonic()-verify_started
        with accounting.measure('source_runtime_recheck'):
            verify_sources(request['source'])
            if digest(runtime_identity())!=request['runtime_sha256']:
                raise ValueError('Runtime changed during phase')
    except TraceLimit:
        rc=1;result['error']='trace_limit'
    except TraceDivergence as exc:
        rc=1;result.update(error='replay_divergence',first_divergence={'step':exc.step,'fields':exc.fields})
    except MemoryError:
        rc=1;result['error']='memory_limit'
    except Exception as exc:
        rc=1;result.update(error='worker_error',exception_class=type(exc).__name__)
    usage=resource.getrusage(resource.RUSAGE_SELF)
    result.update(cpu_seconds=usage.ru_utime+usage.ru_stime,peak_rss_bytes=usage.ru_maxrss*1024,
                  seconds=time.monotonic()-started,cpu_usage=accounting.snapshot())
    publish(directory/f'{mode}-result.json',result)
    return rc


if __name__=='__main__':
    raise SystemExit(main())
