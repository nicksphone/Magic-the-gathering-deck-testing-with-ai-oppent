"""Local real-owner/fuser controls, NOT hosted or kernel-wide closure proof."""
import json
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch
import unittest


SCRIPTS = Path(__file__).resolve().parents[1]
SCENARIO = r'''
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import patch
from urllib.parse import unquote, urlsplit

scripts, base = map(Path, sys.argv[1:3])
root = base / 'mtg-backend-work-Ab12cd' / 'source'
root.mkdir(parents=True)
for name in ('persistence/__init__.py', 'persistence/db.py', 'persistence/capacity.py',
             'persistence/models.py', 'persistence/job_retention.py',
             'analytics/__init__.py', 'analytics/resource_budget.py',
             'knowledge/__init__.py', 'knowledge/models.py',
             'scripts/verify_storage_restore.py'):
    target = root / 'backend' / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(scripts.parents[1] / 'backend' / name, target)
for name in ('.private', '.private-choice-audit-source'):
    (root / name).write_text(str(root))
os.environ.update(RUNNER_TEMP=str(base), MTG_ISOLATED_TEST_ROOT=str(root),
                  MTG_CI_PASSED_SNAPSHOT_CLEANUP='1')
os.environ.pop('MTG_DATABASE_PATH', None)
def deny(event, args):
    if event.startswith('socket.'):
        raise RuntimeError('SOCKET_DENIED')
    if event == 'sqlite3.connect':
        value = args[0]
        if str(value).startswith('file:'):
            parsed = urlsplit(value)
            if parsed.netloc or parsed.query != 'mode=ro':
                raise RuntimeError('FOREIGN_SQL_DENIED')
            value = unquote(parsed.path)
        path = Path(value)
        if not path.is_absolute() or path.parent != root / 'backend':
            raise RuntimeError('FOREIGN_SQL_DENIED')
    if event in ('os.system', 'os.posix_spawn'):
        raise RuntimeError('PROCESS_DENIED')
    if event == 'subprocess.Popen' and (args[0] != '/usr/bin/fuser' or
            not all(Path(value).is_absolute() and Path(value).parent == root / 'backend'
                    for value in args[1][1:])):
        raise RuntimeError('PROCESS_DENIED')
sys.addaudithook(deny)
sys.path.insert(0, str(root / 'backend'))
from persistence import db, capacity
from sqlmodel import SQLModel
SQLModel.metadata.create_all(db.engine, tables=[table for table in SQLModel.metadata.sorted_tables
    if table.name not in {'resourcecapacity', 'resourcereservation'}])
path = scripts / 'ci_backend_snapshot_cleanup.py'
if path.exists():
    spec = importlib.util.spec_from_file_location('cleanup', path)
    plugin = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(plugin)
else:
    # Honest baseline: existing CI retains every successful startup backup.
    class Retain:
        def before_setup(self, item): pass
        def after_report(self, item, report): pass
    plugin = ModuleType('baseline_retention')
    plugin.SnapshotCleanup = lambda: Retain()
    plugin.owned_children_closed = lambda _: True

results = {}
observations = []
if hasattr(plugin, 'subprocess'):
    real_run = plugin.subprocess.run
    def observe(*args, **kwargs):
        try:
            result = real_run(*args, **kwargs)
        except Exception as exc:
            observations.append({'exception': type(exc).__name__})
            raise
        observations.append({'status': result.returncode,
                             'stdout_bytes': len(result.stdout), 'stderr_bytes': len(result.stderr)})
        return result
    plugin.subprocess.run = observe
for case in ('closed', 'failed_setup', 'failed_call', 'failed_teardown', 'skipped',
             'xfail', 'live', 'changed', 'preexisting', 'foreign', 'unregistered',
             'open_snapshot', 'open_source', 'visibility', 'tool', 'symlink',
             'hardlink', 'producer', 'wrong_pid', 'uncertain', 'duplicate', 'disabled',
             'open_journal', 'fuser_stdout', 'fuser_stderr', 'fuser_status', 'fuser_timeout',
             'known_child', 'workspace_marker'):
    if case == 'disabled': os.environ['MTG_CI_PASSED_SNAPSHOT_CLEANUP'] = '0'
    if case == 'workspace_marker': (root / '.private').unlink()
    observations.clear()
    cleanup = plugin.SnapshotCleanup()
    os.environ['MTG_CI_PASSED_SNAPSHOT_CLEANUP'] = '1'
    (root / '.private').write_text(str(root))
    item = SimpleNamespace(nodeid=case)
    owner = capacity.DatabaseOwner(db.engine).acquire()
    backup = owner.path.with_name(owner.path.name + '.before-capacity-' + owner.epoch + '.db')
    if case != 'preexisting':
        cleanup.before_setup(item)
    capacity.initialize_capacity(owner, backup)
    owner.open_admission()
    if case == 'preexisting':
        cleanup.before_setup(item)
    def report(phase, outcome='passed', xfail=False):
        row = SimpleNamespace(when=phase, outcome=outcome)
        if xfail: row.wasxfail = 'synthetic xfail'
        cleanup.after_report(item, row)
    if case == 'foreign':
        old = db.DATABASE_PATH
        db.DATABASE_PATH = root / 'backend' / 'other.db'
    if case == 'unregistered':
        with capacity._OWNER_LOCK: del capacity._OWNERS[db.engine]
    report('setup', 'failed' if case == 'failed_setup' else 'passed')
    if case == 'foreign': db.DATABASE_PATH = old
    if case == 'unregistered':
        with capacity._OWNER_LOCK: capacity._OWNERS[db.engine] = owner
    if case == 'duplicate': report('setup')
    report('call', 'failed' if case == 'failed_call' else 'skipped' if case == 'skipped'
           else 'passed', xfail=case == 'xfail')
    if case != 'live':
        owner.fence_admission()
        owner.close()
    held = None
    if case == 'changed': backup.write_bytes(backup.read_bytes() + b'changed')
    if case == 'symlink':
        saved = backup.with_suffix('.saved')
        backup.rename(saved)
        backup.symlink_to(saved)
    if case == 'hardlink': os.link(backup, backup.with_suffix('.linked'))
    if case == 'producer': owner.producers['synthetic'] = object()
    if case == 'wrong_pid': owner.pid += 1
    if case == 'uncertain': owner.uncertain = True
    if case in ('open_snapshot', 'open_source'):
        held = (backup if case == 'open_snapshot' else owner.path).open('rb')
    if case == 'open_journal':
        journal = Path(str(owner.path) + '-journal')
        journal.write_bytes(b'synthetic journal')
        held = journal.open('rb')
    if case == 'known_child' and hasattr(cleanup, 'states'):
        cleanup.states[case]['children'].add(os.getpid())
    # Ordinary positive/holder cases use real fuser and real owned-child observation.
    def teardown():
        if case == 'tool' and hasattr(plugin, 'subprocess'):
            with patch.object(plugin.subprocess, 'run', side_effect=FileNotFoundError) as probe:
                report('teardown')
                assert probe.call_count == 1
        elif case.startswith('fuser_') and hasattr(plugin, 'subprocess'):
            if case == 'fuser_timeout':
                fault = {'side_effect': plugin.subprocess.TimeoutExpired('fuser', 5)}
            else:
                fault = {'return_value': SimpleNamespace(
                    returncode=0 if case == 'fuser_status' else 1,
                    stdout=b'123' if case == 'fuser_stdout' else b'',
                    stderr=b'permission denied' if case == 'fuser_stderr' else b'')}
            with patch.object(plugin.subprocess, 'run', **fault) as probe:
                report('teardown')
                assert probe.call_count == 1
        else:
            report('teardown', 'failed' if case == 'failed_teardown' else 'passed')
    if case == 'visibility':
        with patch.object(plugin, 'owned_children_closed', side_effect=PermissionError) as probe:
            teardown()
            if hasattr(cleanup, 'states'): assert probe.call_count == 1
    else:
        teardown()
    results[case] = {'removed': not backup.exists(), 'default_retained': owner.path.is_file(),
                     'fuser': list(observations)}
    if held: held.close()
    if case == 'open_journal': journal.unlink()
    if case == 'live':
        owner.fence_admission()
        owner.close()
    if case == 'producer': owner.producers.clear()
print(json.dumps(results, sort_keys=True))
'''


