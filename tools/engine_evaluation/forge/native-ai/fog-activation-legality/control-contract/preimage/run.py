#!/usr/bin/env python3
"""Bounded original-eight plus separately labelled native preservation controls."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
BASE = '0c04d1b1435472432cfb377db47595ca3b3ff76c18eeb6d6db57ec4f076f8ef1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    identity_path, parent, out = (Path(value).resolve() for value in sys.argv[1:4])
    candidate = Path(sys.argv[4]).resolve() if len(sys.argv) == 5 else None
    identity = json.loads(identity_path.read_text())
    assert sha(identity_path) == 'cf27ccd7a08f1a9433f75da8d399b3e9c87b83b95b17f883ffc4812ee2dfb3d0'
    assert not out.exists(), 'Use a fresh evidence root; never retry an expired gate'
    out.mkdir(mode=0o700)
    def save(name, data):
        (out / name).write_text(json.dumps(data, indent=2) + '\n')
    for name in ('source', 'classes', 'home', 'tmp', 'reports'):
        (out / name).mkdir(mode=0o700)
    base = json.loads((parent / 'MANIFEST.json').read_text())
    assert base == json.loads((HERE / 'PREFIX-PIN.json').read_text()) and base['content_id'] == BASE
    runtime = candidate or parent
    manifest = json.loads((runtime / 'MANIFEST.json').read_text())
    assert len(manifest['sources']) == 8 and len(manifest['classes']) == 15
    pins = {str(identity_path): sha(identity_path)}
    for directory, data in [(parent, base), (runtime, manifest)]:
        pins[str(directory / 'MANIFEST.json')] = sha(directory / 'MANIFEST.json')
        pins.update({str(directory / 'shadow' / path): digest for path, digest in data['classes'].items()})
        pins.update({str(directory / 'source' / path): digest for path, digest in data['sources'].items()})
    for name in ('NativeFogActivationAudit.java', 'NativeFogActivationControls.java', 'DECLARATION.json'):
        pins[str(HERE / name)] = sha(HERE / name)
    assert sha(HERE / 'NativeFogActivationAudit.java') == '14890b4f97de6b1a575913ef0296c702d757a4f7bd7144009ea8051c08bde2ae'
    forge, jdk, cache = (Path(identity[key]) for key in ('forge', 'jdk', 'cache'))
    for path in (HERE / 'canonical').glob('*.txt'):
        original = forge / 'forge-gui/res/cardsfolder' / path.name[0] / path.name
        assert path.read_bytes() == original.read_bytes()
        pins[str(path)] = sha(path)
        pins[str(original)] = sha(original)
    assert all(sha(path) == digest for path, digest in pins.items())
    save('BEFORE.json', {'pins': pins, 'base': BASE, 'runtime': manifest['content_id']})
    sources = [HERE / name for name in ('NativeFogActivationAudit.java', 'NativeFogActivationControls.java')]
    for path in sources:
        shutil.copyfile(path, out / 'source' / path.name)
    cp = ':'.join([str(runtime / 'shadow')] + identity['runtime_classpath'])
    compile_argv = [str(jdk / 'bin/javac'), '-J-Xmx1500m', '-J-XX:ActiveProcessorCount=1', '--release', '17',
                    '-proc:none', '-implicit:none', '-sourcepath', '', '-cp', cp, '-d', str(out / 'classes')]
    compile_argv += [str(out / 'source' / path.name) for path in sources]
    save('COMPILE-ARGV.json', compile_argv)
    with (out / 'compile.log').open('wb') as log:
        result = subprocess.run(compile_argv, stdout=log, stderr=log)
    save('COMPILE-EXIT.json', {'exit': result.returncode})
    assert result.returncode == 0, 'Harness compile error, not a native RED'
    java = subprocess.run(['ps', '-C', 'java', '-o', 'pid='], capture_output=True, text=True).stdout.split()
    assert len(java) <= 1, 'At most one other authorized native JVM'
    argv = ['timeout', '-k', '5s', '300', 'bwrap', '--unshare-user', '--unshare-net', '--unshare-pid',
            '--unshare-ipc', '--unshare-uts', '--die-with-parent', '--new-session']
    for path in ['/usr', '/lib', '/lib64', '/bin', '/etc', str(cache), str(identity_path.parent), str(parent), str(runtime)]:
        argv += ['--ro-bind', path, path]
    argv += ['--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp', '--ro-bind', str(out), str(out)]
    for name in ('home', 'tmp', 'reports'):
        argv += ['--bind', str(out / name), str(out / name)]
    argv += ['--chdir', str(forge / 'forge-gui-desktop'), '--clearenv', '--setenv', 'PATH',
             str(jdk / 'bin') + ':/usr/bin:/bin', '--setenv', 'HOME', str(out / 'home'), '--setenv', 'LANG', 'C.UTF-8',
             str(jdk / 'bin/java'), '-Xmx1500m', '-XX:ActiveProcessorCount=1', '-Djava.awt.headless=true',
             '-Duser.home=' + str(out / 'home'), '-Djava.io.tmpdir=' + str(out / 'tmp'), '-Dsentry.dsn=',
             '-Xlog:class+load=info:file=' + str(out / 'reports/class-load.log') + ':uptime,level,tags',
             '--add-opens', 'java.base/java.lang=ALL-UNNAMED', '-cp', str(out / 'classes') + ':' + cp,
             'forge.evaluation.NativeFogActivationControls', str(out / 'reports')]
    save('ARGV.json', argv)
    started = time.monotonic()
    with (out / 'stdout.private.log').open('wb') as stdout, (out / 'stderr.private.log').open('wb') as stderr:
        process = subprocess.Popen(argv, stdout=stdout, stderr=stderr, start_new_session=True)
        save('LAUNCH.json', {'pid': process.pid, 'other_java_pids': java})
        code = process.wait()
    save('PROCESS-CLOSED.json', {'exit': code, 'seconds': time.monotonic() - started})
    summary = json.loads((out / 'reports/summary.private.json').read_text()) if (out / 'reports/summary.private.json').exists() else None
    origins = {}
    for line in (out / 'reports/class-load.log').read_text().splitlines():
        found = re.search(r'\] (forge\.[\w.$]+) source: file:(.*)$', line)
        if found:
            origins[found[1]] = found[2].rstrip('/')
    observed = {}
    for path in manifest['classes']:
        name = path[:-6].replace('/', '.')
        if name in origins:
            assert Path(origins[name]) == runtime / 'shadow'
            observed[name] = origins[name]
    assert Path(origins['forge.ai.ComputerUtil']) == runtime / 'shadow'
    changes = [path for path, digest in pins.items() if sha(path) != digest]
    save('AFTER.json', {'changed_inputs': changes, 'pins': pins, 'actual_loaded_origins': observed,
                        'physical_payload_count': 15, 'observed_payload_count': len(observed)})
    save('RESULT.json', {'status': 'CLOSED' if summary is not None and code in (0, 1, 2) else 'INCOMPLETE',
                         'exit': code, 'seconds': time.monotonic() - started, 'summary': summary,
                         'runtime_content_id': manifest['content_id'], 'all_pins_unchanged': not changes,
                         'natural_game': False})
    print((out / 'RESULT.json').read_text())
    assert not changes
    raise SystemExit(code)


if __name__ == '__main__':
    main()
