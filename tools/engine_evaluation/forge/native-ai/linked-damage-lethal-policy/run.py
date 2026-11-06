#!/usr/bin/env python3
"""Compile one new diagnostic, run one bounded engine JVM; never alter the prefix."""
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


here = Path(__file__).resolve().parent
identity_path, prefix, out = [Path(value).resolve() for value in sys.argv[1:4]]
candidate = Path(sys.argv[4]).resolve() if len(sys.argv) == 5 else None
repo = here.parents[4]
ancestor = 'fd0fe1dfc77c5d3a647b57b7211c4098385b48cc'
subprocess.run(['git', '-C', str(repo), 'merge-base', '--is-ancestor', ancestor, 'HEAD'], check=True)
actual_head = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
assert sha(identity_path) == 'cf27ccd7a08f1a9433f75da8d399b3e9c87b83b95b17f883ffc4812ee2dfb3d0'
identity = json.loads(identity_path.read_text())
k, jdk, cache = [Path(identity[key]) for key in ('forge', 'jdk', 'cache')]
pin = json.loads((here/'PREFIX-PIN.json').read_text())
assert pin['content_id'] == '3f595b71da5b339b2c9f5f6bced98fb25291db7d55c6427835d52b6d532e38ee'
assert json.loads((prefix.parent/'MANIFEST.json').read_text()) == pin
assert identity['build_id'] == pin['identity']['base_build_id']
assert len(pin['identity']['payloads']) == 8 and len(pin['identity']['sources']) == 6
assert not out.exists()
filesystem = subprocess.check_output(['findmnt', '-T', str(out.parent), '-n', '-o', 'FSTYPE'], text=True)
assert not any(value.startswith(('nfs', 'cifs')) for value in filesystem.splitlines())
out.mkdir(mode=0o700)
for name in ('classes', 'test-source', 'home', 'tmp'):
    (out/name).mkdir(mode=0o700)

inputs = {str(identity_path): sha(identity_path)}
candidate_manifest = None
if candidate:
    candidate_manifest = json.loads((candidate.parent/'MANIFEST.json').read_text())
    layer = candidate_manifest['identity']
    assert layer['parent_content_id'] == pin['content_id'] and layer['base_build_id'] == identity['build_id']
    assert len(layer['sources']) == 1 and len(layer['payloads']) == 1
    assert layer['payloads'][0]['path'] == 'forge/ai/ability/DamageDealAi.class'
    assert [str(p.relative_to(candidate)) for p in candidate.rglob('*') if p.is_file()] == ['forge/ai/ability/DamageDealAi.class']
    for section, root in (('payloads', candidate), ('sources', candidate.parent/'source')):
        for item in layer[section]:
            path = root/item['path']
            assert sha(path) == item['sha256']
            inputs[str(path)] = item['sha256']
    inputs[str(candidate.parent/'MANIFEST.json')] = sha(candidate.parent/'MANIFEST.json')
for item in pin['identity']['payloads']:
    path = prefix/item['path']
    assert sha(path) == item['sha256']
    inputs[str(path)] = item['sha256']
for item in pin['identity']['sources']:
    path = prefix.parent/'source'/item['path']
    assert sha(path) == item['sha256']
    inputs[str(path)] = item['sha256']
assert set(str(p.relative_to(prefix)) for p in prefix.rglob('*.class')) == {
    item['path'] for item in pin['identity']['payloads']}

for path in sorted(here.rglob('*')):
    if path.is_file():
        inputs[str(path)] = sha(path)
for card in (here/'canonical').glob('*.txt'):
    native = k/'forge-gui/res/cardsfolder'/card.name[0]/card.name
    assert native.read_bytes() == card.read_bytes()
    inputs[str(native)] = sha(native)
subprocess.run(['sha256sum', '-c', str(here/'canonical.sha256')], cwd=here,
               check=True, stdout=subprocess.DEVNULL)

# Preserve all original pressure8/chain2 files and old lethal26 source unchanged.
for family in ('sorcery-pressure', 'sorcery-pressure-policy', 'lethal-timing', 'linked-damage-lethal-audit'):
    for path in (here.parent/family).rglob('*'):
        if path.is_file():
            inputs[str(path)] = sha(path)
