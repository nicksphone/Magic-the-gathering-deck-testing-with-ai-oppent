"""Serial owned dependency qualification. Native installer children are not an OS sandbox."""
import ast,hashlib,json,os,resource,shutil,signal,subprocess,sys,time,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from live_size import live_size
D=Path(__file__).resolve().parents[1];S=D/'source';E=D/'evidence';V=Path('/home/nick/.local/share/mtg-deck-testing-lab/runtimes/app-py312-certifi20261019-20261021-iMMqrycK/venv');P=V/'bin/python'
assert json.loads((D/'ACTIVATION.json').read_text())['build'] is True, 'Inactive build candidate'
bindings=json.loads((D/'BINDINGS.json').read_text())
node_exe=Path(bindings['Node']['path']);npm_cli=Path(bindings['npm_cli'])
assert hashlib.sha256(node_exe.read_bytes()).hexdigest()==bindings['Node']['sha256']
assert bindings['npm_cli_sha256'] and hashlib.sha256(npm_cli.read_bytes()).hexdigest()==bindings['npm_cli_sha256']
LIMIT=1024**3;FLOOR=3*1024**3;identities={};OUT=None;_OWNED_FAMILIES={}
# Reuse the previously reviewed identity/scoped-process observer, not new app instrumentation.
assert bindings['process_observer_source'] and bindings['process_observer_sha256'], 'Exact observer dependency unbound'
observer=Path(bindings['process_observer_source']).read_bytes()
assert hashlib.sha256(observer).hexdigest()==bindings['process_observer_sha256']
tree=ast.parse(observer)
for name in ('identity','known_birth','owned_group','record'):
 node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
 exec(compile(ast.Module(body=[node],type_ignores=[]),'reviewed-process-observer','exec'))
env={'PATH':str(node_exe.parent)+':/usr/bin:/bin','HOME':str(D/'home'),'TMPDIR':str(D/'tmp'),'LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1','NODE_OPTIONS':'--max-old-space-size=768','GOMAXPROCS':'2','npm_config_registry':'https://registry.npmjs.org/','npm_config_userconfig':str(D/'home/npm-user.conf'),'npm_config_globalconfig':str(D/'home/npm-global.conf'),'npm_config_cache':str(D/'npm-cache'),'npm_config_update_notifier':'false','npm_config_fund':'false','MTG_TEST_PYTHON':str(P),
 'GIT_DIR':bindings['Git']['dir'],'GIT_WORK_TREE':str(S),
 'GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_SYSTEM':'/dev/null','GIT_CONFIG_GLOBAL':'/dev/null',
 'GIT_NO_REPLACE_OBJECTS':'1','GIT_NO_LAZY_FETCH':'1','GIT_OPTIONAL_LOCKS':'0','GIT_TERMINAL_PROMPT':'0',
 'GIT_CONFIG_COUNT':'4','GIT_CONFIG_KEY_0':'core.hooksPath','GIT_CONFIG_VALUE_0':'/dev/null',
 'GIT_CONFIG_KEY_1':'protocol.allow','GIT_CONFIG_VALUE_1':'never',
 'GIT_CONFIG_KEY_2':'gc.auto','GIT_CONFIG_VALUE_2':'0',
 'GIT_CONFIG_KEY_3':'maintenance.auto','GIT_CONFIG_VALUE_3':'false'}
(E/'DECLARED-ENV.json').write_text(json.dumps(env,indent=2)+'\n')
pins=json.loads((E/'SOURCE-PLAN-PINS.json').read_text())['regular'];h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert shutil.disk_usage(D).free>=5*1024**3
assert V.is_dir() and not(S/'frontend/node_modules').exists() and not(S/'frontend/dist').exists()
assert all(h(S/k)==v for k,v in pins.items())
def bounds():
 size=live_size(D,live=True)
 assert size<=LIMIT,('root cap',size);assert shutil.disk_usage(D).free>=FLOOR
 return size
