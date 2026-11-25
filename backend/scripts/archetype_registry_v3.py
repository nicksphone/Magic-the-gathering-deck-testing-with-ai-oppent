"""Cooperative host-local controller exclusion and permanently consumed run IDs."""
from contextlib import contextmanager
import fcntl
import math
import os
from pathlib import Path
import re
import stat

from scripts.archetype_plan_v3 import (
    HEALTH_RERUN_ID, LEGACY_CAMPAIGN_HOURS, STRENGTH_CAMPAIGN_ID,
    STRENGTH_EXTENDED_IDS, STRENGTH_RUN_ID, strength_campaign_hours, valid_run_id,
)
from scripts.archetype_trace_v3 import canonical, is_sha, load_json


def _campaign_seconds(kind, run_id):
    return (strength_campaign_hours(run_id) if kind == 'strength' else LEGACY_CAMPAIGN_HOURS) * 3600


def _directory(path):
    if not path.is_absolute() or path.resolve()!=path:
        raise ValueError('Registry must not be an alias')
    path.mkdir(mode=0o700,parents=True,exist_ok=True)
    info=path.lstat()
    if not stat.S_ISDIR(info.st_mode)or info.st_uid!=os.getuid()or stat.S_IMODE(info.st_mode)!=0o700:
        raise ValueError('Private owned registry directory required')


def _regular(info):
    if not stat.S_ISREG(info.st_mode)or info.st_uid!=os.getuid()or info.st_nlink!=1 or stat.S_IMODE(info.st_mode)!=0o600:
        raise ValueError('Private regular single-link registry file required')


def _sync(directory):
    fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)


def _read(path):
    try:_regular(path.lstat())
    except FileNotFoundError:return None
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_NOCTTY)
    with os.fdopen(fd,'rb')as stream:
        _regular(os.fstat(stream.fileno()));data=stream.read(16385)
    if len(data)>16384:
        raise ValueError('Registry record exceeds its bound')
    return load_json(data)


def _write(path,row,*,replace=False):
    data=canonical(row)+b'\n'
    target=path.with_suffix('.new')if replace else path
    if len(data)>16384:
        raise ValueError('Registry record exceeds its bound')
    fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb')as stream:
        _regular(os.fstat(stream.fileno()));stream.write(data);stream.flush();os.fsync(stream.fileno())
    if replace:os.replace(target,path)
    _sync(path.parent)


class Claim:
    def __init__(self,root,path,record):
        self.root,self.path,self.record=root,path,record
        self.finished=False
        self.prior_charged_seconds=record['charged_before_worker_seconds']
        self.prior_health_charged_seconds=record['charged_health_before_worker_seconds']

    def finish(self,*,charged_worker_seconds,report_sha256):
        if (self.finished or type(charged_worker_seconds)not in(int,float)
                or not math.isfinite(charged_worker_seconds)or charged_worker_seconds<0
                or report_sha256 is not None and not is_sha(report_sha256)):
            raise ValueError('Invalid or repeated controller closure')
        cumulative=self.prior_charged_seconds+charged_worker_seconds
        health=self.prior_health_charged_seconds+(charged_worker_seconds if self.record['kind']=='health' else 0.)
        strength=self.record.get('charged_strength_before_worker_seconds',0.)
        if self.record['kind']=='strength':
            strength+=charged_worker_seconds
        row={**self.record,'state':'closed','child_handles_reaped':True,
             'charged_worker_seconds':charged_worker_seconds,
             'charged_campaign_worker_seconds':cumulative,
             'remaining_campaign_worker_seconds':max(0.,self.record['campaign_worker_seconds']-cumulative),
             'charged_health_worker_seconds':health,'remaining_health_worker_seconds':max(0.,30*3600-health),
             'health_budget_exceeded':health>30*3600,
             'report_sha256':report_sha256,'pilot_budget_exceeded':cumulative-health-strength>18*3600}
        if 'charged_strength_before_worker_seconds' in self.record:
            row['charged_strength_worker_seconds']=strength
        _write(self.path,row,replace=True)
        _write(self.root/'active.json',row,replace=True)
        self.finished=True
        return row


