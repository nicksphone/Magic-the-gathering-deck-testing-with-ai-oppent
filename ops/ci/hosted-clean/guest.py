"""Fresh guest packages/build, then the byte-preserved HTTPS client. No host imports."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from host import empty_report, error_class, write_report

ROOT = Path('/tmp/mtg-hosted-clean')
PUBLIC = Path('/public')
HELPERS = PUBLIC / 'ops/ci/hosted-clean'
F = Path('/home/nick/.local/share/mtg-deck-testing-lab/runtimes/app-py312-certifi20261019-20261021-iMMqrycK')
NODE = Path('/opt/node/bin/node')
CADDY = Path('/home/nick/.local/share/mtg-deck-testing-lab/runtimes/caddy2117-e8d654-restored-20261021-xq0syqfu/bin/caddy')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def profile(root):
    result = {}
    for path in [root, *root.rglob('*')]:
        relative = path.relative_to(root).as_posix()
        info = path.lstat()
        row = {'mode': info.st_mode & 0o7777, 'uid': info.st_uid, 'gid': info.st_gid,
               'nlink': info.st_nlink, 'mtime_ns': info.st_mtime_ns}
        if path.is_symlink():
            result[relative] = dict(row, type='symlink', link=os.readlink(path))
        elif path.is_file():
            result[relative] = dict(row, type='regular', sha256=digest(path), bytes=info.st_size)
        elif path.is_dir():
            result[relative] = dict(row, type='directory')
        else:
            raise ValueError('Input type rejected')
    return result


def execution_identity(status):
    fields = dict(line.split(':', 1) for line in status.splitlines() if ':' in line)
    uid, gid = [int(value) for value in fields['Uid'].split()], [int(value) for value in fields['Gid'].split()]
    caps = {name: int(fields[name].strip(), 16) for name in ('CapInh', 'CapPrm', 'CapEff', 'CapBnd', 'CapAmb')}
    if uid != [1001] * 4 or gid != [1001] * 4 or any(caps.values()) or fields['NoNewPrivs'].strip() != '1':
        raise ValueError('Guest identity rejected')
    if fields['Groups'].strip():
        raise ValueError('Supplementary groups rejected')
    return dict(schema=1, uid=uid, gid=gid, caps=caps, no_new_privs=1, parent_pid=int(fields['PPid']))


def os_inputs():
    roots = ('/usr', '/opt', '/etc/apt', '/etc/ssl/certs', '/etc/ssl/openssl.cnf',
             '/etc/ld.so.conf', '/etc/ld.so.conf.d', '/etc/ld.so.cache',
             '/etc/nsswitch.conf', '/etc/passwd', '/etc/group', '/var/lib/dpkg/status', str(CADDY.parent))
    result = {root: profile(Path(root)) for root in roots if Path(root).exists()}
    for rows in result.values():
        for row in rows.values():
            assert row['uid'] == 0
            if row['type'] != 'symlink':
                assert not row['mode'] & 0o002
                assert not (row['gid'] == 1001 and row['mode'] & 0o020)
    return result


def main():
    assert os.environ['MTG_UID'] == os.environ['MTG_GID'] == '1001'
    identity = execution_identity(Path('/proc/self/status').read_text())
    assert os.getuid() == os.geteuid() == os.getgid() == os.getegid() == 1001 and 'VITE_API_BASE_URL' not in os.environ
    (ROOT / 'APP_IDENTITY.json').write_text(json.dumps(identity))
    (ROOT / 'INIT_STATUS.txt').write_text(Path('/proc/1/status').read_text())
    head = os.environ['MTG_HEAD']
    provision = empty_report('provisioning', head)
    life = empty_report('lifecycle', head)
    phase = 'python5'
    build = ROOT / 'build'
    https = ROOT / 'https'
    source_before = None
    runtime_before = None
    started = time.monotonic()

    def run(label, argv, seconds, cwd, env):
        directory = ROOT / 'private-logs'
        directory.mkdir(exist_ok=True)
        with (directory / (label + '.stdout')).open('xb') as out, (directory / (label + '.stderr')).open('xb') as err:
            return subprocess.run(['/usr/bin/timeout', '--signal=TERM', '--kill-after=15s',
                                   str(seconds) + 's', *map(str, argv)], cwd=cwd, env=env,
                                  stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                  timeout=seconds + 20, check=False).returncode

    try:
        assert not build.exists() and not https.exists() and not (F / 'venv').exists()
        assert shutil.disk_usage(ROOT).free >= 5 * 1024**3
        os_before = os_inputs()
        (ROOT / 'OS_TOOL_INPUTS_BEFORE.json').write_text(json.dumps(os_before, sort_keys=True))
        build.mkdir(mode=0o700)
        (build / 'evidence').mkdir()
        shutil.copytree(PUBLIC, build / 'source')
        source = build / 'source'
        source_before = profile(source)
        assert not (source / 'backend/mtg_lab.db').exists()
        # New guest-owned data, not a copied venv or installed node_modules.
        for name in ('admin', 'inputs', 'evidence', 'home', 'tmp'):
            (F / name).mkdir(mode=0o700, exist_ok=True)
        for name in ('bootstrap_pip.py', 'pip_offline.py', 'collect_runtime_metadata.py'):
            shutil.copyfile(HELPERS / 'python5' / name, F / 'admin' / name)
        shutil.copyfile(HELPERS / 'python5/installer.lock', F / 'inputs/installer.lock')
        shutil.copyfile(HELPERS / 'python5/wheels.json', F / 'inputs/WHEEL_DATA_EXPECTED.json')
        shutil.copyfile(source / 'backend/requirements-py312-linux.lock', F / 'inputs/requirements-py312-linux.lock')
        python = F / 'venv/bin/python'
        env = dict(PATH='/usr/bin:/bin', HOME=str(F / 'home'), TMPDIR=str(F / 'tmp'),
                   LC_ALL='C', PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1')
        stages = [
            ('VENV_CREATE', ['/usr/bin/python3', '-I', '-B', '-m', 'venv', '--without-pip', '--symlinks', F / 'venv']),
            ('INSTALLER', [python, '-I', '-B', F / 'admin/bootstrap_pip.py', F]),
            ('APPLICATION', [python, '-I', '-B', F / 'admin/pip_offline.py', F / 'evidence/APPLICATION_IO.json',
                             '--isolated', '--disable-pip-version-check', '--no-cache-dir', 'install', '--no-index',
                             '--find-links', F / 'wheels', '--require-hashes', '--only-binary=:all:', '--no-compile',
                             '--report', F / 'evidence/APPLICATION_REPORT.json', '-r', F / 'inputs/requirements-py312-linux.lock']),
            ('PIP_CHECK', [python, '-I', '-B', F / 'admin/pip_offline.py', F / 'evidence/PIP_CHECK_IO.json',
                           '--isolated', '--disable-pip-version-check', '--no-cache-dir', 'check']),
            ('RUNTIME_METADATA', [python, '-I', '-B', F / 'admin/collect_runtime_metadata.py', F]),
        ]
        python_started = time.monotonic()
        for index, (label, argv) in enumerate(stages):
            remaining = int(300 - (time.monotonic() - python_started))
            assert remaining > 0
            code = run(label, argv, remaining, F, env)
            (F / 'evidence' / (label + '.exit')).write_text(str(code) + '\n')
            provision['python5_exits'][index] = code
            assert code == 0
        metadata = json.loads((F / 'evidence/RUNTIME_METADATA_RESULT.json').read_bytes())
        assert len(metadata['packages']) == 29 and metadata['installed_metadata_matches_exact_29_wheels'] is True
        provision['python_packages'] = 28
        runtime_before = profile(F / 'venv')
        provision['tools'].update(python=digest(Path('/usr/bin/python3.12')), node=digest(NODE),
                                  npm=digest(Path('/opt/node/lib/node_modules/npm/bin/npm-cli.js')),
                                  caddy=digest(CADDY), curl=digest(Path('/usr/bin/curl')),
                                  lock=digest(source / 'backend/requirements-py312-linux.lock'),
                                  system=hashlib.sha256(json.dumps(os_before, sort_keys=True).encode()).hexdigest(),
                                  app_runtime=hashlib.sha256(json.dumps(runtime_before, sort_keys=True).encode()).hexdigest())
        phase = 'build5'
        shutil.copytree(HELPERS / 'actors', build / 'actors')
        for name in ('home', 'tmp'):
            (build / name).mkdir()
        for name in ('npm-user.conf', 'npm-global.conf'):
            (build / 'home' / name).write_text('')
        pins = {name: row['sha256'] for name, row in source_before.items() if 'sha256' in row}
        (build / 'evidence/SOURCE-PLAN-PINS.json').write_text(json.dumps({'regular': pins}))
        (build / 'ACTIVATION.json').write_text(json.dumps({'build': True}))
        observer = build / 'actors/process_observer.py'
        (build / 'BINDINGS.json').write_text(json.dumps({
            'Node': {'path': str(NODE), 'sha256': digest(NODE)},
            'npm_cli': '/opt/node/lib/node_modules/npm/bin/npm-cli.js',
            'npm_cli_sha256': digest(Path('/opt/node/lib/node_modules/npm/bin/npm-cli.js')),
            'process_observer_source': str(observer), 'process_observer_sha256': digest(observer),
            'Git': {'dir': str(ROOT / 'git')},
        }))
        code = run('build5', [python, '-B', build / 'actors/build-only-driver.py'], 1200, build, env)
        names = ('frontend-npm-ci', 'frontend-type', 'frontend-lint', 'frontend-full-test', 'frontend-build')
        for index, name in enumerate(names):
            terminal = build / 'evidence' / name / 'terminal.json'
            if terminal.is_file():
                provision['frontend5_exits'][index] = json.loads(terminal.read_bytes())['actual_cli_rc']
        assert code == 0 and provision['frontend5_exits'] == [0] * 5
        assert all(digest(source / name) == row['sha256'] for name, row in source_before.items() if 'sha256' in row)
        dist = profile(source / 'frontend/dist')
        assert dist
        provision['tools']['dist'] = hashlib.sha256(json.dumps(dist, sort_keys=True).encode()).hexdigest()
        assert os_inputs() == os_before
        provision.update(source_equal=True, runtime_equal=profile(F / 'venv') == runtime_before,
                         verified=True, phase='complete', exit_code=0)
        write_report(ROOT, 'provisioning', provision)
        # Only the existing host controller can attest that bridge removal succeeded.
        (ROOT / 'NETWORK_READY').write_text('true\n')
        deadline = time.monotonic() + 30
        while not (ROOT / 'NETWORK_DISABLED').is_file() and time.monotonic() < deadline:
            time.sleep(.1)
        assert (ROOT / 'NETWORK_DISABLED').read_text() == 'true\n'
        phase = 'https'
        https.mkdir(mode=0o700)
        (https / 'evidence').mkdir()
        shutil.move(str(source), https / 'source')
        shutil.copytree(HELPERS / 'https', https / 'gate-review')
        assert (https / 'gate-review/client-gate.py').is_file()
        (https / 'gate-review/backend-python.py').chmod(0o755)
        shutil.copytree(HELPERS / 'actors', https / 'actors')
        (https / 'ACTIVATION.json').write_text(json.dumps({'https': True}))
        # This serving copy is mode-readonly, not a kernel readonly mount: its owner
        # can chmod it. The original /public input remains a readonly bind mount.
        for path in (https / 'source').rglob('*'):
            if path.is_file() and not path.is_symlink():
                path.chmod(path.stat().st_mode & 0o555)
        for path in sorted((https / 'source').rglob('*'), key=lambda p: len(p.parts), reverse=True):
            if path.is_dir() and not path.is_symlink():
                path.chmod(0o555)
        (https / 'source').chmod(0o555)
        code = run('https', [python, '-B', https / 'actors/native-one-shot-driver.py'], 900, https, env)
        terminal = json.loads((https / 'evidence/runtime-gate/terminal.json').read_bytes())
        closure = json.loads((https / 'evidence/runtime-gate/native-closure.json').read_bytes())
        checks = terminal['checks']
        assert type(checks) is list and checks and all(set(row) == {'check', 'passed'} for row in checks)
        assert all(type(row['check']) is str and type(row['passed']) is bool for row in checks)
        life.update(checks=len(checks), passed=sum(row['passed'] for row in checks),
                    label_count=len({row['check'] for row in checks}), client_exit=terminal['exit'],
                    closure_issues=len(terminal['closure_issues']),
                    services_closed=terminal['pid_closure'] is True,
                    db_closed=bool(closure['files']) and all(row['exit'] == 1 and row['empty'] is True for row in closure['files']),
                    source_equal=all(digest(https / 'source' / name) == row['sha256'] for name, row in source_before.items() if 'sha256' in row),
                    phase='closure', exit_code=code)
        assert code == terminal['exit'] == 0 and terminal['failure_type'] is None
        assert life['checks'] == life['passed'] and life['services_closed'] and life['db_closed']
        assert life['source_equal'] and not life['closure_issues'] and profile(F / 'venv') == runtime_before
        os_after = os_inputs()
        (ROOT / 'OS_TOOL_INPUTS_AFTER.json').write_text(json.dumps(os_after, sort_keys=True))
        assert os_after == os_before
        assert time.monotonic() - started < 3300
        write_report(ROOT, 'lifecycle', life)
        return 0
    except BaseException as exc:
        life.update(phase=phase, exit_code=1, error_class=error_class(exc), verified=False)
        if not provision['verified']:
            provision.update(phase=phase, exit_code=1, error_class=error_class(exc), verified=False)
        write_report(ROOT, 'provisioning', provision)
        write_report(ROOT, 'lifecycle', life)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