for relative in ('forge-ai/src/main/java/forge/ai/AiController.java',
                 'forge-ai/src/main/java/forge/ai/SpellAbilityAi.java',
                 'forge-ai/src/main/java/forge/ai/PlayerControllerAi.java',
                 'forge-game/src/main/java/forge/game/player/Player.java',
                 'forge-game/src/main/java/forge/game/spellability/SpellAbility.java',
                 'forge-game/src/main/java/forge/game/zone/Zone.java',
                 'forge-game/src/main/java/forge/game/ability/AbilityUtils.java',
                 'forge-gui-desktop/src/test/java/forge/ai/AITest.java'):
    path = k/relative
    inputs[str(path)] = sha(path)
for entry in identity['runtime_classpath']:
    path = Path(entry)
    assert path.is_dir() or path.suffix == '.jar'
    if path.is_dir():
        for file in path.rglob('*.class'):
            inputs[str(file)] = sha(file)
    else:
        inputs[str(path)] = sha(path)

shutil.copyfile(here/'DECLARATION.json', out/'DECLARATION.json')
source = out/'test-source/NativeLinkedDamagePolicyControls.java'
shutil.copyfile(here/source.name, source)
old = here.parent/'linked-damage-lethal-audit'
assert sha(old/'NativeLinkedDamageLethalAudit.java') == '3b8a7f4884a32600468d70b609a54b7edacb64969dfd902f6200c9bd4ca3384c'
assert sha(old/'DECLARATION.json') == '13ab34686a6b0d8c8227e685183ac7677d83084e79d4bd2d7fb12983090a8d8a'
shutil.copyfile(old/'NativeLinkedDamageLethalAudit.java', out/'test-source/NativeLinkedDamageLethalAudit.java')
shutil.copyfile(old/'DECLARATION.json', out/'OLD-DECLARATION.json')
save(out/'BEFORE.json', {'sha256': inputs, 'base_build_id': identity['build_id'],
                       'prefix_content_id': pin['content_id'], 'candidate': candidate_manifest,
                       'source_ancestor': ancestor, 'actual_source_head': actual_head,
                       'old_checks_unchanged': True})
cp = ':'.join(([str(candidate)] if candidate else []) + [str(prefix)] + identity['runtime_classpath'])
with (out/'compile.log').open('wb') as log:
    subprocess.run([str(jdk/'bin/javac'), '--release', '17', '-implicit:none', '-sourcepath',
                    str(out/'test-source'), '-cp', cp, '-d', str(out/'classes')]
                   + [str(p) for p in sorted((out/'test-source').glob('*.java'))],
                   stdout=log, stderr=log, check=True)
assert [str(p.relative_to(out/'classes')) for p in (out/'classes').rglob('*.class')] and not any(
    str(p.relative_to(out/'classes')).startswith('forge/ai/') for p in (out/'classes').rglob('*.class'))
argv = ['timeout', '-k', '5s', '180', 'strace', '--seccomp-bpf', '-f', '-qq', '-e',
        'trace=network', '-o', str(out/'network.private.strace'), 'bwrap', '--unshare-user',
        '--unshare-net', '--unshare-pid', '--unshare-ipc', '--unshare-uts', '--die-with-parent', '--new-session']
for path in ['/usr', '/lib', '/lib64', '/bin', '/etc', str(cache), str(identity_path.parent), str(prefix)] + ([str(candidate)] if candidate else []):
    argv += ['--ro-bind', path, path]
argv += ['--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp', '--bind', str(out), str(out),
         '--chdir', str(k/'forge-gui-desktop'), '--clearenv', '--setenv', 'PATH', str(jdk/'bin')+':/usr/bin:/bin',
         '--setenv', 'HOME', str(out/'home'), '--setenv', 'LANG', 'C.UTF-8',
         str(jdk/'bin/java'), '-Xmx1500m', '-XX:ActiveProcessorCount=1', '-Djava.awt.headless=true',
         '-Duser.home='+str(out/'home'), '-Djava.io.tmpdir='+str(out/'tmp'), '-Dsentry.dsn=',
         '-Xlog:class+load=info:file='+str(out/'class-load.log')+':uptime,level,tags',
         '--add-opens', 'java.base/java.lang=ALL-UNNAMED', '-cp', str(out/'classes')+':'+cp,
         'forge.evaluation.NativeLinkedDamagePolicyControls', str(out)]
