#!/usr/bin/env python3
"""Build exactly one copied native source/class over the immutable eight-class parent."""
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


here = Path(__file__).resolve().parent
identity_path, parent, out = [Path(value).resolve() for value in sys.argv[1:]]
assert sha(identity_path) == 'cf27ccd7a08f1a9433f75da8d399b3e9c87b83b95b17f883ffc4812ee2dfb3d0'
base = json.loads(identity_path.read_text())
pin = json.loads((here/'PREFIX-PIN.json').read_text())
assert pin['content_id'] == '3f595b71da5b339b2c9f5f6bced98fb25291db7d55c6427835d52b6d532e38ee'
assert json.loads((parent.parent/'MANIFEST.json').read_text()) == pin
assert base['build_id'] == pin['identity']['base_build_id']
relative = Path('forge-ai/src/main/java/forge/ai/ability/DamageDealAi.java')
assert sha(here/'preimage/DamageDealAi.java') == 'bac01d37456a32978a406fc5875ab5f5ab0305461bcdb1f157916589ca73a129'
assert (here/'preimage/DamageDealAi.java').read_bytes() == (parent.parent/'source'/relative).read_bytes()
assert len(pin['identity']['payloads']) == 8 and len(pin['identity']['sources']) == 6
inputs = {str(identity_path): sha(identity_path)}
for section, root in (('payloads', parent), ('sources', parent.parent/'source')):
    for item in pin['identity'][section]:
        path = root/item['path']
        assert sha(path) == item['sha256']
        inputs[str(path)] = item['sha256']
for path in here.rglob('*'):
    if path.is_file():
        inputs[str(path)] = sha(path)
assert not out.exists()
filesystems = subprocess.check_output(['findmnt', '-T', str(out.parent), '-n', '-o', 'FSTYPE'], text=True)
assert not any(value.startswith(('nfs', 'cifs')) for value in filesystems.splitlines())
repo = here.parents[4]
ancestor = 'fd0fe1dfc77c5d3a647b57b7211c4098385b48cc'
subprocess.run(['git', '-C', str(repo), 'merge-base', '--is-ancestor', ancestor, 'HEAD'], check=True)
actual_head = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
patch = (here/'linked-child-lethal.patch').read_bytes()
headers = re.findall(rb'^(?:---|\+\+\+) ([^\t\r\n]+)', patch, re.M)
assert headers == [('a/'+str(relative)).encode(), ('b/'+str(relative)).encode()]
out.mkdir(mode=0o700)
for directory in ('source', 'shadow', 'inputs'):
    (out/directory).mkdir(mode=0o700)
(out/'source'/relative.parent).mkdir(parents=True)
shutil.copyfile(here/'preimage/DamageDealAi.java', out/'source'/relative)
for name in ('build.py', 'linked-child-lethal.patch', 'PREFIX-PIN.json', 'preimages.sha256', 'LICENSE', 'NOTICE.md'):
    shutil.copyfile(here/name, out/'inputs'/name)
with (out/'patch.log').open('wb') as log:
    subprocess.run(['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-d', str(out/'source')],
                   input=patch, stdout=log, stderr=log, check=True)
assert not re.search(r'fuzz|offset', (out/'patch.log').read_text(), re.I)
assert (out/'source'/relative).read_bytes() == (here/'source'/relative).read_bytes()
assert [str(p.relative_to(out/'source')) for p in (out/'source').rglob('*') if p.is_file()] == [str(relative)]
jdk = Path(base['jdk'])
cp = ':'.join([str(parent)] + base['runtime_classpath'])
with (out/'compile.log').open('wb') as log:
    subprocess.run([str(jdk/'bin/javac'), '--release', '17', '-implicit:none', '-sourcepath',
                    str(out/'source'), '-cp', cp, '-d', str(out/'shadow'), str(out/'source'/relative)],
                   stdout=log, stderr=log, check=True)
payloads = sorted(str(p.relative_to(out/'shadow')) for p in (out/'shadow').rglob('*') if p.is_file())
assert payloads == ['forge/ai/ability/DamageDealAi.class']
assert all(sha(Path(path)) == digest for path, digest in inputs.items()), 'Build inputs changed'
identity = {'schema': 'forge-linked-damage-lethal-one-class-v1', 'base_build_id': base['build_id'],
            'base_identity_sha256': sha(identity_path), 'parent_content_id': pin['content_id'],
            'required_base_launch_sha256': pin['identity']['required_base_launch_sha256'],
            'ancestor_source_commit': ancestor, 'builder_sha256': sha(here/'build.py'),
            'patch_sha256': sha(here/'linked-child-lethal.patch'),
            'preimage_sha256': sha(here/'preimage/DamageDealAi.java'),
            'license_sha256': sha(here/'LICENSE'),
            'sources': [{'path': str(relative), 'sha256': sha(out/'source'/relative)}],
            'payloads': [{'path': p, 'class_name': 'forge.ai.ability.DamageDealAi',
                          'sha256': sha(out/'shadow'/p)} for p in payloads],
            'jdk_inputs': {name: sha(jdk/name) for name in ('bin/java', 'bin/javac', 'release')}}
content_id = hashlib.sha256((json.dumps(identity, sort_keys=True, separators=(',', ':'))+'\n').encode()).hexdigest()
manifest = {'content_id': content_id, 'identity': identity, 'actual_source_head': actual_head,
            'scope': 'One DGAI override; no Draw layer, parent profile or application qualification.'}
(out/'MANIFEST.json').write_text(json.dumps(manifest, indent=2)+'\n')
(out/'CONTENT-ID.txt').write_text(content_id+'\n')
(out/'INPUT-PINS.json').write_text(json.dumps(inputs, indent=2)+'\n')
print(json.dumps(manifest, indent=2), flush=True)
