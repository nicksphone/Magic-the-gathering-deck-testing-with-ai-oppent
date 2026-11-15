#!/usr/bin/env python3
"""Compile only ComputerUtil, compose a fresh prefix, never modify qualified inputs."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
BASE = '0c04d1b1435472432cfb377db47595ca3b3ff76c18eeb6d6db57ec4f076f8ef1'
SOURCE = 'forge-ai/src/main/java/forge/ai/ComputerUtil.java'
PAYLOAD = 'forge/ai/ComputerUtil.class'
POST_SHA = '257cb44971161566ea23296c179e7728827a96f5f63ffa339fcf5ad61ba055ff'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    identity_path, parent, out = (Path(value).resolve() for value in sys.argv[1:])
    assert sha(identity_path) == 'cf27ccd7a08f1a9433f75da8d399b3e9c87b83b95b17f883ffc4812ee2dfb3d0'
    identity = json.loads(identity_path.read_text())
    manifest = json.loads((parent / 'MANIFEST.json').read_text())
    assert manifest == json.loads((HERE / 'PREFIX-PIN.json').read_text()) and manifest['content_id'] == BASE
    assert manifest['sources'][SOURCE] == 'a01fe06b0ceb8e1d2e6ecfbd719e16d59a33cf9cab57874e051f381d425beaf6'
    assert len(manifest['sources']) == 8 and len(manifest['classes']) == 15
    assert sha(HERE / 'source/ComputerUtil.java') == POST_SHA
    assert sha(HERE / 'preimage/ComputerUtil.java') == manifest['sources'][SOURCE]
    assert not out.exists() and not out.is_symlink()
    assert not out.is_relative_to(HERE.parents[4]) and not out.is_relative_to(parent)
    assert 'nfs' not in subprocess.check_output(['findmnt', '-T', str(out.parent), '-n', '-o', 'FSTYPE'], text=True)
    before = {str(parent / 'source' / path): digest for path, digest in manifest['sources'].items()}
    before.update({str(parent / 'shadow' / path): digest for path, digest in manifest['classes'].items()})
    assert all(sha(path) == digest for path, digest in before.items())
    out.mkdir(mode=0o700)
    for group in ('source', 'shadow', 'compiled-one'):
        (out / group).mkdir(mode=0o700)
    for group, values in [('source', manifest['sources']), ('shadow', manifest['classes'])]:
        for relative in values:
            target = out / group / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(parent / group / relative, target)
    with (out / 'patch.log').open('wb') as log:
        result = subprocess.run(['patch', '--batch', '--fuzz=0', '-p0', '-i', str(HERE / 'fog-activation-legality.patch')],
                                cwd=out / 'source', stdout=log, stderr=log)
    assert result.returncode == 0 and not re.search(r'offset|fuzz|FAILED', (out / 'patch.log').read_text())
    assert sha(out / 'source' / SOURCE) == POST_SHA
    jdk = Path(identity['jdk'])
    argv = [str(jdk / 'bin/javac'), '-J-Xmx1500m', '-J-XX:ActiveProcessorCount=1', '--release', '17',
            '-proc:none', '-implicit:none', '-sourcepath', '', '-cp',
            ':'.join([str(parent / 'shadow')] + identity['runtime_classpath']), '-d', str(out / 'compiled-one'),
            str(out / 'source' / SOURCE)]
    (out / 'BUILD-ARGV.json').write_text(json.dumps(argv, indent=2) + '\n')
    with (out / 'compile.log').open('wb') as log:
        subprocess.run(argv, stdout=log, stderr=log, check=True)
    compiled = sorted(path.relative_to(out / 'compiled-one').as_posix() for path in (out / 'compiled-one').rglob('*.class'))
    assert compiled == [PAYLOAD], compiled
    shutil.copyfile(out / 'compiled-one' / PAYLOAD, out / 'shadow' / PAYLOAD)
    sources = {path: sha(out / 'source' / path) for path in manifest['sources']}
    classes = {path: sha(out / 'shadow' / path) for path in manifest['classes']}
    assert all(sources[path] == digest for path, digest in manifest['sources'].items() if path != SOURCE)
    assert all(classes[path] == digest for path, digest in manifest['classes'].items() if path != PAYLOAD)
    assert all(sha(path) == digest for path, digest in before.items())
    body = {'schema': 1, 'parent_content_id': BASE, 'sources': sources, 'classes': classes}
    content = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    (out / 'MANIFEST.json').write_text(json.dumps(dict(body, content_id=content), indent=2) + '\n')
    (out / 'APPROVED-BUNDLE.json').write_text(json.dumps({'schema': 6, 'sources': sources, 'classes': classes}, indent=2) + '\n')
    (out / 'BUILD-PROOF.json').write_text(json.dumps({'compiled_sources': 1, 'compiled_classes': 1,
        'unchanged_source_count': 7, 'unchanged_class_count': 14, 'strict_worker_unchanged': True,
        'parent_inputs_unchanged': True, 'content_id': content, 'source_sha256': POST_SHA,
        'class_sha256': classes[PAYLOAD], 'profile_built': False}, indent=2) + '\n')
    print((out / 'BUILD-PROOF.json').read_text())


if __name__ == '__main__':
    main()
