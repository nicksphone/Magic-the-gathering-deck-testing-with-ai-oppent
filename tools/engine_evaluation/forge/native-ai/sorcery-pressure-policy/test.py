#!/usr/bin/env python3
"""Fresh bounded runtime qualification; never changes frozen predecessor verifiers."""
import hashlib
import json
import shutil
import subprocess
import sys
import time
import re
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n')


here = Path(__file__).resolve().parent
identity_path, parent, out = map(lambda value: Path(value).resolve(), sys.argv[1:4])
candidate = Path(sys.argv[4]).resolve() if len(sys.argv) == 5 else None
assert sha(identity_path) == 'cf27ccd7a08f1a9433f75da8d399b3e9c87b83b95b17f883ffc4812ee2dfb3d0'
identity = json.loads(identity_path.read_text())
k, j, cache, q = Path(identity['forge']), Path(identity['jdk']), Path(identity['cache']), identity_path.parent
pin = json.loads((here/'PREFIX-PIN.json').read_text())
assert pin['content_id'] == 'd36d96612e9b770575dd7de4a40b17fce8bccc23ec8dac66002e557d9e7b3d29'
assert json.loads((parent.parent/'MANIFEST.json').read_text()) == pin
for payload in pin['identity']['payloads']:
    assert sha(parent/payload['path']) == payload['sha256']
for listing, base in [('canonical.sha256', here), ('preimages.sha256', here/'preimage'), ('base-sources.sha256', k)]:
    subprocess.run(['sha256sum', '-c', str(here/listing)], cwd=base, check=True, stdout=subprocess.DEVNULL)
for card in (here/'canonical').glob('*.txt'):
    assert card.read_bytes() == (k/'forge-gui/res/cardsfolder'/card.name[0]/card.name).read_bytes()
assert not out.exists()
assert not subprocess.check_output(['findmnt','-T',str(out.parent),'-n','-o','FSTYPE'], text=True).strip().startswith(('nfs','cifs'))
out.mkdir(mode=0o700)
for name in ['classes','test-source','home','tmp']:
    (out/name).mkdir(mode=0o700)
shutil.copyfile(here/'DECLARATION.json',out/'DECLARATION.json')
chain = here.parent/'sorcery-pressure/chain-supplement/NativeSorceryChainControls.java'
lethal = here.parent/'lethal-timing/NativeLethalTimingControls.java'
for path in [here/'NativeSorceryPolicyControls.java',chain,lethal]:
    shutil.copyfile(path,out/'test-source'/path.name)
preserve = {str(path):sha(path) for path in (here.parent/'sorcery-pressure').rglob('*') if path.is_file()}
preserve[str(lethal)] = sha(lethal)
payload_pins = {str(parent/item['path']):item['sha256'] for item in pin['identity']['payloads']}
runtime = ([str(candidate)] if candidate else [])+[str(parent)]+identity['runtime_classpath']
candidate_manifest = None
if candidate:
    candidate_manifest = json.loads((candidate.parent/'MANIFEST.json').read_text())
    assert candidate_manifest['identity']['parent_content_id'] == pin['content_id']
    for item in candidate_manifest['identity']['payloads']:
        assert sha(candidate/item['path']) == item['sha256']
        payload_pins[str(candidate/item['path'])] = item['sha256']
save(out/'BEFORE.json', {'frozen_source_pins':preserve,'payload_pins':payload_pins,'candidate':candidate_manifest,
    'declaration_sha256':sha(here/'DECLARATION.json'),'base_identity_sha256':sha(identity_path),
    'cohort_invocation':'Unmodified private check methods invoked reflectively; one declared seed before all cohorts, no predecessor main or verifier modification.'})
cp = ':'.join(runtime)
with (out/'compile.log').open('wb') as log:
    subprocess.run([str(j/'bin/javac'),'--release','17','-implicit:none','-sourcepath',str(out/'test-source'),
        '-cp',cp,'-d',str(out/'classes')]+[str(path) for path in sorted((out/'test-source').glob('*.java'))],stdout=log,stderr=log,check=True)
