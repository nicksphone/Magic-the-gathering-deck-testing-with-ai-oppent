#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Candidate-only native Drain8 + Timing6 + Preservation8; all 22 rows mandatory."""
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
PARENT_ID = 'db05b7032887ce9d5b9f769b915f25e9ebdbc04a03f4f8dd4040537d6216f242'
AI_CONTROLLER_SHA = 'e8a7ae4d39b73a9f95c70dbae2b5c54e75b3c1a7cdfb14c6fa2e013026b563e7'
NEW_SOURCES = {'forge-ai/src/main/java/forge/ai/AiController.java',
               'forge-ai/src/main/java/forge/ai/SpellAbilityAi.java'}
NEW_CLASSES = {'forge/ai/AiController.class', 'forge/ai/AiController$1.class', 'forge/ai/SpellAbilityAi.class'}
AUDITS = (
    ('DRAIN8', 'NativeDrainTactics8', 8, 'policy_red',
     'f9b29fe3e5b587c258657a3376969ed3af11b216ec0a8af6fb41737f3b36fa4d'),
    ('TIMING6', 'NativeSacrificeTiming6', 6, 'policy_red',
     '0386517d53e7aa53d29cf9f3d6347235a6d4107a35acea0d08ef7685b851c73e'),
    ('PRESERVATION8', 'NativeSacrificePreservation8', 8, 'helper_red',
     '69ed4cc37c2c8eee54df97c5798446903fafd221c029228f0cbac12d5aa25b80'),
)


def need(ok, message):
    if not ok:
        raise RuntimeError(message)


def input_path(path):
    path = Path(path)
    need(not any(part == '.git' or part.startswith('.env') or part.endswith('.lock')
                 or part.startswith('resource-counterbalanced') or part.startswith('qv-state')
                 or part in ('FEATURES.private.json', 'MODEL.private.json', 'mtg_lab.db')
                 for part in path.parts), 'Protected input path is not admitted')
    return path


def sha(path):
    digest = hashlib.sha256()
    with input_path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def verify(pins):
    changed = []
    for name, pin in pins.items():
        path = input_path(name)
        digest = pin['sha256'] if isinstance(pin, dict) else pin
        if not path.is_file() or (isinstance(pin, dict) and path.stat().st_size != pin['bytes']) or sha(path) != digest:
            changed.append(name)
    return changed


def relative(name):
    path = Path(name)
    need(isinstance(name, str) and not path.is_absolute() and path.parts
         and '..' not in path.parts and path.as_posix() == name, 'Noncanonical relative input path')
    input_path(path)
    return path


def prefix(root, expected):
    manifest = json.loads(input_path(root / 'MANIFEST.json').read_text())
    need(manifest == expected and manifest['schema'] == 1, 'Prefix manifest differs from the frozen payload')
    pins = {str(root / 'MANIFEST.json'): sha(root / 'MANIFEST.json')}
    for key, directory in [('sources', 'source'), ('classes', 'shadow')]:
        actual = set()
        for path in (root / directory).rglob('*'):
            need(not path.is_symlink(), 'Prefix payload symlinks are not admitted')
            if path.is_file():
                actual.add(path.relative_to(root / directory).as_posix())
        need(actual == set(manifest[key]), 'Prefix payload has missing or extra files')
        for name, digest in manifest[key].items():
            need(re.fullmatch('[0-9a-f]{64}', digest) is not None, 'Malformed prefix SHA256')
            pins[str(root / directory / relative(name))] = digest
    return manifest, pins


def package_pins():
    package = json.loads((HERE / 'PINS.json').read_text())
    paths = list(HERE.rglob('*'))
    need(not any(path.is_symlink() for path in paths), 'Package symlinks are not admitted')
    actual = {path.relative_to(HERE).as_posix() for path in paths if path.is_file()}
    need(actual == set(package) | {'PINS.json'}, 'Package has missing or unpinned extra files')
    pins = {}
    for name, digest in package.items():
        need(re.fullmatch('[0-9a-f]{64}', digest) is not None, 'Malformed package SHA256')
        pins[str(HERE / relative(name))] = digest
    pins[str(HERE / 'PINS.json')] = sha(HERE / 'PINS.json')
    need(not verify(pins), 'Package byte pin mismatch')
    return pins


