"""Backend-only ephemeral hosted-runner capacity admission, before private inputs."""
import json
import os
from pathlib import Path
import stat
import subprocess
import sys


# Path pins from actions/runner-images SDK installers; never accept CLI roots.
SDK_ROOTS = (Path('/usr/share/dotnet'), Path('/usr/local/lib/android'))
MIN_FREE_BYTES = 20 * 1024 ** 3  # Proposed admission policy, not a measured suite peak.
SOURCE = Path(__file__).resolve().parents[2]


class CapacityError(RuntimeError):
    pass


def ubuntu24():
    values = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines()
                  if '=' in line and not line.startswith('#'))
    return (values.get('ID', '').strip('"') == 'ubuntu'
            and values.get('VERSION_ID', '').strip('"') == '24.04')


def available_bytes(path):
    filesystem = os.statvfs(path)
    return filesystem.f_bavail * filesystem.f_frsize


def validated_directory(value):
    path = Path(value)
    if not path.is_absolute() or path.resolve() != path or not path.is_dir():
        raise CapacityError('runner-path')
    return path


def validate_sdk(path, protected):
    if path not in SDK_ROOTS:
        raise CapacityError('sdk-path')
    if any(path.is_relative_to(p) or p.is_relative_to(path) for p in protected):
        raise CapacityError('protected-overlap')
    if not os.path.lexists(path):
        return None
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise CapacityError('sdk-path')
    info = os.lstat(path)
    # GitHub's post-deployment configuration sets /usr/share recursively to 0777.
    shared_dotnet = path == SDK_ROOTS[0] and stat.S_IMODE(info.st_mode) == 0o777
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != 0
            or (info.st_mode & 0o022 and not shared_dotnet)):
        raise CapacityError('sdk-path')
    return info.st_dev, info.st_ino


def preflight(env):
    expected = dict(GITHUB_ACTIONS='true', RUNNER_ENVIRONMENT='github-hosted',
        RUNNER_OS='Linux', RUNNER_ARCH='X64', GITHUB_JOB='backend',
        GITHUB_REPOSITORY='nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent',
        MTG_CI_CAPACITY_SCOPE='backend-sdk-cleanup')
    if any(env.get(key) != value for key, value in expected.items()):
        raise CapacityError('hosted-backend-context')
    if not ubuntu24():
        raise CapacityError('runner-image')
    workspace, temporary, toolcache = (validated_directory(env.get(key, '')) for key in
        ('GITHUB_WORKSPACE', 'RUNNER_TEMP', 'RUNNER_TOOL_CACHE'))
    if workspace != SOURCE or Path.cwd() != workspace:
        raise CapacityError('workspace-binding')
    protected = (workspace, workspace.parent, temporary, toolcache,
                 Path(sys.executable).resolve(), Path(sys.prefix).resolve())

    def measure(phase):
        free = {name: available_bytes(path) for name, path in
                [('workspace', workspace), ('runner_temp', temporary)]}
        print('CI_BACKEND_CAPACITY ' + json.dumps(dict(phase=phase,
            floor_bytes=MIN_FREE_BYTES, available_bytes=free), sort_keys=True), flush=True)
        return all(value >= MIN_FREE_BYTES for value in free.values())

    # A passing initial floor does not bound the full suite's later scratch use.
    measure('before')
    # Validate the whole fixed plan before performing even the first deletion.
    plan = [(path, validate_sdk(path, protected)) for path in SDK_ROOTS]
    for path, identity in plan:
        if identity is None:
            print('CI_BACKEND_CAPACITY_SDK_ABSENT ' + str(path), flush=True)
            continue
        if validate_sdk(path, protected) != identity:
            raise CapacityError('sdk-identity')
        print('CI_BACKEND_CAPACITY_RECLAIM ' + str(path), flush=True)
        try:
            subprocess.run(['/usr/bin/sudo', '-n', '/usr/bin/rm', '-rf',
                '--one-file-system', '--', str(path)], check=True, timeout=120,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError) as error:
            raise CapacityError('sdk-cleanup') from error
        if os.path.lexists(path):
            raise CapacityError('sdk-remains')
    if not measure('after'):
        raise CapacityError('byte-floor')
    print('CI_BACKEND_CAPACITY_READY cleanup=fixed-unused-sdks', flush=True)


def main():
    try:
        if sys.argv[1:]:
            raise CapacityError('arguments')
        preflight(os.environ)
    except CapacityError as error:
        print('CI_BACKEND_CAPACITY_REJECTED reason=' + str(error), flush=True)
        return 2
    except OSError:
        print('CI_BACKEND_CAPACITY_REJECTED reason=filesystem-observation', flush=True)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
