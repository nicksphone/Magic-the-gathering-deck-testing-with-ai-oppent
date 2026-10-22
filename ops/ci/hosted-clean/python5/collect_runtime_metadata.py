"""Parent-invoked post-install metadata and full file inventory, no app imports."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import stat
import sys

root = Path(sys.argv[1]).resolve()
expected = json.loads((root / 'inputs/WHEEL_DATA_EXPECTED.json').read_bytes())['wheel_rows']
venv = root / 'venv'
assert Path(sys.prefix).resolve() == venv
assert sys.implementation.name == 'cpython' and sys.version_info[:3] == (3, 12, 3)
assert platform.system() == 'Linux' and platform.machine() == 'x86_64'
assert platform.libc_ver() == ('glibc', '2.39')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def normalize(name):
    return name.lower().replace('_', '-').replace('.', '-')


versions = {}
site = venv / 'lib/python3.12/site-packages'
for dist in importlib.metadata.distributions(path=[str(site)]):
    name = normalize(dist.metadata['Name'])
    assert name not in versions and name in expected
    assert dist.version == expected[name]['version']
    paths = [dist.locate_file(p) for p in dist.files or [] if str(p).endswith('.dist-info/METADATA')]
    assert len(paths) == 1 and paths[0].resolve().is_relative_to(site.resolve())
    assert sha(paths[0].read_bytes()) == expected[name]['metadata_sha256']
    versions[name] = dist.version
assert set(versions) == set(expected) and len(versions) == 29

for label, names in [('INSTALLER', {'pip'}), ('APPLICATION', set(expected) - {'pip'})]:
    report = json.loads((root / 'evidence' / (label + '_REPORT.json')).read_bytes())
    installed = report['install']
    assert len(installed) == len(names)
    found = set()
    for row in installed:
        name = normalize(row['metadata']['name'])
        assert name not in found and name in names
        assert row['metadata']['version'] == expected[name]['version']
        assert row['download_info']['archive_info']['hashes']['sha256'] == expected[name]['sha256']
        assert row['download_info']['url'].startswith('file:')
        found.add(name)
    assert found == names
assert (root / 'evidence/PIP_CHECK.exit').read_text().strip() == '0'

entries = {}
for base, dirs, files in os.walk(venv, followlinks=False):
    for name in sorted(dirs + files):
        path = Path(base) / name
        key = path.relative_to(venv).as_posix()
        info = path.lstat()
        common = {'mode': stat.S_IMODE(info.st_mode), 'mtime_ns': info.st_mtime_ns,
                  'uid': info.st_uid, 'gid': info.st_gid}
        if path.is_symlink():
            entries[key] = dict(common, type='symlink', target=os.readlink(path))
        elif path.is_dir():
            entries[key] = dict(common, type='directory')
        else:
            assert stat.S_ISREG(info.st_mode)
            entries[key] = dict(common, type='regular', bytes=info.st_size, sha256=sha(path.read_bytes()))
inventory = json.dumps(entries, indent=2, sort_keys=True) + '\n'
(root / 'evidence/RUNTIME_INVENTORY.json').write_text(inventory)
summary = {'python': sys.version, 'executable': sys.executable, 'base_prefix': sys.base_prefix,
           'venv': str(venv), 'packages': versions, 'pip_check_exit': 0,
           'installer_and_app_report_wheel_hashes_verified': True,
           'installed_metadata_matches_exact_29_wheels': True,
           'inventory_sha256': sha(inventory.encode()),
           'inventory_counts': {kind: sum(row['type'] == kind for row in entries.values())
                                for kind in ('regular', 'directory', 'symlink')},
           'certificate_regressions': 'PENDING_SEPARATE_GATE',
           'offline_HTTP_suite': 'PENDING_SEPARATE_GATE', 'runtime_adoption': 'NOT_AUTHORIZED'}
(root / 'evidence/RUNTIME_METADATA_RESULT.json').write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n')
print(json.dumps(summary, indent=2, sort_keys=True))
