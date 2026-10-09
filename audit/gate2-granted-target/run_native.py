"""Bounded whole NEW modules; native Python controls, not an OS sandbox."""
import sys
import hashlib
import json
import os
from pathlib import Path
import signal
import random
import threading
import time

ROOT = Path(__file__).resolve().parent
MODE = sys.argv[1]
SOURCE = Path(os.environ.get("MTG_AUDIT_SOURCE", ROOT.parents[1])).resolve()
E = Path(sys.argv[2]).resolve()
assert not E.is_relative_to(SOURCE) and not E.is_relative_to(Path(sys.prefix).resolve())
SOURCE_PINS = Path(sys.argv[3]).resolve()
RUNTIME_PINS = Path(sys.argv[4]).resolve()
RUNTIME_MANIFEST = Path(sys.argv[5]).resolve()
MODULES = {
    "composed265": ([
        "test_granted_target_producers.py",
        "test_granted_target_diagnostics.py",
        "test_granted_target_publication.py",
        "test_granted_target_boundary.py",
        "../../gate2-granted-target-AI/test_ai_granted_equip.py",
        "../../gate2-granted-target-AI/test_ai_granted_forecast.py",
        "../../gate2-granted-target-AI/test_ai_granted_rollout.py",
        "../../gate2-granted-target-AI/test_ai_simulation_frontier.py",
        "../../../backend/tests/test_equip_context.py",
        "../../../backend/tests/test_attachments.py",
        "../../../backend/tests/test_ai_pending_counter_gain.py",
        "../../../backend/tests/test_ai_stack_response_delta.py",
        "../../../backend/tests/test_ai_deferred_forecast_scores.py",
        "../../../backend/tests/test_ai_opaque_draw_horizon.py",
    ], 265),
    "composed140": (["test_granted_target_producers.py", "test_granted_target_diagnostics.py", "test_granted_target_publication.py", "../../gate2-granted-target-AI/test_ai_granted_equip.py", "../../gate2-granted-target-AI/test_ai_granted_forecast.py", "../../../backend/tests/test_equip_context.py", "../../../backend/tests/test_attachments.py"], 140),
    "boundary56": (["test_granted_target_producers.py", "test_granted_target_diagnostics.py", "test_granted_target_publication.py"], 56),
    "paid24-original": (["test_paid_nadu.py"], 24),
    "paid24-qualified": (["test_paid_nadu.py"], 24),
    "compiler33": (["test_granted_target_boundary.py"], 33),
    "incarnation4": (["test_paid_nadu_incarnation_witnesses.py"], 4),
}
assert MODE in MODULES
assert E.is_dir() and {p.name for p in E.iterdir()} <= {'stdout.log'}
assert sys.dont_write_bytecode and sys.flags.optimize == 0
CAP, FLOOR = 16*1024**2, 3*1024**3
assert os.statvfs(E).f_bavail*os.statvfs(E).f_frsize > FLOOR+128*1024**2
assert sys.version_info[:3] == (3, 12, 3)
START = time.monotonic()

def save(name, value):
    data = json.dumps(value, indent=2, sort_keys=True).encode()+b'\n'
    assert sum(p.stat().st_size for p in E.rglob('*') if p.is_file())+len(data)+1024**2 <= CAP
    assert os.statvfs(ROOT).f_bavail*os.statvfs(ROOT).f_frsize >= FLOOR
    with (E/name).open('xb') as stream:
        stream.write(data)

def hashes(directory):
    return {str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in directory.rglob('*') if p.is_file() and not p.is_symlink()
            and '__pycache__' not in p.parts and p.suffix!='.pyc'}

def runtime():
    prefix = Path(sys.prefix).resolve()
    assert sys.prefix != sys.base_prefix
    assert sys.prefix == str(prefix)
    manifest = json.loads(RUNTIME_MANIFEST.read_bytes())
    full = hashes(prefix)
    assert len(full)==2037 and full==json.loads(RUNTIME_PINS.read_bytes())
    nonpip = {k:v for k,v in full.items() if not k.startswith(
        ('lib/python3.12/site-packages/pip/', 'lib/python3.12/site-packages/pip-'))}
    assert len(nonpip)==1558 and nonpip==manifest['nonpip']
    links = {k:os.readlink(prefix/k.removeprefix("venv/")) for k in manifest['symlink_targets'] if k.startswith('venv/')}
    assert links=={k:v for k,v in manifest['symlink_targets'].items() if k.startswith('venv/')}
    from importlib.metadata import version
    return {'sys_prefix':sys.prefix, 'executable':sys.executable, 'full':full,
        'nonpip':nonpip, 'full_count':len(full), 'nonpip_count':len(nonpip),
        'links':links, 'versions':{k:version(k) for k in ('pip','pytest','fastapi','starlette','sqlmodel','pydantic')}}

