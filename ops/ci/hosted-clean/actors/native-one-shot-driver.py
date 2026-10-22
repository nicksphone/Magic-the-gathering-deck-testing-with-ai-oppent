"""Owned one-shot resource monitor; no product or reviewed-control changes."""
import datetime,json,os,signal,subprocess,time
from pathlib import Path
H=Path(__file__).resolve().parents[1];N=Path('/home/nick/.local/share/mtg-deck-testing-lab/runtimes/app-py312-certifi20261019-20261021-iMMqrycK');E=H/'evidence'
assert json.loads((H/'ACTIVATION.json').read_text())['https'] is True, 'Inactive HTTPS candidate'
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def identity(pid):
 f=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
 return {'pid':pid,'start_ticks':f[19],'pgid':int(f[2])}
def size(root):
 total=0
 for p in root.rglob('*'):
  try:
   if p.is_file() and not p.is_symlink():total+=p.stat().st_size
  except FileNotFoundError:pass
 return total
assert not (E/'one-shot-driver.exit').exists()
env={'PATH':'/usr/bin:/bin','HOME':str(H),'LANG':'C.UTF-8','MTG_CADDY_SQL_LEASE':'parent-explicit','PYTHONDONTWRITEBYTECODE':'1'}
command=['timeout','--signal=TERM','--kill-after=15s','900s',str(N/'venv/bin/python'),str(H/'gate-review/client-gate.py'),'--execute-reviewed-gate']
with (E/'one-shot-driver.log').open('xb') as log:
 process=subprocess.Popen(command,env=env,stdout=log,stderr=log,start_new_session=True)
 outer=identity(process.pid);assert outer['pgid']==process.pid
 receipt={'utc':utc(),'driver':identity(os.getpid()),'outer':outer,'children':[],'command':command,'bounded_seconds':900,'kill_after_seconds':15,'client_alarm_seconds':800}
 (E/'one-shot-start.json').write_text(json.dumps(receipt,indent=2)+'\n');print('ONE-SHOT START outerPID='+str(process.pid),flush=True)
 seen={};stop_reason=None;maximum=0;minimum_free=None
 with (E/'resource-monitor.jsonl').open('x') as monitor:
  while process.poll() is None:
   try:
    for value in Path(f'/proc/{process.pid}/task/{process.pid}/children').read_text().split():
     pid=int(value);seen[pid]=identity(pid)
   except FileNotFoundError:pass
   combined=size(H)+size(N);output=size(E/'runtime-gate')+log.tell()
   free=os.statvfs('/tmp').f_bavail*os.statvfs('/tmp').f_frsize
   maximum=max(maximum,combined);minimum_free=free if minimum_free is None else min(minimum_free,free)
   monitor.write(json.dumps({'utc':utc(),'combined_logical_bytes':combined,'runtime_output_bytes':output,'free_bytes':free})+'\n');monitor.flush()
   if combined>1024**3 or output>512*1024**2 or free<3*1024**3:
    stop_reason='resource_bound'
    if identity(process.pid)!=outer:raise RuntimeError('Owned outer identity mismatch; not signalled')
    os.killpg(process.pid,signal.SIGTERM);break
   time.sleep(.5)
  code=process.wait(timeout=915)
 receipt.update(end_utc=utc(),outer_exit=code,children=list(seen.values()),resource_stop_reason=stop_reason,maximum_combined_bytes=maximum,minimum_free_bytes=minimum_free)
 (E/'one-shot-terminal.json').write_text(json.dumps(receipt,indent=2)+'\n');(E/'one-shot-driver.exit').write_text(str(code)+'\n')
 print('ONE-SHOT TERMINAL exit='+str(code),flush=True)
 raise SystemExit(code if not stop_reason else 1)