def restricted():resource.setrlimit(resource.RLIMIT_FSIZE,(128*1024**2,128*1024**2))
def stage(name,args,seconds=180,acceptable=(0,)):
 global OUT,identities
 OUT=E/name;OUT.mkdir();identities={};proc=None;failure=None;start=time.monotonic()
 command=['/usr/bin/timeout','--signal=TERM','--kill-after=15s',str(seconds)+'s',*map(str,args)]
 (OUT/'command.json').write_text(json.dumps({'argv':command,'env':env},indent=2)+'\n')
 (OUT/'start.utc').write_text(time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())+'\n')
 try:
  with (OUT/'stdout.log').open('wb') as out,(OUT/'stderr.log').open('wb') as err:
   proc=subprocess.Popen(command,env=env,cwd=D,stdout=out,stderr=err,start_new_session=True,preexec_fn=restricted)
   leader=identity(proc.pid);assert leader['pgid']==proc.pid;identities[proc.pid]=leader;record('leader',**leader,requested_argv=command)
   while proc.poll() is None:
    for pid,i in owned_group(proc.pid).items():
     if pid in identities:assert identities[pid]==i
     else:
      identities[pid]=i
      try:argv=Path(f'/proc/{pid}/cmdline').read_bytes().decode(errors='replace').split('\0')
      except FileNotFoundError:argv=['exited before sampled argv']
      record('owned_child',**i,sampled_argv=argv,stage_requested_argv=command)
    bounds();assert time.monotonic()-start<seconds+20
    time.sleep(.1)
 except BaseException:
  failure=traceback.format_exc();record('observer_failure',traceback=failure)
 finally:
  if proc is not None:
   if proc.poll() is None:
    assert identity(proc.pid)==identities[proc.pid];os.killpg(proc.pid,signal.SIGTERM)
    try:proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
     assert identity(proc.pid)==identities[proc.pid];os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=5)
   deadline=time.monotonic()+5
   while owned_group(proc.pid) and time.monotonic()<deadline:time.sleep(.05)
   r={'actual_cli_rc':proc.returncode,'seconds':round(time.monotonic()-start,3),'failure':failure,'identities':identities,'group_empty':not owned_group(proc.pid),'root_bytes':bounds(),'free_bytes':shutil.disk_usage(D).free,'scope':'sampled process identities/argv; no complete FD visibility or OS SQL/network sandbox'}
   (OUT/'terminal.json').write_text(json.dumps(r,indent=2)+'\n')
   (OUT/'end.utc').write_text(time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())+'\n')
   print(name,proc.returncode,flush=True)
 assert proc and not failure and proc.returncode in acceptable and not owned_group(proc.pid),name
 return OUT
# Fresh locked frontend install only; no Python install or duplicate advisory queries.
npm=[str(node_exe),str(npm_cli)]
stage('frontend-npm-ci',[*npm,'--prefix',S/'frontend','ci','--no-fund','--no-audit'],300)
# Full dependency profile before gates; all generated differences remain explicit.
def profile(root):return {str(p.relative_to(root)):{'symlink':os.readlink(p)} if p.is_symlink() else {'sha256':h(p),'bytes':p.stat().st_size} for p in root.rglob('*') if p.is_file() or p.is_symlink()}
deps_before=profile(S/'frontend/node_modules');(E/'FRONTEND-DEPS-BEFORE-GATES.json').write_text(json.dumps(deps_before,indent=2)+'\n')
stage('frontend-type',[node_exe,S/'frontend/node_modules/typescript/bin/tsc','--project',S/'frontend/tsconfig.json','--noEmit'])
stage('frontend-lint',[*npm,'--prefix',S/'frontend','run','lint'])
stage('frontend-full-test',[*npm,'--prefix',S/'frontend','test'])
stage('frontend-build',[*npm,'--prefix',S/'frontend','run','build'])
assert (S/'frontend/dist/index.html').is_file()
dist=profile(S/'frontend/dist');assert dist
(E/'FRESH-DIST-PINS.json').write_text(json.dumps(dist,indent=2)+'\n')
assert all(h(S/k)==v for k,v in pins.items());assert not(S/'backend/mtg_lab.db').exists()
after=profile(S/'frontend/node_modules');delta={'added':sorted(after.keys()-deps_before.keys()),'removed':sorted(deps_before.keys()-after.keys()),'changed':[k for k in after.keys()&deps_before.keys() if after[k]!=deps_before[k]]}
(E/'FRONTEND-DEPS-AFTER-GATES.json').write_text(json.dumps(after,indent=2)+'\n');(E/'DEPENDENCY-GENERATED-DELTA.json').write_text(json.dumps(delta,indent=2)+'\n')
r={'source_files_equal':len(pins),'default_DB_absent':True,'fresh_npm_ci_not_retainedcache':True,'AppF_reused_readonly_not_fresh_install':True,'root_bytes':bounds(),'free_bytes':shutil.disk_usage(D).free,'dependency_delta':delta,'stages':[json.loads(p.read_text()) for p in sorted(E.glob('*/terminal.json'))]}
(E/'TERMINAL.json').write_text(json.dumps(r,indent=2)+'\n');print('PIPELINE_TERMINAL0',flush=True)