denied = []
class Denied(PermissionError):
    pass
def audit(event, args):
    blocked = event.startswith(('sqlite3.', 'socket.')) or event in {
        'subprocess.Popen','os.system','os.fork','os.forkpty','os.posix_spawn','os.exec','pty.spawn'}
    if event=='open' and len(args)>2 and isinstance(args[2],int) and args[2] & (
            os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):
        blocked = not Path(os.fspath(args[0])).resolve().is_relative_to(E)
    if event in {'os.remove','os.rmdir','os.mkdir','os.rename','os.link','os.symlink','os.truncate'}:
        operand = Path(os.fspath(args[0])).resolve()
        existing_directory_probe = event=='os.mkdir' and operand.is_dir() and operand.is_relative_to(SOURCE)
        blocked = blocked or (not operand.is_relative_to(E) and not existing_directory_probe)
        if event=='os.rename':
            blocked = blocked or not Path(os.fspath(args[1])).resolve().is_relative_to(E)
    if blocked:
        denied.append({'event':event,'operand':str(args[0]) if args else None})
        raise Denied(event)
sys.addaudithook(audit)

signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('300s total wall bound')))
signal.alarm(300)
import _sqlite3
import sqlite3
import _socket
import subprocess
for operation in (lambda:_sqlite3.connect(str(E/'denied.db')), lambda:sqlite3.connect(':memory:'),
                  lambda:_socket.socket(), lambda:subprocess.run(['true'])):
    try:
        operation()
    except Denied:
        pass
    else:
        raise AssertionError('Native canary escaped')
assert len(denied)==4 and not (E/'denied.db').exists()
save('native-precollection.json', {'pid':os.getpid(),'denied':denied[:],'app_imports_at_probe':[]})
before = hashes(SOURCE)
assert before==json.loads(SOURCE_PINS.read_bytes())
assert not list(SOURCE.rglob('*.db')) and not any(p.is_symlink() for p in SOURCE.rglob('*'))
save('source-before.json', before)
test_pins = {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [*ROOT.glob('*.py'),*ROOT.glob('*.json'),*(ROOT/'tests').glob('*.py')]}
save('test-inputs-before.json',test_pins)
rb = runtime()
save('runtime-before.json', rb)
paths = ['backend','audit/complete-body/tests','audit/complete-body/gap6','audit/gate2-domain-compiler','audit/gate2-suncleanser']
sys.path[:0] = [str(ROOT),str(ROOT/'tests'),*[str(SOURCE/p) for p in paths]]
os.environ['ADMISSION_PHASE']='gap6'
os.environ['GAP6_EVIDENCE']=str(E)
os.environ['NADU_EVIDENCE']=str(E)
os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1'
os.environ['TMPDIR']=str(E)
os.chdir(ROOT)

seed = json.loads((SOURCE/'backend/card_data/builtin_oracle_seed.json').read_bytes())['cards']
assert len(seed)==155
save('seed155-before.json', seed)
import pytest
# Unchanged archive omits generated media: redirect only disposable output, never Oracle or game functions.
import card_data.placeholders
import card_data.sync
import card_data.token_images
card_data.placeholders.CACHE_DIR = E/'media'
card_data.sync.CACHE_DIR = E/'media'
card_data.token_images.CACHE_DIR = E/'media'
card_data.token_images._INDEX_FILE = E/'media'/'token-index.json'
baseline_rng = random.getstate()
baseline_threads = [t.name for t in threading.enumerate()]
def fds():
    result={}
    for p in Path('/proc/self/fd').iterdir():
        try:result[p.name]=os.readlink(p)
        except FileNotFoundError:pass
    return result
