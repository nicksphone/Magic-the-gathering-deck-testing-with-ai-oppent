#!/usr/bin/env python3
"""Build a separate two-class layer, never the parent's composed profile."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


here = Path(__file__).resolve().parent
identity_path, parent, out = map(lambda value: Path(value).resolve(), sys.argv[1:])
assert sha(identity_path) == 'cf27ccd7a08f1a9433f75da8d399b3e9c87b83b95b17f883ffc4812ee2dfb3d0'
base = json.loads(identity_path.read_text())
pin = json.loads((here/'PREFIX-PIN.json').read_text())
assert json.loads((parent.parent/'MANIFEST.json').read_text()) == pin
assert pin['content_id'] == 'd36d96612e9b770575dd7de4a40b17fce8bccc23ec8dac66002e557d9e7b3d29'
for item in pin['identity']['payloads']:
    assert sha(parent/item['path']) == item['sha256']
subprocess.run(['sha256sum','-c',str(here/'preimages.sha256')],cwd=here/'preimage',check=True,stdout=subprocess.DEVNULL)
assert not out.exists()
assert not subprocess.check_output(['findmnt','-T',str(out.parent),'-n','-o','FSTYPE'],text=True).strip().startswith(('nfs','cifs'))
out.mkdir(mode=0o700)
for name in ['source','shadow','inputs']:
    (out/name).mkdir(mode=0o700)
rel = Path('forge-ai/src/main/java/forge/ai/ability')
(out/'source'/rel).mkdir(parents=True)
for name in ['DamageAiBase.java','DamageDealAi.java']:
    shutil.copyfile(here/'preimage'/name,out/'source'/rel/name)
for name in ['pressure-fallback.patch','build.py','PREFIX-PIN.json','preimages.sha256']:
    shutil.copyfile(here/name,out/'inputs'/name)
with (out/'patch.log').open('wb') as log:
    subprocess.run(['patch','--batch','--forward','--fuzz=0','-p1','-d',str(out/'source')],
        input=(here/'pressure-fallback.patch').read_bytes(),stdout=log,stderr=log,check=True)
for name in ['DamageAiBase.java','DamageDealAi.java']:
    assert (out/'source'/rel/name).read_bytes() == (here/'source'/rel/name).read_bytes()
j = Path(base['jdk'])
cp = ':'.join([str(parent)]+base['runtime_classpath'])
with (out/'compile.log').open('wb') as log:
    subprocess.run([str(j/'bin/javac'),'--release','17','-implicit:none','-sourcepath',str(out/'source'),
        '-cp',cp,'-d',str(out/'shadow')]+[str(out/'source'/rel/name) for name in ['DamageAiBase.java','DamageDealAi.java']],
        stdout=log,stderr=log,check=True)
paths = sorted(str(path.relative_to(out/'shadow')) for path in (out/'shadow').rglob('*') if path.is_file())
assert paths == ['forge/ai/ability/DamageAiBase.class','forge/ai/ability/DamageDealAi.class']
identity = {'schema':'forge-fallback-sorcery-pressure-layer-v1','base_build_id':base['build_id'],
    'base_identity_sha256':sha(identity_path),'parent_content_id':pin['content_id'],
    'required_base_launch_sha256':pin['identity']['required_base_launch_sha256'],
    'builder_sha256':sha(here/'build.py'),'patch_sha256':sha(here/'pressure-fallback.patch'),
    'sources':[{'path':str(rel/name),'sha256':sha(out/'source'/rel/name)} for name in ['DamageAiBase.java','DamageDealAi.java']],
    'payloads':[{'path':path,'sha256':sha(out/'shadow'/path)} for path in paths],
    'jdk_inputs':{name:sha(j/name) for name in ['bin/java','bin/javac','release']}}
content_id = hashlib.sha256((json.dumps(identity,sort_keys=True,separators=(',',':'))+'\n').encode()).hexdigest()
(out/'MANIFEST.json').write_text(json.dumps({'content_id':content_id,'identity':identity,
    'scope':'Two-class override only; parent owns eight-class composition/profile/app approval.'},indent=2)+'\n')
(out/'CONTENT-ID.txt').write_text(content_id+'\n')
print(json.dumps({'content_id':content_id,'sources':identity['sources'],'payloads':identity['payloads']},indent=2))