class SnapshotCleanupTests(unittest.TestCase):
    def test_real_closed_owner_only_passed_snapshot_is_removed(self):
        with tempfile.TemporaryDirectory(prefix='ci-snapshot-controls-') as directory:
            env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
            result = subprocess.run([sys.executable, '-I', '-B', '-c', SCENARIO,
                str(SCRIPTS), directory], env=env, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            rows = json.loads(result.stdout)
            self.assertTrue(rows['closed']['removed'], rows['closed'])
            self.assertTrue(all(row['default_retained'] for row in rows.values()))
            for case, row in rows.items():
                if case != 'closed':
                    with self.subTest(case=case):
                        self.assertFalse(row['removed'])

    def test_real_pytest_requires_all_three_passed_phases(self):
        scenario = SCENARIO.split('results = {}')[0] + r'''
import pytest
tests = root / 'backend' / 'test_lifecycle.py'
tests.write_text(r''' + "'''" + r'''
import json
import os
from pathlib import Path
import pytest
from persistence import capacity, db

@pytest.fixture
def owned(request):
    owner = capacity.DatabaseOwner(db.engine).acquire()
    backup = owner.path.with_name(owner.path.name + '.before-capacity-' + owner.epoch + '.db')
    capacity.initialize_capacity(owner, backup)
    owner.open_admission()
    with Path(os.environ['CONTROL_RECORD']).open('a') as out:
        out.write(json.dumps({'case': request.param, 'backup': str(backup)}) + '\n')
    yield request.param
    owner.fence_admission()
    owner.close()
    if request.param == 'teardown': raise RuntimeError('synthetic teardown failure')

@pytest.mark.parametrize('owned', ['passed', 'failed', 'skipped', 'xfail', 'teardown'], indirect=True)
def test_lifecycle(owned):
    if owned == 'failed': assert False, 'synthetic call failure'
    if owned == 'skipped': pytest.skip('synthetic skip')
    if owned == 'xfail': pytest.xfail('synthetic xfail')
''' + "'''" + r''')
os.environ['CONTROL_RECORD'] = str(base / 'record.jsonl')
os.chdir(root)
phases = []
class PhaseObserver:
    def pytest_runtest_logreport(self, report):
        phases.append((report.nodeid, report.when, report.outcome))
status = pytest.main(['-q', '-p', 'no:cacheprovider', str(tests)], plugins=[plugin, PhaseObserver()])
rows = [json.loads(row) for row in Path(os.environ['CONTROL_RECORD']).read_text().splitlines()]
assert status == 1
assert len(phases) == 15 and len({(node, phase) for node, phase, outcome in phases}) == 15
assert len({node for node, phase, outcome in phases}) == 5
print('CI_CLEANUP_RESULT=' + json.dumps({row['case']: not Path(row['backup']).exists() for row in rows}))
'''
        with tempfile.TemporaryDirectory(prefix='ci-snapshot-pytest-') as directory:
            env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1',
                   'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1'}
            env.pop('PYTEST_ADDOPTS', None)
            result = subprocess.run([sys.executable, '-I', '-B', '-c', scenario,
                str(SCRIPTS), directory], env=env, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            rows = json.loads(next(line.split('=', 1)[1] for line in result.stdout.splitlines()
                                   if line.startswith('CI_CLEANUP_RESULT=')))
            self.assertEqual(rows, {'passed': True, 'failed': False, 'skipped': False,
                                    'xfail': False, 'teardown': False})

    def test_canonical_workspace_markers_serial_and_opt_in_are_required(self):
        path = SCRIPTS / 'ci_backend_snapshot_cleanup.py'
        self.assertTrue(path.is_file(), 'New inactive plugin API absent on baseline')
        spec = importlib.util.spec_from_file_location('cleanup_scope', path)
        plugin = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(plugin)
        with tempfile.TemporaryDirectory(prefix='ci-snapshot-scope-') as directory:
            runner = Path(directory)
            root = runner / 'mtg-backend-work-Ab12cd' / 'source'
            (root / 'backend').mkdir(parents=True)
            for name in ('.private', '.private-choice-audit-source'):
                (root / name).write_text(str(root))
            environment = {'RUNNER_TEMP': str(runner), 'MTG_ISOLATED_TEST_ROOT': str(root),
                           'MTG_CI_PASSED_SNAPSHOT_CLEANUP': '1'}
            with patch.dict(os.environ, environment, clear=True):
                self.assertEqual(plugin.SnapshotCleanup().root, root)
                for name, value in (('MTG_CI_PASSED_SNAPSHOT_CLEANUP', '0'),
                                    ('MTG_ISOLATED_TEST_ROOT', str(root / '..' / 'source')),
                                    ('RUNNER_TEMP', str(root)), ('PYTEST_XDIST_WORKER', 'gw0')):
                    with self.subTest(name=name), patch.dict(os.environ, {name: value}):
                        self.assertIsNone(plugin.SnapshotCleanup().root)
                (root / '.git').touch()
                self.assertIsNone(plugin.SnapshotCleanup().root)
                (root / '.git').unlink()
                (root / '.private').write_text('foreign')
                self.assertIsNone(plugin.SnapshotCleanup().root)


if __name__ == '__main__':
    unittest.main()
