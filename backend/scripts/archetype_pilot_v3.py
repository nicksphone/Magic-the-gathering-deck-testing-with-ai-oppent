"""Fresh 36-cell v3 pilot; no health-matrix execution or RC/strength acceptance."""
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import contextmanager
import math
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

from scripts.archetype_matrix_pilot import (
    BACKEND, available_memory, boot_time, file_sha, publish, runtime_identity,
    source_identity, verify_sources, worker_environment,
)
from scripts.archetype_plan_v3 import LEGACY_CAMPAIGN_HOURS, STANDARD_WALL_SECONDS, build_plan, validate_plan
from scripts.archetype_trace_v3 import digest, is_sha, load_json, verify_progress_prefix
from scripts.archetype_worker_v3 import read_progress, request_identity, validate_cpu_usage, validate_request
from scripts.archetype_registry_v3 import claim_run

STATE_ROOT=Path.home()/'.local/state/mtg/archetype-v3'


def host_offset():
    return boot_time()-time.monotonic()


def run_process(command,*,directory,name,environment,seconds,stop):
    """Reap this owned child with wait4, never Popen.poll's usage-losing waitpid."""
    if type(seconds) not in (int,float) or not math.isfinite(seconds) or seconds<=0:
        raise ValueError('Positive remaining wall budget required')
    empty={'started':False,'waited':False,'returncode':None,'termination':'cancelled',
           'cpu_seconds':0.,'peak_rss_bytes':0}
    if stop.is_set():
        return empty
    started,offset=boot_time(),host_offset()
    process=None;usage=None;termination=None
    def reap(block=False):
        nonlocal usage
        pid,status,observed=os.wait4(process.pid,0 if block else os.WNOHANG)
        if pid:
            process.returncode=os.waitstatus_to_exitcode(status);usage=observed
            return True
        return False
    def terminate():
        if reap():
            return
        try:
            os.killpg(process.pid,signal.SIGTERM)
        except ProcessLookupError:
            pass
        until=time.monotonic()+1
        while time.monotonic()<until:
            if reap():
                return
            time.sleep(.01)
        try:
            os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:
            pass
        reap(True)
    def logfile(suffix):
        return os.fdopen(os.open(directory/f'{name}.{suffix}',
            os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb')
    with logfile('stdout') as out,logfile('stderr') as err:
        try:
            process=subprocess.Popen(command,cwd=BACKEND,env=environment,stdin=subprocess.DEVNULL,
                                     stdout=out,stderr=err,start_new_session=True)
            while not reap():
                if abs(host_offset()-offset)>.25:
                    termination='host_sleep';stop.set()
                elif stop.is_set():
                    termination='cancelled'
                elif boot_time()-started>=seconds:
                    termination='wall_limit'
                if termination:
                    terminate();break
                stop.wait(min(.05,max(0,seconds-(boot_time()-started))))
        except BaseException:
            if process is not None and process.returncode is None:
                terminate()
            raise
    return {'started':True,'waited':True,'returncode':process.returncode,'termination':termination,
            'cpu_seconds':usage.ru_utime+usage.ru_stime,'peak_rss_bytes':usage.ru_maxrss*1024}


class SlotBudget:
    """Charge both planned slots throughout controller lifetime, including idle."""
    reserved_health_seconds=30*3600
    campaign_seconds=LEGACY_CAMPAIGN_HOURS*3600
    pilot_with_overhead_seconds=18*3600

    def __init__(self,*,started,prior_charged_seconds=0.):
        self.started=started
        self.prior_charged_seconds=prior_charged_seconds

    def charged_seconds(self,now):
        return max(0.,2*(now-self.started))

    def remaining_campaign_seconds(self,now):
        return max(0.,self.campaign_seconds-self.prior_charged_seconds-self.charged_seconds(now))

    def exceeded(self,now):
        return self.prior_charged_seconds+self.charged_seconds(now)>self.pilot_with_overhead_seconds

    def can_launch(self,*,now,unstarted,pending_deadlines):
        remaining=self.pilot_with_overhead_seconds-self.prior_charged_seconds-self.charged_seconds(now)
        reserved=unstarted*STANDARD_WALL_SECONDS+sum(max(0.,deadline-now)for deadline in pending_deadlines)
        return remaining>=reserved


def _read_result(path):
    with path.open('rb') as stream:
        data=stream.read(1024*1024+1)
    if len(data)>1024*1024:
        raise ValueError('Worker result is unexpectedly large')
    return load_json(data)


def _number(value):
    return type(value) in (int,float) and math.isfinite(value) and value>=0


def _common_result(result,request,process):
    if (type(result) is not dict or type(result.get('schema')) is not int or result['schema']!=3
            or result.get('mode')!=request['mode'] or result.get('cell_id')!=request['cell']['cell_id']
            or digest(result.get('identity'))!=digest(request_identity(request))
            or process.get('started') is not True or process.get('waited') is not True
            or not _number(result.get('cpu_seconds')) or not _number(process.get('cpu_seconds'))
            or result['cpu_seconds']>process['cpu_seconds']+.02
            or type(result.get('peak_rss_bytes')) is not int or result['peak_rss_bytes']<0
            or not _number(result.get('seconds'))
            or digest(result.get('controls'))!=digest({'affinity':[request['cpu']],
                'memory_bytes':request['memory_bytes'],'cpu_soft_seconds':request['cpu_seconds']})):
        raise ValueError('Worker completion does not bind its admission')
    validate_cpu_usage(result.get('cpu_usage'))
    if result['cpu_usage']['process_cpu_seconds']>process['cpu_seconds']+.02:
        raise ValueError('Worker CPU exceeds actual waited usage')


def _outcome(value,plan):
    if (type(value) is not dict or set(value)!={'status','winner','termination','accepted_actions','turn'}
            or type(value['accepted_actions']) is not int or not 0<=value['accepted_actions']<=plan['policy']['max_ticks']
            or type(value['turn']) is not int or value['turn']<1
            or value['status'] not in ('resolved','draw','tick_limit','turn_limit','error')
            or type(value['termination']) is not str):
        raise ValueError('Invalid game outcome')
    if value['status']=='resolved':
        if type(value['winner']) is not int or value['winner'] not in (1,2):
            raise ValueError('Resolved game has no genuine winner')
    elif value['winner'] is not None:
        raise ValueError('Non-winning outcome claims a winner')


def _row(cell,directory,started,stages,outcome,error,invalid):
    actual=[s.get('cpu_seconds')for s in stages]
    closed=all(s.get('started')is False or s.get('started')is True and s.get('waited')is True for s in stages)
    cpu=sum(actual) if closed and all(_number(v)for v in actual) else None
    by_phase={};partial_actions=None
    for stage in stages:
        receipt=stage.get('result')if stage.get('result_valid') else None
        usage=(receipt or {}).get('cpu_usage')or(stage.get('progress')or{}).get('cpu_usage')
        if usage is not None:
            by_phase[stage['mode']]=usage
        if stage['mode']=='game' and stage.get('progress'):
            partial_actions=stage['progress']['accepted_actions']
    measured=sum(sum(x['category_seconds'].values())for x in by_phase.values())
    trace=directory/'trace.jsonl'
    status='error' if error else (outcome or {}).get('status','error')
    if error in ('cpu_limit','wall_limit','memory_limit','trace_limit'):
        status='timeout'
    if error=='replay_divergence':
        status='replay_divergence'
    verified=not error and len(stages)==2 and all(s.get('result_valid')for s in stages)
    return {'cell_id':cell['cell_id'],'status':status,'winner':None if error else (outcome or {}).get('winner'),
        'termination':error or(outcome or{}).get('termination','worker_error'),
        'accepted_actions':(outcome or{}).get('accepted_actions'),'accepted_actions_partial':partial_actions,
        'seconds':boot_time()-started,'cpu_seconds':cpu,
        'child_handles_reaped':closed,
        'peak_rss_bytes':max([s.get('peak_rss_bytes',0)for s in stages],default=0),
        'cpu_attribution_complete':bool(stages)and all(s.get('result_valid')for s in stages),
        'cpu_usage_by_phase':by_phase,'unattributed_cpu_seconds':max(0.,cpu-measured)if cpu is not None else None,
        'parity_checked':bool(verified),'run_invalid':invalid,'stages':stages,
        'trace_sha256':file_sha(trace)if trace.exists()else None,'trace_bytes':trace.stat().st_size if trace.exists()else 0,
        'replay_seconds':(stages[-1].get('result')or{}).get('replay_seconds')if len(stages)==2 else None}


def run_cell(plan,cell,directory,*,cpu,source,runtime,stop,kind='pilot'):
    started,offset=boot_time(),host_offset()
    directory=Path(directory);directory.mkdir(mode=0o700)
    stages=[];outcome=None;error=None
    cpu_limit=plan['policy']['max_cpu_seconds_per_game']
    wall_limit=plan['policy']['max_seconds']
    try:
        verify_sources(source)
        if digest(runtime_identity())!=digest(runtime):
            raise ValueError('Runtime changed')
        for mode in ('game','verify'):
            if stop.is_set():
                error='cancelled';break
            seconds=wall_limit-(boot_time()-started)
            remaining=cpu_limit-sum(s['cpu_seconds']for s in stages)
            if seconds<=0 or remaining<1:
                error='wall_limit'if seconds<=0 else 'cpu_limit';break
            request={'schema':3,'mode':mode,'plan':plan,'cell':cell,'cpu':cpu,
                'cpu_seconds':math.floor(remaining),'wall_seconds':seconds,
                'memory_bytes':plan['policy']['max_memory_bytes_per_worker'],'source':source,
                'runtime_sha256':digest(runtime),'trace_sha256':file_sha(directory/'trace.jsonl')if mode=='verify'else None,
                'accepted_actions':outcome['accepted_actions']if outcome else None}
            validate_request(request,kind=kind)
            path=directory/f'{mode}-request.json';publish(path,request)
            stage={'mode':mode,'attempted':True,'started':None,'waited':False,
                   'cpu_seconds':None,'peak_rss_bytes':0}
            stages.append(stage)
            worker='scripts.archetype_worker_v3' if kind=='pilot' else f'scripts.archetype_{kind}_worker_v3'
            process=run_process([sys.executable,'-B','-m',worker,str(path)],
                directory=directory,name=mode,environment=worker_environment(BACKEND),seconds=seconds,stop=stop)
            stage.update(process)
            if not _number(process.get('cpu_seconds')):
                raise ValueError('Actual child usage missing')
            result_path=directory/f'{mode}-result.json'
            if result_path.exists():
                try:
                    stage['result']=_read_result(result_path)
                    _common_result(stage['result'],request,process)
                    stage['result_valid']=True
                except (ValueError,TypeError,OSError):
                    stage['result_unreadable_or_unbound']=True
            progress_path=directory/f'{mode}-progress.json'
            if progress_path.exists():
                try:
                    stage['progress']=read_progress(progress_path,request_identity(request),mode)
                    trace=directory/'trace.jsonl'
                    if trace.stat().st_size>plan['trace_policy']['max_bytes']:
                        raise ValueError('Trace exceeds its registered bound')
                    with trace.open('rb')as stream:
                        stage['progress_boundary']=verify_progress_prefix(stream,stage['progress'])
                    if stage['progress']['cpu_usage']['process_cpu_seconds']>process['cpu_seconds']+.02:
                        raise ValueError('Partial CPU exceeds actual wait')
                except (ValueError,TypeError,OSError):
                    stage.pop('progress',None);stage['progress_unreadable_or_unbound']=True
            if process.get('termination'):
                error=process['termination'];break
            rc=process.get('returncode')
            if rc!=0:
                if rc==-signal.SIGXCPU:error='cpu_limit'
                elif rc==-signal.SIGALRM:error='wall_limit'
                elif type(rc)is int and rc<0:error='worker_crash';stop.set()
                else:
                    error=(stage.get('result')or{}).get('error')if stage.get('result_valid')else None
                    if error not in ('memory_limit','trace_limit','replay_divergence','worker_error'):
                        error='worker_protocol'
                    if error in ('worker_error','worker_protocol','replay_divergence'):stop.set()
                break
            if not stage.get('result_valid') or not stage.get('progress'):
                error='worker_protocol';stop.set();break
            if (stage['progress_boundary']['last_kind']!='final'
                    or stage['progress']['trace_bytes']!=(directory/'trace.jsonl').stat().st_size):
                error='worker_protocol';stop.set();break
            result=stage['result']
            if mode=='game':
                outcome=result.get('outcome');_outcome(outcome,plan)
                if result.get('trace_sha256')!=file_sha(directory/'trace.jsonl'):
                    raise ValueError('Completed trace changed')
            else:
                replay=result.get('replay');selected={0,outcome['accepted_actions']-1}|set(range(0,outcome['accepted_actions'],100))if outcome['accepted_actions']else set()
                checks=result.get('handler_boundaries')
                if (type(replay)is not dict or replay.get('matched')is not True
                        or replay.get('status')!=outcome['status']
                        or digest(replay.get('outcome'))!=digest(outcome)
                        or type(replay.get('actions'))is not int or replay['actions']!=outcome['accepted_actions']
                        or type(replay.get('restart_roundtrips'))is not int or replay['restart_roundtrips']!=outcome['accepted_actions']
                        or result.get('handler_checks_performed')is not True or type(checks)is not list
                        or len(checks)!=len(selected) or any(type(x)is not dict or type(x.get('step'))is not int for x in checks)
                        or {x['step']for x in checks}!=selected):
                    error='replay_divergence';stop.set();break
            count=outcome['accepted_actions']
            expected_sequence=count+(2 if outcome['termination']=='rejected_action'else 1)
            if stage['progress']['accepted_actions']!=count or stage['progress']['last_sequence']!=expected_sequence:
                error='worker_protocol';stop.set();break
            if sum(s['cpu_seconds']for s in stages)>cpu_limit:
                error='cpu_limit';break
        verify_sources(source)
        if digest(runtime_identity())!=digest(runtime):
            raise ValueError('Runtime changed')
    except Exception:
        error='source_runtime_or_controller_error';stop.set()
    if abs(host_offset()-offset)>.25:
        error='host_sleep';stop.set()
    if not error and boot_time()-started>wall_limit:
        error='wall_limit'
    row=_row(cell,directory,started,stages,outcome,error,stop.is_set())
    publish(directory/'cell-result.json',row)
    return row


def pilot_report(rows,plan):
    expected=[cell['cell_id']for cell in plan['cells']]
    seen=[row['cell_id']for row in rows]
    if len(set(seen))!=len(seen)or any(x not in expected for x in seen):
        raise ValueError('Duplicate or undeclared pilot result')
    complete=seen==expected and not any(row.get('run_invalid')for row in rows)
    usable=complete and all(row.get('status')in('resolved','draw')and row.get('parity_checked')is True
        and row.get('cpu_attribution_complete')is True and row.get('child_handles_reaped')is True
        and _number(row.get('cpu_seconds'))for row in rows)
    seconds=sorted(row['seconds']for row in rows)
    statuses={status:sum(row['status']==status for row in rows)for status in sorted({r['status']for r in rows})}
    mean=sum(seconds)/len(seconds)if seconds else None
    p95=seconds[max(0,math.ceil(.95*len(seconds))-1)]if seconds else None
    total_bytes=sum(row['trace_bytes']for row in rows)
    return {'scheduled':len(expected),'accounted':len(rows),'complete':complete,'usable':usable,
        'statuses':statuses,'accepts_matrix_or_strength':False,'statistical_gate_complete':False,
        'mean_cell_seconds':mean,'p95_cell_seconds':p95,'trace_bytes':total_bytes,
        'forecast_1440_worker_hours':1440*mean/3600 if usable else None,
        'forecast_72_worker_hours':72*mean/3600 if usable else None,
        'forecast_trace_bytes':total_bytes*40 if usable else None,
        'forecast_reason':'completed_games_and_verification'if usable else 'incomplete_or_censored_or_failed_cells',
        'cpu_usage_available_cells':sum(_number(row.get('cpu_seconds'))for row in rows),
        'replay_time_available_cells':sum(_number(row.get('replay_seconds'))for row in rows)}


def run_pilot(plan,directory):
    return _admit_run(plan,directory,kind='pilot',budget_factory=SlotBudget,
                      reporter=pilot_report,prefix='PILOT')


def _admit_run(plan,directory,*,kind,budget_factory,reporter,prefix):
    started=boot_time();offset=host_offset()
    validate_plan(plan)
    if plan['kind']!=kind or not is_sha(plan['runtime_sha256']):
        raise ValueError(f'Only a runtime-bound v3 {kind} may execute here')
    source=source_identity(plan['revision']);runtime=runtime_identity()
    if digest(runtime)!=plan['runtime_sha256']:
        raise ValueError('Runtime differs from pre-registration')
    cpus=sorted(os.sched_getaffinity(0))
    if len(cpus)<3 or available_memory()<5*1024**3:
        raise ValueError('Two affinity slots plus controller/5GiB headroom required')
    from scripts.archetype_game_v3 import admit_decks
    admit_decks(plan['source_matrix'])
    directory=Path(directory)
    if (not directory.is_absolute() or directory.resolve()!=directory
            or directory.is_relative_to(BACKEND.parent)):
        raise ValueError('Absent canonical private output outside checkout required')
    from persistence.job_retention import local_path
    directory=local_path(directory,existing=False)
    with claim_run(STATE_ROOT,run_id=plan['run_id'],plan_sha256=digest(plan),revision=plan['revision'],
                   runtime_sha256=plan['runtime_sha256'],output=str(directory),kind=kind)as claim:
        extra={}
        if kind=='health':
            extra.update(prior_health_charged_seconds=claim.prior_health_charged_seconds,
                         wall_seconds=plan['policy']['max_seconds'])
        if kind=='strength':
            extra['wall_seconds']=plan['policy']['max_seconds']
        budget=budget_factory(started=started,prior_charged_seconds=claim.prior_charged_seconds,**extra)
        return _registered_pilot(plan,directory,source,runtime,cpus,started,budget,offset,claim,
                                 reporter=reporter,prefix=prefix,kind=kind)


@contextmanager
def _pool(stop):
    with ThreadPoolExecutor(max_workers=2)as pool:
        try:
            yield pool
        except BaseException:
            stop.set()
            raise


def _registered_pilot(plan,directory,source,runtime,cpus,started,budget,offset,claim,*,
                      reporter=pilot_report,prefix='PILOT',kind='pilot'):
    stop=threading.Event();rows={};pending={};next_index=0;available=cpus[:2]
    previous_handlers={}
    def cancel(_signal,_frame):
        stop.set()
    budget_refused=False
    try:
        directory.mkdir(mode=0o700)
        publish(directory/'plan.json',plan);publish(directory/'source.json',source);publish(directory/'runtime.json',runtime)
        for signum in (signal.SIGINT,signal.SIGTERM):
            previous_handlers[signum]=signal.signal(signum,cancel)
        with _pool(stop)as pool:
            while True:
                if abs(host_offset()-offset)>.25:
                    stop.set()
                if budget.exceeded(boot_time()):
                    stop.set();budget_refused=True
                while available and next_index<len(plan['cells']) and not stop.is_set():
                    now=boot_time()
                    if not budget.can_launch(now=now,unstarted=len(plan['cells'])-next_index,
                                             pending_deadlines=[value[2]for value in pending.values()]):
                        stop.set();budget_refused=True;break
                    index=next_index;next_index+=1;cpu=available.pop()
                    extra={'kind':kind} if kind!='pilot' else {}
                    future=pool.submit(run_cell,plan,plan['cells'][index],directory/f'{index:03d}',
                                       cpu=cpu,source=source,runtime=runtime,stop=stop,**extra)
                    pending[future]=(index,cpu,now+plan['policy']['max_seconds'])
                if not pending:
                    break
                finished,_=wait(pending,timeout=.25,return_when=FIRST_COMPLETED)
                for future in finished:
                    index,cpu,_deadline=pending.pop(future);available.append(cpu)
                    try:
                        rows[index]=future.result()
                    except Exception:
                        stop.set()
        ordered=[rows[index]for index in sorted(rows)]
        verify_sources(source)
        if digest(runtime_identity())!=plan['runtime_sha256']:
            stop.set()
        if budget.exceeded(boot_time()):
            stop.set();budget_refused=True
        report=reporter(ordered,plan)
        report.update(run_id=plan['run_id'],plan_sha256=digest(plan),source_sha256=digest(source),
            runtime_sha256=digest(runtime),elapsed_seconds=boot_time()-started,
            charged_worker_seconds=budget.charged_seconds(boot_time()),
            charged_campaign_worker_seconds=budget.prior_charged_seconds+budget.charged_seconds(boot_time()),
            remaining_campaign_worker_seconds=budget.remaining_campaign_seconds(boot_time()),
            reserved_health_worker_seconds=budget.reserved_health_seconds,budget_refused=budget_refused)
        report['complete']=bool(report['complete']and not stop.is_set()and abs(host_offset()-offset)<=.25)
        report['usable']=bool(report['usable']and report['complete'])
        if not report['usable'] and kind!='strength':
            report['forecast_reason']='incomplete_or_censored_or_failed_cells'
            for key in ('forecast_1440_worker_hours','forecast_72_worker_hours','forecast_trace_bytes'):
                report[key]=None
        if kind=='strength':
            report['strength_passed']=report['usable']
        if kind=='health':
            report.update(health_passed=bool(report['usable'] and report['complete']),
                charged_health_worker_seconds=claim.prior_health_charged_seconds+budget.charged_seconds(boot_time()),
                remaining_health_worker_seconds=budget.remaining_health_seconds(boot_time()))
        report_path=directory/(f'{prefix}-COMPLETE.json'if report['complete']else f'{prefix}-INCOMPLETE.json')
        publish(report_path,report)
        # A returned row must contain actual wait usage, not an unproven child.
        if next_index==len(rows)and all(row.get('child_handles_reaped')is True and _number(row.get('cpu_seconds'))for row in rows.values()):
            closed=claim.finish(charged_worker_seconds=budget.charged_seconds(boot_time()),report_sha256=file_sha(report_path))
            if kind=='health' and report['usable'] and (closed['health_budget_exceeded']
                    or closed['charged_campaign_worker_seconds']>budget.campaign_seconds):
                raise ValueError('Health budget exceeded during final publication; report alone is not acceptance')
            if (kind=='strength' and report['strength_passed']
                    and closed['charged_campaign_worker_seconds']>budget.campaign_seconds):
                raise ValueError('Strength budget exceeded during final publication')
        return report
    finally:
        stop.set()
        for signum,previous in previous_handlers.items():
            signal.signal(signum,previous)
        if not claim.finished and next_index==len(rows)and all(row.get('child_handles_reaped')is True and _number(row.get('cpu_seconds'))for row in rows.values()):
            claim.finish(charged_worker_seconds=budget.charged_seconds(boot_time()),report_sha256=None)


def main(argv=None):
    if sys.flags.optimize or not sys.flags.dont_write_bytecode:
        raise SystemExit('Run v3 pilot without optimization and with -B')
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('plan');p.add_argument('run_id');p.add_argument('output',type=Path)
    p.add_argument('--kind',choices=('pilot','health'),default='pilot')
    r=sub.add_parser('run');r.add_argument('plan',type=Path);r.add_argument('output',type=Path)
    r.add_argument('--execute-pilot',action='store_true',required=True)
    args=parser.parse_args(argv)
    if args.command=='plan':
        if (not args.output.is_absolute()or args.output.resolve()!=args.output
                or args.output.is_relative_to(BACKEND.parent)):
            raise ValueError('Private plan output outside checkout required')
        revision=subprocess.check_output(['git','-C',str(BACKEND.parent),'rev-parse','HEAD'],text=True).strip()
        source_identity(revision)
        runtime=runtime_identity()
        plan=build_plan(revision,args.run_id,kind=args.kind,runtime_sha256=digest(runtime))
        publish(args.output,plan)
        return 0
    with args.plan.open('rb')as stream:
        data=stream.read(4*1024*1024+1)
    if len(data)>4*1024*1024:
        raise ValueError('Plan exceeds its bound')
    report=run_pilot(load_json(data),args.output)
    print(json.dumps({key:report[key]for key in ('complete','usable','accounted','statuses','accepts_matrix_or_strength')}))
    return 0 if report['usable']else 1


if __name__=='__main__':
    raise SystemExit(main())