def check_summary(label, summary, native_exit):
    labels = {'DRAIN8': 'CONTROLLED-NATIVE-DRAIN-TACTICS8',
              'TIMING6': 'CONTROLLED-NATIVE-SACRIFICE-TIMING6',
              'PRESERVATION8': 'INTERNAL-PROTOCOL-NATIVE-SACRIFICE-PRESERVATION8'}
    spec = next(spec for spec in AUDITS if spec[0] == label)
    total, red_key = spec[2:4]
    fixed = {'label': labels[label], 'total': total, 'natural_games': 0,
             'ordinary_Default_initial_callbacks': total, 'RNG_purity_asserted': False}
    if label == 'PRESERVATION8':
        fixed.update({'ordinary_choices_judged': False, 'manual_controls_are_AI_successes': False, 'expert_games': 0})
    else:
        fixed['forced_AI_actions_or_winners'] = False
    need(isinstance(summary, dict) and set(summary) == set(fixed) | {'pass', red_key, 'harness_errors'},
         label + ': incomplete or unexpected summary schema')
    need(all(type(summary[key]) is type(value) and summary[key] == value for key, value in fixed.items()),
         label + ': frozen native declaration changed')
    need(all(type(summary[key]) is int and summary[key] >= 0 for key in ('pass', red_key, 'harness_errors')),
         label + ': malformed verdict counts')
    need(summary['harness_errors'] == 0 and summary['pass'] + summary[red_key] == total,
         label + ': all declared rows must close without harness errors')
    need(type(native_exit) is int and native_exit == (1 if summary[red_key] else 0),
         label + ': native exit disagrees with strict verdict')