started = time.monotonic()
with (out/'stdout.private.log').open('wb') as stdout, (out/'stderr.private.log').open('wb') as stderr:
    process = subprocess.Popen(argv, stdout=stdout, stderr=stderr, start_new_session=True)
    save(out/'LAUNCH.json', {'pid': process.pid, 'argv': argv})
    print('ENGINE_STARTED pid='+str(process.pid)+' output='+str(out), flush=True)
    code = process.wait()
save(out/'PROCESS-CLOSED.json', {'exit': code, 'seconds': time.monotonic()-started})
assert code in (0, 1), 'Abnormal native process exit; do not rerun blindly'
summary = json.loads((out/'summary.private.json').read_text())
assert len(summary['cases']) == 32
assert sum(row['cohort']=='OLD12-UNMODIFIED-CHECK-METHODS' for row in summary['cases']) == 12
assert sum(row['cohort']=='NEW20-PRESERVATION-CONTROLS' for row in summary['cases']) == 20
assert all(row['default_choice_invocations']==1 for row in summary['cases'])
assert all(sha(Path(path)) == digest for path, digest in inputs.items()), 'Input changed during bounded run'
origins = {}
for line in (out/'class-load.log').read_text().splitlines():
    match = re.search(r'\] (forge\.[\w.$]+) source: file:(.*)$', line)
    if match:
        origins[match[1]] = match[2].rstrip('/')
for name in ('forge.ai.ability.DamageAiBase', 'forge.ai.ability.DamageDealAi',
             'forge.ai.ComputerUtil', 'forge.ai.ComputerUtilMana', 'forge.ai.ComputerUtilCost'):
    assert Path(origins[name]) == (candidate if candidate and name=='forge.ai.ability.DamageDealAi' else prefix)
loaded = {item['class_name']: origins.get(item['class_name'], 'NOT-OBSERVED-LOADED')
          for item in pin['identity']['payloads']}
assert all(value=='NOT-OBSERVED-LOADED' or Path(value)==(candidate if candidate and name=='forge.ai.ability.DamageDealAi' else prefix)
           for name, value in loaded.items())
network = (out/'network.private.strace').read_text()
assert not re.search(r'connect\(.*sa_family=AF_INET6?', network)
assert not re.search(r'TimeoutException|AI eval thread at timeout|AITimeoutTracker\$Expired',
                     (out/'stderr.private.log').read_text())
cohorts = {}
for row in summary['cases']:
    counts = cohorts.setdefault(row['cohort'], {'passed': 0, 'failures': 0})
    counts['passed' if row.get('passed') else 'failures'] += 1
closed = {'status': 'TERMINAL-CONTROLS-ONLY-NO-PROFILE-APP-QUALIFICATION', 'exit': code,
          'seconds': time.monotonic()-started, 'cohorts': cohorts, 'errors': summary['errors'],
          'input_files_before_after_exact': len(inputs), 'loaded_prefix_origins': loaded,
          'one_seed_before_model_only': True, 'declared_ai_choices': 32, 'manual_controls': 0,
          'engine_jvms': 1, 'natural_games': 0, 'candidate_content_id': candidate_manifest['content_id'] if candidate else None,
          'source_ancestor': ancestor, 'actual_source_head': actual_head,
          'unexpected_controls': [row for row in summary['cases'] if not row.get('passed') and
              (candidate or row['cohort']!='OLD12-UNMODIFIED-CHECK-METHODS' or row['scene'] not in ('landfall-stomper', 'nonlandfall-stomper'))]}
save(out/'VERIFIED-CLOSED.json', closed)
print(json.dumps(closed, indent=2), flush=True)
raise SystemExit(code)