baseline_fds = fds()

class Ledger:
    def __init__(self):self.rows=[]
    def pytest_collection_finish(self, session):
        save('collection.json', {'nodes':[i.nodeid for i in session.items], 'count':len(session.items),'no_filters':True})
        assert len(session.items)==MODULES[MODE][1]
        assert not any(i.get_closest_marker('skip') for i in session.items)
        if MODE=='paid24-qualified':
            expected=json.loads((ROOT/'paid24-reentry-node-seeds.json').read_bytes())
            nodes={'tests/'+i.path.name+'::'+i.nodeid.split('::',1)[1] for i in session.items}
            assert set(expected)==nodes
            save('effective-seed-table.json',expected)
    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_call(self, item):
        if MODE=='paid24-qualified' and item.callspec.params['case']=='new_incarnation':
            from copy import deepcopy
            from unittest.mock import patch
            import nadu_support
            seat=item.callspec.params['seat']
            inputs=json.loads((ROOT/'paid24-reentry-inputs.json').read_bytes())
            assert inputs['recipe']==nadu_support.WITNESSES['recipe']
            qualified=deepcopy(nadu_support.WITNESSES)
            qualified['witnesses'][f'{seat}-land']=inputs['witnesses'][str(seat)]
            with patch.object(nadu_support,'WITNESSES',qualified):yield
        else:yield
    def pytest_runtest_logreport(self, report):
        self.rows.append({'node':report.nodeid,'phase':report.when,'outcome':report.outcome,
                          'duration':report.duration,'trace':str(report.longrepr) if report.failed else None})

ledger=Ledger()
exit_code=126
try:
    exit_code=pytest.main(['-vv','--tb=long','-p','no:cacheprovider','--capture=sys',
        '-o','log_file='+str(E/'pytest.log'),
        '--basetemp='+str(E/'pytest-tmp'), '--junitxml='+str(E/'junit.xml'), *[str(ROOT/"tests"/module) for module in MODULES[MODE][0]]], plugins=[ledger])
finally:
    save('pytest-ledger.json', ledger.rows)
    after=hashes(SOURCE)
    save('source-after.json', after)
    after_test_pins={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in test_pins}
    save('test-inputs-after.json',after_test_pins)
    assert test_pins==after_test_pins
    ra=runtime()
    save('runtime-after.json', ra)
    seed_after=json.loads((SOURCE/'backend/card_data/builtin_oracle_seed.json').read_bytes())['cards']
    save('seed155-after.json', seed_after)
    imports={}
    foreign=[]
    for name,module in tuple(sys.modules.items()):
        path=getattr(module,'__file__',None)
        if path:
            path=Path(path).resolve()
            if path.is_relative_to(SOURCE):
                relative=str(path.relative_to(SOURCE))
                imports[name]={'path':relative,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
                assert imports[name]['sha256']==before[relative]
            elif name.split('.')[0] in {'rules_engine','game_state','effects','card_data','decks','scripts'}:
                foreign.append({'module':name,'path':str(path)})
    closure={'pytest_exit':int(exit_code), 'wall_seconds':time.monotonic()-START,
        'source_exact':before==after,'runtime_exact':rb==ra,'seed155_exact':seed==seed_after,
        'rng_exact':baseline_rng==random.getstate(),'threads_before':baseline_threads,
        'threads_after':[t.name for t in threading.enumerate()], 'fds_before':baseline_fds,'fds_after':fds(),
        'owned_imports':imports,'foreign_imports':foreign,'denied':denied,
        'database_absent':not list(SOURCE.rglob('*.db')), 'cap_bytes':CAP, 'floor_bytes':FLOOR, 'guard_scope':'process-native SQL/socket/child denial and owned-file writes, not OS sandbox', 'fixture_SQL_attempts_denied':sum(row['event'].startswith('sqlite3.') for row in denied[4:]), 'owned_media_cache':str(E/'media')}
    save('closure.json', closure)
    assert before==after and rb==ra and seed==seed_after and not foreign
    assert closure['rng_exact'] and closure['threads_before']==closure['threads_after']
    assert closure['fds_before']==closure['fds_after'] and len(denied)==4 and closure['database_absent']
    signal.alarm(0)
sys.exit(exit_code)