@contextmanager
def claim_run(root,*,run_id,plan_sha256,revision,runtime_sha256,output,kind='pilot'):
    if (not valid_run_id(kind, run_id)
            or not is_sha(plan_sha256)or not is_sha(runtime_sha256)
            or type(revision)is not str or re.fullmatch('[0-9a-f]{40}',revision)is None
            or type(output)is not str or not Path(output).is_absolute()):
        raise ValueError('Invalid run consumption identity')
    root=Path(root);_directory(root);_directory(root/'runs')
    lock=os.open(root/'controller.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    try:
        _regular(os.fstat(lock));os.set_inheritable(lock,False)
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as exc:raise ValueError('Another v3 controller owns the host slots')from exc
        active=_read(root/'active.json')
        if active is not None and (type(active)is not dict or active.get('state')!='closed'
                                   or active.get('child_handles_reaped')is not True):
            raise ValueError('Previous v3 controller closure is unproven; do not reset state automatically')
        if active is not None:
            active_kind=active.get('kind','pilot')
            if (type(active_kind) is not str or active_kind not in ('pilot','health','strength')
                    or (active_kind=='strength' and
                        (active.get('campaign_id')!=STRENGTH_CAMPAIGN_ID
                         or not valid_run_id('strength', active.get('run_id'))))
                    or (active_kind!='strength' and 'campaign_id' in active)):
                raise ValueError('Prior campaign identity or ceiling is invalid')
            active_ceiling = _campaign_seconds(active_kind, active.get('run_id'))
            if active.get('campaign_worker_seconds', active_ceiling) != active_ceiling:
                raise ValueError('Prior campaign identity or ceiling is invalid')
        prior=active.get('charged_campaign_worker_seconds')if active is not None else 0.
        if (type(prior)not in(int,float)or not math.isfinite(prior)or prior<0
                or active is not None and active.get('remaining_campaign_worker_seconds')!=max(0.,active_ceiling-prior)):
            raise ValueError('Prior campaign charges are missing or inconsistent')
        health=active.get('charged_health_worker_seconds',0.)if active is not None else 0.
        if (type(health)not in(int,float)or not math.isfinite(health)or not 0<=health<=prior
                or active is not None and active.get('kind')=='health'and 'charged_health_worker_seconds'not in active
                or active is not None and 'remaining_health_worker_seconds'in active
                   and active['remaining_health_worker_seconds']!=max(0.,30*3600-health)):
            raise ValueError('Prior health charges are missing or inconsistent')
        if kind=='strength':
            rerun=_read(root/'runs'/f'{HEALTH_RERUN_ID}.json')
            if (type(rerun)is not dict or rerun.get('run_id')!=HEALTH_RERUN_ID
                    or rerun.get('kind')!='health' or rerun.get('state')!='closed'
                    or rerun.get('child_handles_reaped')is not True
                    or not is_sha(rerun.get('report_sha256'))
                    or type(rerun.get('charged_campaign_worker_seconds')) not in (int,float)
                    or not 0 < rerun['charged_campaign_worker_seconds'] <= prior
                    or type(rerun.get('charged_health_worker_seconds')) not in (int,float)
                    or not 0 < rerun['charged_health_worker_seconds'] <= health):
                raise ValueError('Strength requires the existing closed health rerun charge history')
        strength=active.get('charged_strength_worker_seconds',0.) if active is not None else 0.
        if (type(strength) not in (int,float) or not math.isfinite(strength)
                or strength<0 or strength+health>prior+.000001
                or (active is not None and active_kind=='strength' and 'charged_strength_worker_seconds' not in active)):
            raise ValueError('Prior strength charges are missing or inconsistent')
        if run_id in STRENGTH_EXTENDED_IDS:
            original = _read(root/'runs'/f'{STRENGTH_RUN_ID}.json')
            if (type(original) is not dict or original.get('kind') != 'strength'
                    or original.get('run_id') != STRENGTH_RUN_ID
                    or original.get('campaign_id') != STRENGTH_CAMPAIGN_ID
                    or original.get('campaign_worker_seconds') != _campaign_seconds('strength', STRENGTH_RUN_ID)
                    or original.get('state') != 'closed' or original.get('child_handles_reaped') is not True
                    or not is_sha(original.get('report_sha256'))
                    or type(original.get('charged_campaign_worker_seconds')) not in (int, float)
                    or not 0 < original['charged_campaign_worker_seconds'] <= prior
                    or type(original.get('charged_strength_worker_seconds')) not in (int, float)
                    or not 0 < original['charged_strength_worker_seconds'] <= strength):
                raise ValueError('Rerun2 requires the existing closed original strength charge history')
        row={'schema':3,'kind':kind,'state':'running','child_handles_reaped':False,'run_id':run_id,
             'plan_sha256':plan_sha256,'revision':revision,'runtime_sha256':runtime_sha256,
             'output':output,'campaign_worker_seconds':_campaign_seconds(kind, run_id),'reserved_health_worker_seconds':30*3600,
             'charged_worker_seconds':None,'remaining_campaign_worker_seconds':None,
             'charged_before_worker_seconds':prior,'charged_campaign_worker_seconds':None,
             'charged_health_before_worker_seconds':health,'charged_health_worker_seconds':None,
             'remaining_health_worker_seconds':None,'health_budget_exceeded':False,
             'report_sha256':None,'pilot_budget_exceeded':False}
        if kind=='strength':
            row['campaign_id']=STRENGTH_CAMPAIGN_ID
        if kind=='strength' or strength:
            row['charged_strength_before_worker_seconds']=strength
            row['charged_strength_worker_seconds']=None
        path=root/'runs'/f'{run_id}.json'
        _write(path,row)  # permanent consumption, even if startup later fails
        _write(root/'active.json',row,replace=True)
        yield Claim(root,path,row)
    finally:
        fcntl.flock(lock,fcntl.LOCK_UN)
        os.close(lock)