def loaded_origins(log, manifest, candidate, classes, main_class):
    origins = {}
    for line in log.read_text().splitlines() if log.is_file() else []:
        match = re.search(r'\] (forge\.[\w.$]+) source: file:(.*)$', line)
        if match:
            origins[match[1]] = str(Path(unquote(match[2])).resolve())
    observed, errors = {}, []
    for name in manifest['classes']:
        binary = name[:-6].replace('/', '.')
        if binary in origins:
            observed[binary] = origins[binary]
            if origins[binary] != str(candidate / 'shadow'):
                errors.append(binary)
    for binary in ('forge.ai.AiController', 'forge.ai.SpellAbilityAi'):
        if origins.get(binary) != str(candidate / 'shadow'):
            errors.append(binary)
    if origins.get(main_class) != str(classes):
        errors.append(main_class)
    return observed, sorted(set(errors))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('identity', type=Path, help='Qualified base BUILD-IDENTITY.json')
    parser.add_argument('parent', type=Path, help='Frozen 10-source/17-class reference prefix; never executed')
    parser.add_argument('out', type=Path, help='Fresh local private evidence directory')
    parser.add_argument('candidate', type=Path, help='Final exact 12-source/20-class candidate prefix')
    args = parser.parse_args()
    os.umask(0o077)
    state = json.loads((HERE / 'PACKAGE-STATE.json').read_text())
    need(state['state'] == 'READY', 'HOLD: final candidate3 pins and review handoff are required; nothing executed')
    identity_path, parent, out, candidate = [path.resolve() for path in
                                            (args.identity, args.parent, args.out, args.candidate)]
    need(sha(identity_path) == IDENTITY_SHA, 'Wrong qualified base identity')
    identity = json.loads(identity_path.read_text())
    forge, jdk, cache = [Path(identity[key]) for key in ('forge', 'jdk', 'cache')]
    protected = [HERE, parent, candidate, identity_path.parent, cache]
    need(not out.exists() and out.parent.is_dir(), 'Use a fresh evidence directory with an existing local parent')
    need(all(not out.is_relative_to(path) and not path.is_relative_to(out) for path in protected), 'Evidence must be disjoint from inputs')
    need(parent != candidate and all(':' not in str(path) for path in protected + [out]), 'Invalid prefix or classpath roots')
    types = subprocess.check_output(['findmnt', '-n', '-o', 'FSTYPE', '-T', str(out.parent)], text=True).split()
    need(types and not any(kind in ('nfs', 'nfs4', 'cifs', 'smb3') for kind in types), 'Active evidence must be local')
    out.mkdir(mode=0o700)

    def save(name, value):
        with (out / name).open('x') as stream:
            json.dump(value, stream, indent=2)
            stream.write('\n')

    def interrupted(signum, frame):
        raise KeyboardInterrupt('Runner interrupted')
    signal.signal(signal.SIGTERM, interrupted)
    process, runs, owned = None, [], []
    started = time.monotonic()
    try:
        for name in ('source', 'classes', 'home', 'tmp', 'reports'):
            (out / name).mkdir(mode=0o700)
        pins = package_pins()
        content = identity_path.parent / 'RUNTIME-CONTENT.json'
        need(sha(content) == CONTENT_SHA, 'Wrong base resource manifest')
        resources = json.loads(content.read_text())
        need(len(resources) == identity['files'] == 59971, 'Wrong base resource inventory')
        need(all(isinstance(pin, dict) and set(pin) == {'bytes', 'sha256'}
                 and type(pin['bytes']) is int and pin['bytes'] >= 0
                 and re.fullmatch('[0-9a-f]{64}', pin['sha256']) is not None for pin in resources.values()),
             'Wrong parent base resource pin schema')
        need(not verify(resources), 'Qualified base resource pin mismatch')
        expected_parent = json.loads((HERE / 'PREFIX-PIN.json').read_text())
        base, more = prefix(parent, expected_parent)
        pins.update(more)
        need(base['content_id'] == PARENT_ID and len(base['sources']) == 10 and len(base['classes']) == 17,
             'Wrong old 10-source/17-class parent reference')
        expected_candidate = json.loads((HERE / 'CANDIDATE-PIN.json').read_text())
        manifest, more = prefix(candidate, expected_candidate)
        pins.update(more)
        need(len(manifest['sources']) == 12 and len(manifest['classes']) == 20, 'Wrong candidate architecture')
        need(set(manifest['sources']) == set(base['sources']) | NEW_SOURCES
             and set(manifest['classes']) == set(base['classes']) | NEW_CLASSES, 'Unexpected added source/class inventory')
        need(all(manifest[key][name] == digest for key in ('sources', 'classes') for name, digest in base[key].items()),
             'All old ten sources/seventeen classes must remain exact')
        need(manifest['sources']['forge-ai/src/main/java/forge/ai/AiController.java'] == AI_CONTROLLER_SHA,
             'AiController source must retain the reviewed e8a7 predicate')
        bundle = {'schema': 9, 'sources': manifest['sources'], 'classes': manifest['classes']}
        need(hashlib.sha256(json.dumps(bundle, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
             == manifest['content_id'], 'Candidate schema9 content identity mismatch')
        pins[str(identity_path)], pins[str(content)] = IDENTITY_SHA, CONTENT_SHA
        for name in NEW_SOURCES:
            need(sha(HERE / 'source' / name) == manifest['sources'][name], 'Full candidate source binding mismatch')
            original, preimage = forge / name, HERE / 'preimage' / name
            need(original.read_bytes() == preimage.read_bytes(), 'Complete Forge source preimage mismatch')
            pins[str(original)] = sha(preimage)
        canonical = json.loads((HERE / 'CANONICAL-PINS.json').read_text())
        need(len(canonical) == 12, 'Exactly twelve complete canonical union programs required')
        for name, pin in canonical.items():
            local, original = HERE / 'canonical' / relative(name), forge / relative(pin['upstream_path'])
            need(local.read_bytes() == original.read_bytes() and sha(local) == pin['sha256']
                 and local.stat().st_size == pin['bytes'], 'Complete canonical program mismatch')
            pins[str(original)] = pin['sha256']
        for _, name, _, _, digest in AUDITS:
            filename = name + '.java'
            need(sha(HERE / filename) == digest, 'Original Java audit source changed')
            shutil.copyfile(HERE / filename, out / 'source' / filename)
            pins[str(out / 'source' / filename)] = digest
        need(not verify(pins), 'Input pin mismatch')
        save('BEFORE.json', {'pins': pins, 'base_resources_verified': 59971, 'parent_reference_executed': False,
                            'runtime_content_id': manifest['content_id'], 'native_rows_required': 22})
        save('EXECUTION-DECLARATION.json', {'fresh_sequential_native_JVMs': 3, 'native_rows_required': 22,
            'audits': [{'label': spec[0], 'rows': spec[2]} for spec in AUDITS], 'candidate_only': True,
            'parent_reference_executed': False, 'baseline_helper_missing_skip': False,
            'shared_compile_and_native_budget_seconds': 300, 'private_protocol8_included': False,
            'separate_no_Artist_two_step_issue_closed': False})
        cp = ':'.join([str(candidate / 'shadow')] + identity['runtime_classpath'])
        env = {'PATH': '/usr/bin:/bin', 'HOME': str(out / 'home'), 'LANG': 'C.UTF-8', 'TMPDIR': str(out / 'tmp')}
        deadline = time.monotonic() + 300

        def launch(label, command, writable):
            nonlocal process
            found = subprocess.run(['ps', '-C', 'java,javac', '-o', 'pid='], capture_output=True, text=True, timeout=5)
            need(found.returncode in (0, 1) and not found.stderr and (found.returncode != 1 or not found.stdout),
                 'Unable to inspect existing JVMs')
            other = found.stdout.split()
            need(all(pid.isdecimal() for pid in other) and len(other) <= 1, 'At most one other host JVM is admitted')
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('Shared compile/native budget exhausted')
            argv = ['timeout', '-k', '5s', str(math.ceil(remaining)), 'bwrap', '--unshare-user', '--unshare-net',
                    '--unshare-pid', '--unshare-ipc', '--unshare-uts', '--die-with-parent', '--new-session']
            for path in dict.fromkeys(['/usr', '/lib', '/lib64', '/bin', '/etc', str(cache),
                                      str(identity_path.parent), str(parent), str(candidate), str(out)]):
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
                owned.append(process.pid)
                save(label + '-LAUNCH.json', {'pid': process.pid, 'other_java_pids': other})
                code = process.wait()
            save(label + '-CLOSED.json', {'exit': code, 'seconds': time.monotonic() - begin})
            process = None
            return code

        compile_code = launch('COMPILE', [str(jdk / 'bin/javac'), '-J-Xmx1500m', '-J-XX:ActiveProcessorCount=1',
            '--release', '17', '-proc:none', '-implicit:none', '-sourcepath', '', '-cp', cp, '-d', str(out / 'classes')]
            + [str(out / 'source' / (spec[1] + '.java')) for spec in AUDITS], ('home', 'tmp', 'classes'))
        if compile_code in (124, 137):
            raise TimeoutError('Compilation exceeded the shared compile/native budget')
        need(compile_code == 0, 'Harness compilation failed; not a policy RED')
        emitted = {path.relative_to(out / 'classes').as_posix() for path in (out / 'classes').rglob('*.class')}
        need(emitted == {'forge/evaluation/' + spec[1] + '.class' for spec in AUDITS}, 'Unexpected compiled audit inventory')
        harness_pins = {str(out / 'classes' / name): sha(out / 'classes' / name) for name in emitted}
        save('HARNESS-CLASS-PINS.json', harness_pins)
        for label, name, _, _, _ in AUDITS:
            need(not verify(pins) and not verify(harness_pins), 'Input changed before mandatory native audit')
            report = out / 'reports' / label
            report.mkdir(mode=0o700)
            main_class = 'forge.evaluation.' + name
            code = launch(label, [str(jdk / 'bin/java'), '-Xmx1500m', '-XX:ActiveProcessorCount=1',
                '-Djava.awt.headless=true', '-Duser.home=' + str(out / 'home'), '-Djava.io.tmpdir=' + str(out / 'tmp'),
                '-Dsentry.dsn=', '-Xlog:class+load=info:file=' + str(report / 'class-load.log') + ':uptime,level,tags',
                '--add-opens', 'java.base/java.lang=ALL-UNNAMED', '-cp', str(out / 'classes') + ':' + cp,
                main_class, str(report)], ('home', 'tmp', 'reports'))
            path = report / 'summary.private.json'
            summary = json.loads(path.read_text()) if path.is_file() else None
            observed, origin_errors = loaded_origins(report / 'class-load.log', manifest, candidate, out / 'classes', main_class)
            errors = []
            try:
                check_summary(label, summary, code)
            except RuntimeError as error:
                errors.append(str(error))
            row = {'label': label, 'native_exit': code, 'summary': summary, 'validation_errors': errors,
                   'origin_errors': origin_errors, 'actual_loaded_override_origins': observed,
                   'physical_payload_count': 20, 'observed_payload_count': len(observed)}
            runs.append(row)
            save(label + '-RESULT.private.json', row)
            if code in (124, 137):
                raise TimeoutError('Native audit exceeded the shared budget; not a draw, win, or policy RED')
        changed, base_changed = verify(pins) + verify(harness_pins), verify(resources)
        prefix(parent, expected_parent)
        prefix(candidate, expected_candidate)
        package_pins()
        need({path.relative_to(out / 'classes').as_posix() for path in (out / 'classes').rglob('*.class')} == emitted,
             'Compiled audit inventory changed')
        save('AFTER.json', {'changed_inputs': changed, 'changed_base_resources': base_changed,
                           'base_resources_checked': 59971, 'parent_reference_executed': False,
                           'no_forced_unused_CounterAi_loading': True})
        need(not changed and not base_changed, 'Pinned inputs changed during gate')
        need(len(runs) == 3 and not any(run['validation_errors'] or run['origin_errors'] for run in runs),
             'All 22 mandatory rows, native exits, and actual new-class origins must validate')
        result_code = 1 if any(run['native_exit'] for run in runs) else 0
        result = {'status': 'STRICT_RED' if result_code else 'PASS', 'exit': result_code,
                  'runtime_content_id': manifest['content_id'], 'seconds': time.monotonic() - started,
                  'runs': runs, 'mandatory_native_rows': 22, 'all_pins_unchanged': True,
                  'parent_reference_executed': False, 'natural_games': 0, 'native_SQL_denial_claim': False,
                  'private_protocol8_included': False, 'separate_no_Artist_two_step_issue_closed': False}
        save('RESULT.json', result)
        print(json.dumps({'status': result['status'], 'exit': result_code, 'mandatory_native_rows': 22,
                          'counts': [run['summary'] for run in runs]}))
        return result_code
    except BaseException as error:
        incomplete = isinstance(error, TimeoutError)
        save('RUNNER-ERROR.private.json', {'type': type(error).__name__, 'message': str(error), 'runs': runs})
        result = {'status': 'INCOMPLETE_SHARED_BUDGET' if incomplete else 'RUNNER_OR_NATIVE_ERROR',
                  'exit': 124 if incomplete else 2, 'native_rows_required': 22, 'native_JVMs_started': len(runs),
                  'not_started': [spec[0] for spec in AUDITS[len(runs):]], 'runs': runs,
                  'no_pass_or_skip_for_missing_helper': True, 'parent_reference_executed': False}
        save('RESULT.json', result)
        print(json.dumps({key: result[key] for key in ('status', 'exit', 'not_started')}))
        return result['exit']
    finally:
        if process is not None and process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        save('CLOSURE.json', {'owned_outer_pids': owned,
                             'all_owned_outer_pids_gone': all(not Path('/proc', str(pid)).exists() for pid in owned),
                             'no_forced_unused_class_loading': True})


if __name__ == '__main__':
    raise SystemExit(main())
