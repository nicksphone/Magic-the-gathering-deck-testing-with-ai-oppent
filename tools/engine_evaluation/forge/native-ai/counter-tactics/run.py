#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pinned native Counter16 and candidate protocol controls; no application/database imports."""
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
COUNTER = 'forge-ai/src/main/java/forge/ai/ability/CounterAi.java'
COUNTER_CLASS = 'forge/ai/ability/CounterAi.class'
SOURCE_SHA = 'fa781549b9272dd3b8fc05e80febc9baf470722cb5edce67a2ae4c9e3e423659'
CLASS_SHA = 'baf7d165ef2115d475a29438e9280fcec27b5007228548a4b20dea5852a2b823'
BASE_CLASS_SHA = '4572424c18ba1ba060b5c7f1de4c4e3cccc40da3f6d5361173cdb16aeb208823'
AUDITS = {
    'NativeCountertactics16.java': 'd0397d11eb4a718c2c88f941a607ca19a17c328431660eefae5f195e59d52774',
    'NativeCounterTargetLegality2.java': 'de1b753591263c217d1a978740f0fee69e4049659972b6be16b4afec524d5e33',
    'NativeCounterWorship2.java': 'a1dda0bba527460703886480cc7a4e24414bf34046a779586003a18c938dd22e',
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
    parser.add_argument('parent', type=Path, help='Exact E5 9-source/16-class prefix root containing MANIFEST.json')
    parser.add_argument('out', type=Path, help='Fresh local private evidence directory')
    parser.add_argument('candidate', type=Path, nargs='?', help='Optional exact Counter candidate3 10-source/17-class prefix root')
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
    runs = []
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
        need(len(expected['sources']) == 9 and len(expected['classes']) == 16
             and expected['content_id'] == 'a7d94a7e8998cdc81fb6f6cc762a551e1e03f1c918f0e9fbbea56155b6ef32c1',
             'Wrong E5 payload declaration')
        base, pins = prefix(parent, expected)
        runtime = candidate or parent
        if candidate:
            manifest, more = prefix(candidate, json.loads((HERE / 'CANDIDATE-PIN.json').read_text()))
            need(manifest['sources'] == {**base['sources'], COUNTER: SOURCE_SHA}, 'Old nine sources must remain unchanged')
            need(manifest['classes'] == {**base['classes'], COUNTER_CLASS: CLASS_SHA}, 'Old sixteen classes must remain unchanged')
            need(manifest['content_id'] == 'db05b7032887ce9d5b9f769b915f25e9ebdbc04a03f4f8dd4040537d6216f242',
                 'Wrong Counter candidate3 identity')
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
        need(sha(HERE / 'source' / COUNTER) == SOURCE_SHA, 'Product source is not frozen fa7815')
        preimage = HERE / 'preimage' / COUNTER
        need((forge / COUNTER).read_bytes() == preimage.read_bytes(), 'Forge source differs from the frozen preimage')
        pins[str(forge / COUNTER)] = sha(preimage)
        pins[str(forge / 'forge-ai/target/classes' / COUNTER_CLASS)] = BASE_CLASS_SHA
        canonical = json.loads((HERE / 'CANONICAL-PINS.json').read_text())
        need(len(canonical) == 12, 'Exactly twelve complete canonical programs required')
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
        need(emitted == {'forge/evaluation/NativeCountertactics16.class',
                         'forge/evaluation/NativeCounterTargetLegality2.class',
                         'forge/evaluation/NativeCounterWorship2.class'}, 'Unexpected harness class inventory')
        harness_pins = {str(out / 'classes' / name): sha(out / 'classes' / name) for name in emitted}
        save('HARNESS-CLASS-PINS.json', harness_pins)
        executions = [
                ('COUNTER16', 'forge.evaluation.NativeCountertactics16', []),
                ('GILDED2', 'forge.evaluation.NativeCounterTargetLegality2', ['candidate' if candidate else 'baseline'])]
        if candidate:
            executions.append(('WORSHIP2', 'forge.evaluation.NativeCounterWorship2', ['candidate']))
        baseline_not_executed = {} if candidate else {
            'WORSHIP2': {'execution': 'NOT_EXECUTED', 'helper_predicate': 'INAPPLICABLE_BASELINE'}}
        save('EXECUTION-DECLARATION.json', {'fresh_native_JVMs': len(executions),
             'native_case_rows': 20 if candidate else 18, 'shared_compile_and_native_budget_seconds': 300,
             'baseline_not_executed': baseline_not_executed})
        for label, main_class, extra in executions:
            report = out / 'reports' / label
            report.mkdir(mode=0o700)
            native_code = launch(label, [str(jdk / 'bin/java'), '-Xmx1500m', '-XX:ActiveProcessorCount=1',
                 '-Djava.awt.headless=true', '-Duser.home=' + str(out / 'home'), '-Djava.io.tmpdir=' + str(out / 'tmp'), '-Dsentry.dsn=',
                 '-Xlog:class+load=info:file=' + str(report / 'class-load.log') + ':uptime,level,tags',
                 '--add-opens', 'java.base/java.lang=ALL-UNNAMED', '-cp', str(out / 'classes') + ':' + cp,
                 main_class, str(report)] + extra, ('home', 'tmp', 'reports'))
            summary_path = report / 'summary.private.json'
            summary = json.loads(summary_path.read_text()) if summary_path.is_file() else None
            origins = {}
            log = report / 'class-load.log'
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
            counter_origin = runtime / 'shadow' if candidate else forge / 'forge-ai/target/classes'
            if summary is not None:
                if origins.get('forge.ai.ability.CounterAi') != str(counter_origin):
                    origin_errors.append('forge.ai.ability.CounterAi')
                if origins.get('forge.ai.ComputerUtil') != str(runtime / 'shadow'):
                    origin_errors.append('forge.ai.ComputerUtil')
            run = {'label': label, 'native_exit': native_code, 'summary': summary,
                   'actual_loaded_override_origins': observed,
                   'actual_CounterAi_origin': origins.get('forge.ai.ability.CounterAi'), 'origin_errors': origin_errors,
                   'helper_assertion_applicable': candidate is not None if label != 'COUNTER16' else None,
                   'predicate_status': 'NOT_APPLICABLE_BASELINE_OBSERVATION_ONLY' if label == 'GILDED2' and candidate is None else 'APPLICABLE'}
            runs.append(run)
            save(label + '-RESULT.private.json', run)
            if native_code not in (0, 1):
                break
            need(summary is not None and summary['harness_errors'] == 0, 'Missing complete native result or harness errors')
            if label == 'COUNTER16':
                need(summary['total'] == summary['ordinary_Default_choices'] == 16
                     and summary['pass'] + summary['policy_red'] == 16 and summary['natural_games'] == 0
                     and summary['seed_search_or_late_RNG_reset'] is False,
                     'Counter16 did not execute its exact frozen declaration')
                need(native_code == (1 if summary['policy_red'] else 0), 'Counter16 exit disagrees with strict verdict')
            elif label == 'GILDED2':
                need(summary['total'] == 2 and summary['pass'] + summary['protocol_red'] == 2
                     and summary['candidate_helper_assertions_applicable'] is (candidate is not None)
                     and summary['ordinary_choice_has_no_forced_decline_expectation'] is True
                     and summary['natural_games'] == 0, 'Wrong Gilded2 protocol scope')
                need(native_code == (1 if summary['protocol_red'] else 0), 'Gilded2 exit disagrees with strict verdict')
            else:
                need(candidate is not None and summary['total'] == 2
                     and summary['pass'] + summary['protocol_red'] == 2
                     and summary['candidate_only_internal_protocol'] is True
                     and summary['forced_ordinary_decline_assertion'] is False
                     and summary['natural_games'] == 0, 'Wrong Worship2 protocol scope')
                need(native_code == (1 if summary['protocol_red'] else 0), 'Worship2 exit disagrees with strict verdict')
        changed = verify(pins) + verify(harness_pins)
        base_changed = verify(resources)
        prefix(parent, expected)
        if candidate:
            prefix(candidate, json.loads((HERE / 'CANDIDATE-PIN.json').read_text()))
        need({p.relative_to(out / 'classes').as_posix() for p in (out / 'classes').rglob('*.class')} == emitted,
             'Harness class inventory changed during gate')
        save('AFTER.json', {'changed_inputs': changed, 'changed_base_resources': base_changed,
             'base_resources_checked': len(resources), 'physical_payload_count': len(manifest['classes']),
             'runs': [{key: value for key, value in run.items() if key != 'summary'} for run in runs],
             'no_forced_class_loading': True})
        need(not changed and not base_changed, 'Pinned input changed during gate')
        need(not any(run['origin_errors'] for run in runs), 'Loaded origin verification failed')
        codes = [run['native_exit'] for run in runs]
        native_code = next((code for code in codes if code not in (0, 1)), next((code for code in codes if code), 0))
        if native_code == 0:
            need(len(runs) == len(executions), 'Exit zero without all declared fresh native JVM results')
        status = ('PASS' if candidate else 'BASELINE_OBSERVATION_ONLY') if native_code == 0 else 'STRICT_RED' if native_code == 1 else 'NATIVE_ERROR'
        save('RESULT.json', {'status': status, 'native_exit': native_code, 'seconds': time.monotonic() - started,
             'runtime_content_id': manifest['content_id'], 'runs': runs, 'all_pins_unchanged': True,
             'natural_game': False, 'baseline_not_executed': baseline_not_executed,
             'private_preservation10_applicability4_protocol8_included': False})
        print(json.dumps({'status': status, 'exit': native_code, 'native_exits': codes,
                          'gilded_helper_predicate': 'APPLICABLE' if candidate else 'INAPPLICABLE_BASELINE_OBSERVATION_ONLY',
                          'worship_execution': 'DECLARED_CANDIDATE_ONLY' if candidate else 'NOT_EXECUTED_HELPER_INAPPLICABLE_BASELINE',
                          'counts': [{key: run['summary'].get(key) for key in ('total', 'pass', 'policy_red', 'protocol_red', 'harness_errors')}
                                     if run['summary'] else None for run in runs]}))
        return native_code
    except BaseException as error:
        save('RUNNER-ERROR.private.json', {'type': type(error).__name__, 'message': str(error), 'native_exit': native_code, 'runs': runs})
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