argv = ['timeout','-k','5s','180','strace','--seccomp-bpf','-f','-qq','-e','trace=network','-o',str(out/'network.private.strace'),
    'bwrap','--unshare-user','--unshare-net','--unshare-pid','--unshare-ipc','--unshare-uts','--die-with-parent','--new-session']
for path in ['/usr','/lib','/lib64','/bin','/etc',str(cache),str(q),str(parent)]+([str(candidate)] if candidate else []):
    argv += ['--ro-bind',path,path]
argv += ['--proc','/proc','--dev','/dev','--tmpfs','/tmp','--bind',str(out),str(out),'--chdir',str(k/'forge-gui-desktop'),
    '--clearenv','--setenv','PATH',str(j/'bin')+':/usr/bin:/bin','--setenv','HOME',str(out/'home'),'--setenv','LANG','C.UTF-8',
    str(j/'bin/java'),'-Xmx1500m','-XX:ActiveProcessorCount=1','-Djava.awt.headless=true','-Duser.home='+str(out/'home'),
    '-Djava.io.tmpdir='+str(out/'tmp'),'-Dsentry.dsn=', '-Xlog:class+load=info:file='+str(out/'class-load.log')+':uptime,level,tags',
    '--add-opens','java.base/java.lang=ALL-UNNAMED','-cp',str(out/'classes')+':'+cp,
    'forge.evaluation.NativeSorceryPolicyControls',str(out)]
started = time.monotonic()
with (out/'stdout.private.log').open('wb') as stdout,(out/'stderr.private.log').open('wb') as stderr:
    process = subprocess.Popen(argv,stdout=stdout,stderr=stderr,start_new_session=True)
    save(out/'LAUNCH.json',{'pid':process.pid,'argv':argv})
    code = process.wait()
save(out/'PROCESS-CLOSED.json',{'exit':code,'seconds':time.monotonic()-started})
result = json.loads((out/'summary.private.json').read_text())
assert code in [0,1] and result['errors'] == 0
assert all(sha(Path(path)) == digest for path,digest in {**preserve,**payload_pins}.items())
origins = {}
for line in (out/'class-load.log').read_text().splitlines():
    match = re.search(r'\] (forge\.[\w.$]+) source: file:(.*)$',line)
    if match: origins[match[1]] = match[2].rstrip('/')
assert Path(origins['forge.ai.ability.DamageDealAi']) == (candidate or parent)
assert Path(origins['forge.ai.ability.DamageAiBase']) == (candidate or k/'forge-ai/target/classes')
assert Path(origins['forge.ai.ComputerUtilMana']) == parent
assert not re.search(r'connect\(.*sa_family=AF_INET6?',(out/'network.private.strace').read_text())
assert not re.search(r'TimeoutException|AI eval thread at timeout|AITimeoutTracker\$Expired',(out/'stderr.private.log').read_text())
cohorts = {}
unexpected = []
for row in result['cases']:
    counts = cohorts.setdefault(row['cohort'],{'passed':0,'failures':0})
    counts['passed' if row.get('passed') else 'failures'] += 1
    if not row.get('passed') and not (row['cohort']=='unchanged-chain2-check-method' or row.get('scene') in ['pressure1','pressure2','pressure3','axe']):
        unexpected.append(row)
verified = {'exit':code,'seconds':time.monotonic()-started,'cohorts':cohorts,'unexpected_controls':unexpected,
    'errors':result['errors'],'all_frozen_source_and_payload_pins_unchanged':True,
    'native_source_origins':{name:origins[name] for name in ['forge.ai.ability.DamageAiBase','forge.ai.ability.DamageDealAi','forge.ai.ComputerUtilMana']},
    'natural_games':0,'profile_app_qualification':False,'knowledge38_not_run':True}
save(out/'VERIFIED-CLOSED.json',verified)
print(json.dumps(verified,indent=2),flush=True)
raise SystemExit(2 if unexpected else code)
