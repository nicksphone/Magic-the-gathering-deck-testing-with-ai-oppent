"""Cooperative host-local controller exclusion and permanently consumed run IDs."""
from contextlib import contextmanager
import fcntl
import math
import os
from pathlib import Path
import re
import stat

from scripts.archetype_trace_v3 import canonical, is_sha, load_json


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

    def finish(self,*,charged_worker_seconds,report_sha256):
        if (self.finished or type(charged_worker_seconds)not in(int,float)
                or not math.isfinite(charged_worker_seconds)or charged_worker_seconds<0
                or report_sha256 is not None and not is_sha(report_sha256)):
            raise ValueError('Invalid or repeated controller closure')
        cumulative=self.prior_charged_seconds+charged_worker_seconds
        row={**self.record,'state':'closed','child_handles_reaped':True,
             'charged_worker_seconds':charged_worker_seconds,
             'charged_campaign_worker_seconds':cumulative,
             'remaining_campaign_worker_seconds':max(0.,48*3600-cumulative),
             'report_sha256':report_sha256,'pilot_budget_exceeded':cumulative>18*3600}
        _write(self.path,row,replace=True)
        _write(self.root/'active.json',row,replace=True)
        self.finished=True
        return row


@contextmanager
def claim_run(root,*,run_id,plan_sha256,revision,runtime_sha256,output):
    if (type(run_id)is not str or re.fullmatch(r'archetype-pilot-20261116-v3-[A-Za-z0-9-]{1,48}',run_id)is None
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
        prior=active.get('charged_campaign_worker_seconds')if active is not None else 0.
        if (type(prior)not in(int,float)or not math.isfinite(prior)or prior<0
                or active is not None and active.get('remaining_campaign_worker_seconds')!=max(0.,48*3600-prior)):
            raise ValueError('Prior campaign charges are missing or inconsistent')
        row={'schema':3,'state':'running','child_handles_reaped':False,'run_id':run_id,
             'plan_sha256':plan_sha256,'revision':revision,'runtime_sha256':runtime_sha256,
             'output':output,'campaign_worker_seconds':48*3600,'reserved_health_worker_seconds':30*3600,
             'charged_worker_seconds':None,'remaining_campaign_worker_seconds':None,
             'charged_before_worker_seconds':prior,'charged_campaign_worker_seconds':None,
             'report_sha256':None,'pilot_budget_exceeded':False}
        path=root/'runs'/f'{run_id}.json'
        _write(path,row)  # permanent consumption, even if startup later fails
        _write(root/'active.json',row,replace=True)
        yield Claim(root,path,row)
    finally:
        fcntl.flock(lock,fcntl.LOCK_UN)
        os.close(lock)
