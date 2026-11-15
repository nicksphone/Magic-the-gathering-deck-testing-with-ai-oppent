#!/usr/bin/env python3
"""Pinned controlled native Chalice audit; no application or database imports."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import time
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent
IDENTITY_SHA = 'cf27ccd7a08f1a9433f75da8d399b3e9c87b83b95b17f883ffc4812ee2dfb3d0'
CONTENT_SHA = 'acc7567174ff29e05a392d246b6c54e9b65a14d3e145dd661e60ec34739c624a'
PERMANENT = 'forge-ai/src/main/java/forge/ai/ability/PermanentAi.java'
PERMANENT_CLASS = 'forge/ai/ability/PermanentAi.class'
SOURCE_SHA = '5608d80db5a78f164dbdf582c13a887968fc52c7c0e5e628e66709dae7b26fc2'
CLASS_SHA = 'bb532065e50b3ead54c2711bc73c9d6a2d18d37b5e67fc5fad61d28c7c15298d'
AUDITS = {
    'NativeChalicePartitionAudit.java': '730112256129c7ea887e7b9965b9a96a6cf13fdc458678f2408f0e98eeb89aad',
    'NativeChaliceGoldenAudit.java': '379e3608c04dd90d82d9af4ad5163b60ac3ebd42aee96ea8ebbffcb28c94934c',
}


def need(ok, message):
    if not ok:
        raise RuntimeError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def verify(pins):
    changed = []
    for name, pin in pins.items():
        path = Path(name)
        digest = pin['sha256'] if isinstance(pin, dict) else pin
        if not path.is_file() or (isinstance(pin, dict) and path.stat().st_size != pin['bytes']) or sha(path) != digest:
            changed.append(name)
    return changed


def prefix(root, expected):
    manifest = json.loads((root / 'MANIFEST.json').read_text())
    need(manifest == expected, 'Prefix manifest is not the exact qualified payload')
    pins = {str(root / 'MANIFEST.json'): sha(root / 'MANIFEST.json')}
    for key, directory in [('sources', 'source'), ('classes', 'shadow')]:
        actual = set()
        for path in (root / directory).rglob('*'):
            need(not path.is_symlink(), 'Prefix payload symlinks are not admitted')
            if path.is_file():
                actual.add(path.relative_to(root / directory).as_posix())
        need(actual == set(manifest[key]), 'Prefix payload has missing or extra files')
        pins.update({str(root / directory / name): value for name, value in manifest[key].items()})
    return manifest, pins


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('identity', type=Path, help='Qualified base BUILD-IDENTITY.json')
    parser.add_argument('parent', type=Path, help='Exact E4 prefix root containing MANIFEST.json')
    parser.add_argument('out', type=Path, help='Fresh local private evidence directory')
    parser.add_argument('candidate', type=Path, nargs='?', help='Optional exact E5 candidate prefix root')
    args = parser.parse_args()
    identity_path, parent, out = [p.resolve() for p in (args.identity, args.parent, args.out)]
    candidate = args.candidate.resolve() if args.candidate else None
    os.umask(0o077)
    def interrupted(signum, frame):
        raise KeyboardInterrupt('Runner interrupted')
    signal.signal(signal.SIGTERM, interrupted)
    need(sha(identity_path) == IDENTITY_SHA, 'Wrong qualified base identity')
    identity = json.loads(identity_path.read_text())
    forge, jdk, cache = [Path(identity[k]) for k in ('forge', 'jdk', 'cache')]
    need(not out.exists() and out.parent.is_dir(), 'Use a fresh evidence directory with an existing local parent')
    protected = [HERE, parent, identity_path.parent, cache] + ([candidate] if candidate else [])
    need(all(not out.is_relative_to(p) and not p.is_relative_to(out) for p in protected), 'Evidence must be disjoint from inputs')
    need(all(':' not in str(p) for p in protected + [out]), 'Colon-bearing classpath roots are not admitted')
    types = subprocess.check_output(['findmnt', '-n', '-o', 'FSTYPE', '-T', str(out.parent)], text=True).split()
    need(types and not any(t in ('nfs', 'nfs4', 'cifs', 'smb3') for t in types), 'Active evidence must be local')
    out.mkdir(mode=0o700)

    def save(name, value):
        with (out / name).open('x') as stream:
            json.dump(value, stream, indent=2)
            stream.write('\n')

    process = None
    native_code = None
    started = time.monotonic()
    try:
        for name in ('source', 'classes', 'home', 'tmp', 'reports'):
            (out / name).mkdir(mode=0o700)
        base_content = identity_path.parent / 'RUNTIME-CONTENT.json'
        need(sha(base_content) == CONTENT_SHA, 'Wrong base runtime-content manifest')
        resources = json.loads(base_content.read_text())
        need(len(resources) == identity['files'] == 59971, 'Wrong base resource inventory')
        need(not verify(resources), 'Qualified base resource pin mismatch')
        expected = json.loads((HERE / 'PREFIX-PIN.json').read_text())
        need(len(expected['sources']) == 8 and len(expected['classes']) == 15, 'Wrong E4 payload declaration')
        base, pins = prefix(parent, expected)
        runtime = candidate or parent
        if candidate:
            manifest, more = prefix(candidate, json.loads((HERE / 'CANDIDATE-PIN.json').read_text()))
            need(manifest['sources'] == {**base['sources'], PERMANENT: SOURCE_SHA}, 'Old eight sources must remain unchanged')
            need(manifest['classes'] == {**base['classes'], PERMANENT_CLASS: CLASS_SHA}, 'Old fifteen classes must remain unchanged')
            pins.update(more)
        else:
            manifest = base
        package = json.loads((HERE / 'PINS.json').read_text())
        pins.update({str(HERE / name): digest for name, digest in package.items()})
        pins[str(HERE / 'PINS.json')] = sha(HERE / 'PINS.json')
        pins[str(identity_path)] = IDENTITY_SHA
        pins[str(base_content)] = CONTENT_SHA
        for name, digest in AUDITS.items():
            need(sha(HERE / name) == digest, 'Frozen original/golden Java source changed')
            shutil.copyfile(HERE / name, out / 'source' / name)
            pins[str(out / 'source' / name)] = digest
        need(sha(HERE / 'source' / PERMANENT) == SOURCE_SHA, 'Product source is not frozen 5608')
        preimage = HERE / 'preimage' / PERMANENT
        need((forge / PERMANENT).read_bytes() == preimage.read_bytes(), 'Forge source differs from the frozen preimage')
        pins[str(forge / PERMANENT)] = sha(preimage)
        canonical = json.loads((HERE / 'CANONICAL-PINS.json').read_text())
        need(len(canonical) == 6, 'Exactly six complete canonical programs required')
        for name, pin in canonical.items():
            local, original = HERE / 'canonical' / name, forge / pin['upstream_path']
            need(local.read_bytes() == original.read_bytes() and sha(local) == pin['sha256'], 'Canonical program mismatch')
            pins[str(original)] = pin['sha256']
        need(not verify(pins), 'Input pin mismatch')
        save('BEFORE.json', {'pins': pins, 'base_resources_verified': len(resources),
             'base_runtime_manifest_sha256': CONTENT_SHA, 'parent_content_id': base['content_id'],
             'runtime_content_id': manifest['content_id'], 'candidate_mode': candidate is not None})
        cp = ':'.join([str(runtime / 'shadow')] + identity['runtime_classpath'])
        env = {'PATH': '/usr/bin:/bin', 'HOME': str(out / 'home'), 'LANG': 'C.UTF-8', 'TMPDIR': str(out / 'tmp')}
        deadline = time.monotonic() + 300

        def launch(label, command, writable):
            nonlocal process
            found = subprocess.run(['ps', '-C', 'java,javac', '-o', 'pid='], capture_output=True, text=True, timeout=5)
            need(found.returncode in (0, 1) and not found.stderr, 'Unable to inspect existing JVMs')
            need(found.returncode != 1 or found.stdout == '', 'ps exit one must mean no JVMs')
            other = found.stdout.split()
            need(all(pid.isdecimal() for pid in other), 'Unexpected JVM PID output')
            need(len(other) <= 1, 'At most one other JVM is admitted')
            remaining = deadline - time.monotonic()
            need(remaining > 0, 'Compile/native 300-second budget exhausted')
            argv = ['timeout', '-k', '5s', str(math.ceil(remaining)), 'bwrap', '--unshare-user', '--unshare-net',
                    '--unshare-pid', '--unshare-ipc', '--unshare-uts', '--die-with-parent', '--new-session']
            for path in dict.fromkeys(['/usr', '/lib', '/lib64', '/bin', '/etc', str(cache),
                                      str(identity_path.parent), str(parent), str(runtime), str(out)]):
                argv += ['--ro-bind', path, path]
            argv += ['--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp']
            for name in writable:
                argv += ['--bind', str(out / name), str(out / name)]
            argv += ['--chdir', str(forge / 'forge-gui-desktop'), '--clearenv', '--setenv', 'PATH',
                     str(jdk / 'bin') + ':/usr/bin:/bin', '--setenv', 'HOME', str(out / 'home'),
                     '--setenv', 'LANG', 'C.UTF-8'] + command
            save(label + '-ARGV.private.json', argv)
            begin = time.monotonic()
            with (out / (label + '.stdout.private.log')).open('xb') as stdout, (out / (label + '.stderr.private.log')).open('xb') as stderr:
                process = subprocess.Popen(argv, env=env, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, start_new_session=True)
                save(label + '-LAUNCH.json', {'pid': process.pid, 'other_java_pids': other})
                code = process.wait()
            save(label + '-CLOSED.json', {'exit': code, 'seconds': time.monotonic() - begin})
            process = None
            return code

        compile_code = launch('COMPILE', [str(jdk / 'bin/javac'), '-J-Xmx1500m', '-J-XX:ActiveProcessorCount=1',
             '--release', '17', '-proc:none', '-implicit:none', '-sourcepath', '', '-cp', cp, '-d', str(out / 'classes')]
             + [str(out / 'source' / name) for name in AUDITS], ('home', 'tmp', 'classes'))
        if compile_code != 0:
            changed, base_changed = verify(pins), verify(resources)
            save('AFTER.json', {'changed_inputs': changed, 'changed_base_resources': base_changed,
                 'base_resources_checked': len(resources), 'physical_payload_count': len(manifest['classes']),
                 'observed_payload_count': 0, 'native_started': False})
            need(not changed and not base_changed, 'Pinned input changed during harness compilation')
            save('RESULT.json', {'status': 'HARNESS_COMPILE_FAILED', 'compile_exit': compile_code,
                 'native_exit': None, 'native_started': False})
            print(json.dumps({'status': 'HARNESS_COMPILE_FAILED', 'exit': compile_code}))
            return compile_code
        emitted = {p.relative_to(out / 'classes').as_posix() for p in (out / 'classes').rglob('*.class')}
        need(emitted == {'forge/evaluation/NativeChalicePartitionAudit.class', 'forge/evaluation/NativeChalicePartitionAudit$Case.class',
                         'forge/evaluation/NativeChaliceGoldenAudit.class'}, 'Unexpected harness class inventory')
        harness_pins = {str(out / 'classes' / name): sha(out / 'classes' / name) for name in emitted}
        save('HARNESS-CLASS-PINS.json', harness_pins)
        native_code = launch('NATIVE', [str(jdk / 'bin/java'), '-Xmx1500m', '-XX:ActiveProcessorCount=1',
             '-Djava.awt.headless=true', '-Duser.home=' + str(out / 'home'), '-Djava.io.tmpdir=' + str(out / 'tmp'), '-Dsentry.dsn=',
             '-Xlog:class+load=info:file=' + str(out / 'reports/class-load.log') + ':uptime,level,tags',
             '--add-opens', 'java.base/java.lang=ALL-UNNAMED', '-cp', str(out / 'classes') + ':' + cp,
             'forge.evaluation.NativeChaliceGoldenAudit', str(out / 'reports')], ('home', 'tmp', 'reports'))
        summary_path = out / 'reports/summary.private.json'
        summary = json.loads(summary_path.read_text()) if summary_path.is_file() else None
        origins = {}
        log = out / 'reports/class-load.log'
        for line in log.read_text().splitlines() if log.exists() else []:
            match = re.search(r'\] (forge\.[\w.$]+) source: file:(.*)$', line)
            if match:
                origins[match[1]] = str(Path(unquote(match[2])).resolve())
        observed, origin_errors = {}, []
        for name in manifest['classes']:
            binary = name[:-6].replace('/', '.')
            if binary in origins:
                if Path(origins[binary]) != runtime / 'shadow':
                    origin_errors.append(binary)
                observed[binary] = origins[binary]
        permanent_origin = runtime / 'shadow' if candidate else forge / 'forge-ai/target/classes'
        if native_code in (0, 1, 2) and summary is not None:
            if origins.get('forge.ai.ability.PermanentAi') != str(permanent_origin):
                origin_errors.append('forge.ai.ability.PermanentAi')
            if origins.get('forge.ai.ComputerUtil') != str(runtime / 'shadow'):
                origin_errors.append('forge.ai.ComputerUtil')
        changed = verify(pins) + verify(harness_pins)
        base_changed = verify(resources)
        prefix(parent, expected)
        if candidate:
            prefix(candidate, json.loads((HERE / 'CANDIDATE-PIN.json').read_text()))
        need({p.relative_to(out / 'classes').as_posix() for p in (out / 'classes').rglob('*.class')} == emitted,
             'Harness class inventory changed during gate')
        save('AFTER.json', {'changed_inputs': changed, 'changed_base_resources': base_changed,
             'base_resources_checked': len(resources), 'physical_payload_count': len(manifest['classes']),
             'observed_payload_count': len(observed), 'actual_loaded_override_origins': observed,
             'actual_PermanentAi_origin': origins.get('forge.ai.ability.PermanentAi'), 'origin_errors': origin_errors,
             'no_forced_class_loading': True})
        need(not changed and not base_changed, 'Pinned input changed during gate')
        need(not origin_errors, 'Loaded origin verification failed')
        status = 'INCOMPLETE' if summary is None else 'PASS' if native_code == 0 else 'POLICY_RED' if native_code == 1 else 'HARNESS_ERROR'
        if native_code == 0:
            need(summary is not None and summary['old8'] == {'rows': 8, 'private_pairs_red': 0, 'public_control_pairs_valid': 2}
                 and summary['new10'] == {'rows': 10, 'pass_cases': 10, 'strict_policy_red_cases': 0, 'exile_pairs_pass': 2}
                 and summary['control_fail'] == summary['harness_errors'] == summary['synthetic_cases_run'] == 0
                 and summary['natural_game'] is False, 'Exit zero without the exact complete 18-case result')
        save('RESULT.json', {'status': status, 'native_exit': native_code, 'seconds': time.monotonic() - started,
             'runtime_content_id': manifest['content_id'], 'summary': summary, 'all_pins_unchanged': True,
             'natural_game': False, 'old_standalone_main_rerun': False})
        print(json.dumps({'status': status, 'exit': native_code, 'old8': summary.get('old8') if summary else None,
                          'new10': summary.get('new10') if summary else None}))
        return native_code
    except BaseException as error:
        save('RUNNER-ERROR.private.json', {'type': type(error).__name__, 'message': str(error), 'native_exit': native_code})
        print(json.dumps({'status': 'RUNNER_ERROR', 'native_exit': native_code, 'error_type': type(error).__name__}))
        return 2
    finally:
        if process is not None and process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()


if __name__ == '__main__':
    raise SystemExit(main())
