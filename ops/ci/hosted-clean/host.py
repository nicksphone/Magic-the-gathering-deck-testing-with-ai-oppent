"""One manually granted, disposable hosted-VM container; never run on this workstation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import time

IMAGE = 'ubuntu@sha256:a2d43bffc46670d7108bb3c0468c67c5557c4c92e83e1e34cbff1322ad1b94dc'
PHASES = {'prepare', 'provision', 'python5', 'build5', 'https', 'closure', 'complete', 'cancelled'}
ERRORS = {None, 'AssertionError', 'PermissionError', 'FileNotFoundError', 'TimeoutExpired',
          'ValueError', 'StageError', 'OtherError', 'Cancelled'}
HEX40 = re.compile(r'[0-9a-f]{40}\Z')
HEX64 = re.compile(r'[0-9a-f]{64}\Z')
BASE = {'schema', 'head', 'base_image', 'phase', 'exit_code', 'error_class', 'verified'}
EXTRA = {
    'provisioning': {'python_packages', 'python5_exits', 'frontend5_exits', 'tools', 'source_equal', 'runtime_equal'},
    'lifecycle': {'checks', 'passed', 'label_count', 'client_exit', 'closure_issues', 'db_closed',
                  'services_closed', 'container_closed', 'cgroup_empty', 'source_equal', 'diagnostic'},
}
TOOLS = {'python', 'node', 'npm', 'caddy', 'curl', 'lock', 'dist', 'system', 'app_runtime'}
DIAGNOSTIC_ERRORS = ERRORS | {'RuntimeError', 'KeyError', 'TypeError', 'IndexError', 'OSError',
                             'TimeoutError', 'CalledProcessError', 'JSONDecodeError'}
DIAGNOSTIC_ORIGINS = {'none', 'client', 'driver', 'guest', 'outer', 'unknown'}


def empty_diagnostic():
    return dict(origin='none', error_class=None, line=None, last_failed_check_sha256=None)


def integer(value, low, high, nullable=False):
    if nullable and value is None:
        return
    if type(value) is not int or not low <= value <= high:
        raise ValueError('Integer rejected')


def empty_report(kind, head):
    row = dict(schema=1, head=head, base_image=IMAGE, phase='prepare', exit_code=None,
               error_class=None, verified=False)
    if kind == 'provisioning':
        row.update(python_packages=0, python5_exits=[None] * 5, frontend5_exits=[None] * 5,
                   tools=dict.fromkeys(sorted(TOOLS)), source_equal=False, runtime_equal=False)
    elif kind == 'lifecycle':
        row.update(checks=0, passed=0, label_count=0, client_exit=None, closure_issues=0,
                   db_closed=False, services_closed=False, container_closed=False,
                   cgroup_empty=False, source_equal=False, diagnostic=empty_diagnostic())
    else:
        raise ValueError('Kind rejected')
    return row


def validate_report(row, kind):
    if kind not in EXTRA or type(row) is not dict or set(row) != BASE | EXTRA[kind]:
        raise ValueError('Closed schema rejected')
    if type(row['schema']) is not int or row['schema'] != 1 or not HEX40.fullmatch(row['head']):
        raise ValueError('Binding rejected')
    if row['base_image'] != IMAGE or row['phase'] not in PHASES or row['error_class'] not in ERRORS:
        raise ValueError('Enum rejected')
    integer(row['exit_code'], -255, 255, True)
    booleans = {'verified', 'source_equal'}
    if kind == 'provisioning':
        booleans.add('runtime_equal')
        integer(row['python_packages'], 0, 28)
        for name in ('python5_exits', 'frontend5_exits'):
            if type(row[name]) is not list or len(row[name]) != 5:
                raise ValueError('Stage vector rejected')
            for value in row[name]:
                integer(value, -255, 255, True)
        if type(row['tools']) is not dict or set(row['tools']) != TOOLS:
            raise ValueError('Tools rejected')
        for digest in row['tools'].values():
            if digest is not None and (type(digest) is not str or not HEX64.fullmatch(digest)):
                raise ValueError('Digest rejected')
    else:
        booleans |= {'db_closed', 'services_closed', 'container_closed', 'cgroup_empty'}
        for name in ('checks', 'passed', 'label_count', 'closure_issues'):
            integer(row[name], 0, 10000)
        integer(row['client_exit'], -255, 255, True)
        if row['passed'] > row['checks'] or row['label_count'] > row['checks']:
            raise ValueError('Count rejected')
        diagnostic = row['diagnostic']
        if type(diagnostic) is not dict or set(diagnostic) != set(empty_diagnostic()):
            raise ValueError('Diagnostic schema rejected')
        if (type(diagnostic['origin']) is not str or diagnostic['origin'] not in DIAGNOSTIC_ORIGINS or
                diagnostic['error_class'] is not None and (type(diagnostic['error_class']) is not str
                or diagnostic['error_class'] not in DIAGNOSTIC_ERRORS)):
            raise ValueError('Diagnostic enum rejected')
        integer(diagnostic['line'], 1, 100000, True)
        value = diagnostic['last_failed_check_sha256']
        if value is not None and (type(value) is not str or not HEX64.fullmatch(value)):
            raise ValueError('Diagnostic digest rejected')
        if len(json.dumps(diagnostic).encode()) > 512:
            raise ValueError('Diagnostic size rejected')
    if any(type(row[name]) is not bool for name in booleans):
        raise ValueError('Boolean rejected')
    if row['verified']:
        good = row['phase'] == 'complete' and row['exit_code'] == 0 and row['error_class'] is None
        good = good and all(row[name] for name in booleans)
        if kind == 'provisioning':
            good = good and row['python_packages'] == 28 and all(row['tools'].values())
            good = good and row['python5_exits'] == row['frontend5_exits'] == [0] * 5
        else:
            good = good and row['client_exit'] == 0 and row['checks'] == row['passed'] > 0
            good = good and row['label_count'] > 0 and row['closure_issues'] == 0
            good = good and row['diagnostic']['error_class'] is None
            good = good and row['diagnostic']['last_failed_check_sha256'] is None
        if not good:
            raise ValueError('False qualification rejected')
    return row


def error_class(error):
    name = type(error).__name__
    return name if name in ERRORS else 'OtherError'


def outer_failure(lifecycle, failure, *, cancelled):
    lifecycle.update(verified=False, phase='cancelled' if cancelled else lifecycle['phase'],
                     exit_code=1, error_class='Cancelled' if cancelled else
                     lifecycle['error_class'] or error_class(failure))
    if lifecycle['diagnostic']['origin'] == 'none':
        lifecycle['diagnostic'] = dict(empty_diagnostic(), origin='outer',
                                        error_class=lifecycle['error_class'])


def write_report(root, kind, row):
    validate_report(row, kind)
    data = (json.dumps(row, sort_keys=True) + '\n').encode()
    if len(data) > 65536:
        raise ValueError('Report size rejected')
    if root.is_symlink() or root.resolve() != root:
        raise ValueError('Report directory rejected')
    root.mkdir(parents=True, exist_ok=True)
    path = root / (kind + '.json')
    if path.is_symlink() or path.exists() and (not path.is_file() or path.stat().st_nlink != 1):
        raise ValueError('Report link rejected')
    path.write_bytes(data)


class StageError(Exception):
    def __init__(self, code):
        self.code = code


def checked(command, argv, seconds):
    code = command(argv, timeout=seconds)
    if code:
        raise StageError(code)


def stop_owned(command, cid, head, inspect):
    if type(cid) is not str or not HEX64.fullmatch(cid):
        raise ValueError('CID rejected')
    state = inspect(cid)
    if state['Id'] != cid or state['Config']['Labels'].get('mtg.clean.head') != head:
        raise ValueError('Ownership rejected')
    return command(['docker', 'stop', '--time', '15', cid], timeout=30)


def container_command(public, work, head):
    if not HEX40.fullmatch(head):
        raise ValueError('Head rejected')
    for path in (public, work):
        if not Path(path).is_absolute() or ',' in path or '\n' in path:
            raise ValueError('Mount rejected')
    return ['docker', 'create', '--init', '--platform=linux/amd64', '--restart=no', '--network=bridge',
            '--memory=4g', '--memory-swap=4g', '--cpus=2', '--pids-limit=256',
            '--log-driver=none', '--security-opt=no-new-privileges', '--cgroupns=private',
            '--cap-drop=ALL', '--cap-add=CHOWN', '--cap-add=DAC_OVERRIDE',
            '--cap-add=FOWNER', '--cap-add=FSETID', '--cap-add=SETUID',
            '--cap-add=SETGID', '--cap-add=SETPCAP', '--cap-add=KILL',
            '--ulimit=fsize=536870912:536870912', '--label=mtg.clean.head=' + head,
            '--env=MTG_HEAD=' + head, '--env=MTG_UID=' + str(os.getuid()),
            '--env=MTG_GID=' + str(os.getgid()),
            '--mount=type=bind,src=' + public + ',dst=/public,readonly',
            '--mount=type=bind,src=' + work + ',dst=/tmp/mtg-hosted-clean',
            IMAGE, '/bin/bash', '/public/ops/ci/hosted-clean/entry.sh']


def birth(pid):
    return Path('/proc/' + str(pid) + '/stat').read_text().rsplit(')', 1)[1].split()[19]


def cgroup_path(membership, cid):
    if not HEX64.fullmatch(cid):
        raise ValueError('CID rejected')
    rows = [line[3:] for line in membership.splitlines() if line.startswith('0::')]
    if len(rows) != 1 or not rows[0].startswith('/') or '..' in Path(rows[0]).parts or cid not in rows[0]:
        raise ValueError('Owned cgroup rejected')
    return Path('/sys/fs/cgroup') / rows[0].lstrip('/')


def read_guest_reports(root, head):
    result = {}
    for kind in EXTRA:
        path = root / (kind + '.json')
        if not path.exists():
            continue
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
            raise ValueError('Guest report rejected')
        row = validate_report(json.loads(path.read_bytes()), kind)
        if row['head'] != head:
            raise ValueError('Guest head rejected')
        result[kind] = row
    return result


def admit_storage(total, free):
    integer(total, 0, 16 * 1024**3)
    integer(free, 5 * 1024**3, 2**63 - 1)


def logical_bytes(root):
    return sum(path.lstat().st_size for path in root.rglob('*') if path.is_file() and not path.is_symlink())


def validate_index(tree, index):
    maps = []
    for data, is_tree in ((tree, True), (index, False)):
        if not data or len(data) > 4 * 1024**2 or not data.endswith(b'\0'):
            raise ValueError('Index records rejected')
        rows = {}
        for record in data[:-1].split(b'\0'):
            try:
                metadata, name = record.split(b'\t', 1)
                mode, second, third = metadata.split(b' ')
            except ValueError:
                raise ValueError('Index record rejected') from None
            oid = third if is_tree else second
            if (mode not in (b'100644', b'100755', b'120000') or
                    (second != b'blob' if is_tree else third != b'0') or
                    not re.fullmatch(b'[0-9a-f]{40}', oid) or not name or name in rows):
                raise ValueError('Index entry rejected')
            rows[name] = (mode, oid)
        maps.append(rows)
    if maps[0] != maps[1]:
        raise ValueError('Index differs from HEAD')
    return len(maps[0])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--public', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--capsule', type=Path, required=True)
    parser.add_argument('--head', required=True)
    args = parser.parse_args()
    # Never silently use a developer daemon or a self-hosted runner.
    if os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted':
        raise ValueError('Hosted execution only')
    assert os.getuid() == os.getgid() == 1001
    public, work, head = args.public.resolve(), args.work, args.head
    if work.exists() or not work.is_absolute() or work.resolve() != work or not HEX40.fullmatch(head):
        raise ValueError('Fresh binding rejected')
    assert shutil.disk_usage(work.parent).free >= 5 * 1024**3
    assert (public / 'ops/caddy/run.py').is_file() and not (public / 'backend/mtg_lab.db').exists()
    work.mkdir(mode=0o700)
    capsule = args.capsule.resolve()
    assert (capsule / 'objects').is_dir() and not (capsule / 'objects/info/alternates').exists()
    shutil.copytree(capsule, work / 'git')
    private = work.parent / (work.name + '-controller-private')
    assert not private.exists()
    private.mkdir(mode=0o700)
    (private / 'home').mkdir()
    (private / 'docker-config').mkdir()
    output = work.parent / (work.name + '-public-artifact')
    records = {kind: empty_report(kind, head) for kind in EXTRA}
    cancelled = False
    cid = None
    initial_pid = None
    initial_birth = None
    cgroup = None
    forced = False
    failure = None
    started = time.monotonic()
    command_env = dict(PATH='/usr/bin:/bin', HOME=str(private / 'home'), LANG='C.UTF-8',
                       DOCKER_CONFIG=str(private / 'docker-config'),
                       GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null', GIT_OPTIONAL_LOCKS='0')

    def interrupt(signum, frame):
        nonlocal cancelled
        if not cancelled:
            cancelled = True
            raise InterruptedError('Cancelled')

    signal.signal(signal.SIGTERM, interrupt)
    signal.signal(signal.SIGINT, interrupt)

    def capture(argv, timeout=30, limit=65536):
        with (private / 'commands.stderr').open('ab') as err:
            result = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=err, timeout=timeout, check=False, env=command_env)
        if len(result.stdout) > limit:
            raise ValueError('Command output bound')
        if result.returncode:
            raise StageError(result.returncode)
        return result.stdout

    def command(argv, timeout=30):
        with (private / 'commands.stdout').open('ab') as out, (private / 'commands.stderr').open('ab') as err:
            return subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                  timeout=timeout, check=False, env=command_env).returncode

    def inspect(value):
        return json.loads(capture(['docker', 'inspect', value]))[0]

    try:
        assert capture(['git', '--git-dir=' + str(work / 'git'), 'rev-parse', 'HEAD']).decode().strip() == head
        index = work / 'git/index'
        assert index.is_file() and not index.is_symlink() and index.stat().st_nlink == 1
        git = ['git', '--git-dir=' + str(work / 'git')]
        tracked = validate_index(capture([*git, 'ls-tree', '-r', '-z', 'HEAD'], limit=4 * 1024**2),
                                 capture([*git, 'ls-files', '--stage', '-z'], limit=4 * 1024**2))
        (private / 'CAPSULE_ADMISSION.json').write_text(json.dumps({'head': head, 'tracked': tracked, 'index_matches_tree': True}))
        # Pull is a separately timed provisioning operation; no mutable image tag.
        checked(command, ['docker', 'pull', '--platform=linux/amd64', IMAGE], 300)
        raw = capture(container_command(str(public), str(work), head)).decode('ascii').strip()
        if not HEX64.fullmatch(raw):
            raise ValueError('Created CID rejected')
        cid = raw
        (private / 'CID').write_text(cid + '\n')
        checked(command, ['docker', 'start', cid], 30)
        state = inspect(cid)
        assert state['Image'] == 'sha256:6277ab668b2ad3c3ab851d370faa1690d324b30db29d342527f61fed28f20f36'
        initial_pid = state['State']['Pid']
        integer(initial_pid, 1, 2**31 - 1)
        initial_birth = birth(initial_pid)
        membership = Path(f'/proc/{initial_pid}/cgroup').read_text()
        cgroup = cgroup_path(membership, cid)
        assert cgroup.resolve().is_relative_to(Path('/sys/fs/cgroup'))
        (private / 'initial-process.json').write_text(json.dumps(dict(pid=initial_pid, birth=initial_birth, cgroup=str(cgroup))))
        disconnected = False
        admitted = False
        while state['State']['Running']:
            if cancelled or time.monotonic() - started > 4500:
                raise TimeoutError('Cancelled or outer deadline')
            if (work / 'PROVISION_READY').is_file() and not admitted:
                usage = json.loads(capture(['docker', 'inspect', '--size', cid]))[0]['SizeRw']
                image_size = json.loads(capture(['docker', 'image', 'inspect', IMAGE]))[0]['Size']
                total = usage + image_size + logical_bytes(work) + logical_bytes(public) + logical_bytes(capsule)
                admit_storage(total, shutil.disk_usage(work).free)
                (private / 'provision-admission.json').write_text(json.dumps(dict(total_bytes=total, free_bytes=shutil.disk_usage(work).free)))
                (work / 'PROVISION_ADMITTED').write_text('true\n')
                admitted = True
            ready = work / 'NETWORK_READY'
            if ready.is_file() and not disconnected:
                checked(command, ['docker', 'network', 'disconnect', 'bridge', cid], 30)
                assert not inspect(cid)['NetworkSettings']['Networks']
                (work / 'NETWORK_DISABLED').write_text('true\n')
                disconnected = True
            time.sleep(1)
            state = inspect(cid)
        actual_exit = int(capture(['docker', 'wait', cid], 30).strip())
        records.update(read_guest_reports(work, head))
        if actual_exit or not admitted or not disconnected or state['State'].get('OOMKilled'):
            raise StageError(actual_exit or 1)
        assert records['provisioning']['verified']
    except BaseException as exc:
        failure = exc
    finally:
        try:
            records.update(read_guest_reports(work, head))
        except BaseException as exc:
            failure = failure or exc
        if cid:
            try:
                if inspect(cid)['State']['Running']:
                    forced = True
                    stop_owned(command, cid, head, inspect)
                state = inspect(cid)
                gone = initial_pid is not None and not Path(f'/proc/{initial_pid}').exists()
                empty = cgroup is not None and (not cgroup.exists() or not any(
                    path.read_text().strip() for path in cgroup.rglob('cgroup.procs')))
                closed = not state['State']['Running'] and gone and empty and not state['State'].get('OOMKilled')
                records['lifecycle'].update(container_closed=closed, cgroup_empty=bool(empty))
                (private / 'OUTER_CLOSURE.json').write_text(json.dumps({
                    'container_exit': state['State'].get('ExitCode'),
                    'container_running': state['State']['Running'],
                    'known_init_pid': initial_pid, 'known_init_birth': initial_birth,
                    'init_absent': gone, 'cgroup_empty': bool(empty),
                    'forced_stop': forced, 'oom_killed': state['State'].get('OOMKilled'),
                }))
                if closed:
                    checked(command, ['docker', 'rm', cid], 30)
                else:
                    failure = failure or ValueError('Outer closure unknown')
            except BaseException as exc:
                failure = failure or exc
        lifecycle = records['lifecycle']
        if failure and not records['provisioning']['verified']:
            records['provisioning'].update(
                phase='cancelled' if cancelled else 'provision',
                exit_code=failure.code if isinstance(failure, StageError) else 1,
                error_class='Cancelled' if cancelled else error_class(failure))
        if failure or forced or cancelled:
            outer_failure(lifecycle, failure, cancelled=cancelled)
        else:
            lifecycle.update(phase='complete', exit_code=0, error_class=None, verified=True)
        try:
            validate_report(lifecycle, 'lifecycle')
        except ValueError:
            lifecycle.update(verified=False, exit_code=1, error_class='ValueError')
        for kind, row in records.items():
            write_report(output, kind, row)
    print('Hosted clean terminal: ' + ('qualified' if lifecycle['verified'] else 'UNQUALIFIED'))
    return 0 if lifecycle['verified'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
