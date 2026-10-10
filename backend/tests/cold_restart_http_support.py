"""Complete persistent SQL and native epoch contracts for this HTTP group only."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import sqlite3
import subprocess
import sys

from tests.test_private_choice_http_restart import Server as SharedServer, stable


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def local_file(path):
    path = Path(path)
    assert path.is_absolute() and path.resolve() == path
    assert all(not part.is_symlink() for part in (path, *path.parents))
    assert not subprocess.check_output(['stat', '-f', '-c', '%T', str(path.parent)], text=True).strip().startswith('nfs')
    return path


def facts(path, identifier=None):
    """Read all schema/table rows without SQLite writes; hash actual bytes twice."""
    path = local_file(path)
    before = file_hash(path)
    connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    try:
        connection.execute('PRAGMA query_only=ON')
        connection.row_factory = sqlite3.Row
        sql = list(connection.iterdump())
        tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_schema WHERE type='table'")}
        ledger = [dict(r) for r in connection.execute('SELECT * FROM resourcecapacity')] if 'resourcecapacity' in tables else []
        reservations = [dict(r) for r in connection.execute('SELECT * FROM resourcereservation')] if 'resourcereservation' in tables else []
        jobs = connection.execute('SELECT COUNT(*) FROM simulationjobrecord').fetchone()[0]
        match = None
        if identifier is not None:
            row = connection.execute('SELECT state_json, controller_json FROM activematchrecord WHERE id=?', (identifier,)).fetchone()
            assert row is not None
            match = {'state': json.loads(row[0]), 'controller': json.loads(row[1])}
    finally:
        connection.close()
    after = file_hash(path)
    assert after == before, 'Read-only SQL changed raw database bytes'
    return {'sql': sql, 'ledger': ledger, 'reservations': reservations, 'jobs': jobs,
            'match': match, 'raw_sha256': after}


def sql_hash(rows):
    return hashlib.sha256('\n'.join(rows).encode()).hexdigest()


def bootstrap_transition(before, after, epoch):
    """Job-free group: the only authorized persisted change is actual owner_epoch."""
    without_capacity = lambda rows: [r for r in rows if not r.startswith('INSERT INTO "resourcecapacity"')]
    assert without_capacity(before['sql']) == without_capacity(after['sql']), 'Persistent gameplay SQL changed across bootstrap'
    assert before['jobs'] == after['jobs'] == 0
    assert before['reservations'] == after['reservations'] == []
    assert len(before['ledger']) == len(after['ledger']) == 1
    old = before['ledger'][0]
    assert epoch != old['owner_epoch']
    assert after['ledger'] == [{**old, 'owner_epoch': epoch}], 'Unauthorized capacity ledger transition'


def audit_identity(row):
    return {key: row[key] for key in ('state', 'controller', 'revision')}


class Server(SharedServer):
    def __init__(self, runtime, port):
        super().__init__(runtime, port)
        self.root = self.root.resolve()
        assert not (self.root / '.git').exists()
        for marker in ('.private', '.private-choice-audit-source'):
            (self.root / marker).write_text(str(self.root))
        self.data = self.root.parent / 'cold-restart-data' / self.root.name
        self.data.mkdir(parents=True, exist_ok=False)
        self.path = local_file(self.data / 'state.sqlite3')

    def stop(self):
        super().stop()
        if self.proc is not None:
            # Uvicorn re-raises a captured SIGTERM after successful lifespan exit.
            assert self.proc.poll() in (0, -signal.SIGTERM), 'Native process failed or required forced termination'
            closure = json.loads((self.data / f'closure-{self.proc.pid}.json').read_text())
            assert closure['pid'] == self.proc.pid
            assert closure['registered_owners'] == closure['pool_checkedout'] == 0
            (self.data / f'stop-{self.proc.pid}.json').write_text(json.dumps(
                {'pid': self.proc.pid, 'returncode': self.proc.returncode,
                 'closure_sha256': file_hash(self.data / f'closure-{self.proc.pid}.json')}))

    def environment(self):
        return {**os.environ, 'MTG_PRIVATE_CHOICE_ROOT': str(self.root),
                'MTG_PRIVATE_CHOICE_TOKEN': self.token, 'MTG_ISOLATED_TEST_ROOT': str(self.root),
                'MTG_DATABASE_PATH': str(self.path), 'MTG_COLD_RESTART_DATA': str(self.data),
                'PYTHONPATH': str(self.root / 'backend') + os.pathsep + os.environ.get('PYTHONPATH', '')}

    def readonly(self, expected, identifier, previous_pid, audit=None, path=None):
        index = len(list(self.data.glob('readonly-*.input.json')))
        config = {'root': str(self.root), 'database': str(path or self.path), 'data': str(self.data),
                  'previous_pid': previous_pid, 'parent_pid': os.getpid(),
                  'match_id': identifier, 'expected': expected, 'audit': audit_identity(audit) if audit else None}
        input_path = self.data / f'readonly-{index}.input.json'
        output_path = self.data / f'readonly-{index}.output.json'
        input_path.write_text(json.dumps(config))
        result = subprocess.run([sys.executable, '-m', 'tests.cold_restart_http_probe', str(input_path), str(output_path)],
                                cwd=self.root / 'backend', env=self.environment(), capture_output=True, text=True, timeout=60)
        (self.data / f'readonly-{index}.terminal.json').write_text(json.dumps(
            {'exit': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}))
        assert result.returncode == 0, result.stderr
        observed = json.loads(output_path.read_text())
        assert observed['pid'] not in (os.getpid(), previous_pid)
        assert observed['readonly'] and observed['connections_closed']
        assert observed['facts'] == expected
        return observed

    def restart(self, identifier, before, copy_to=None):
        assert stable(self.audit(identifier)) == stable(before)
        status, receipt = self.call('/fixture/private-choice/database')
        assert status == 200
        captured_path = local_file(Path(receipt['path']))
        assert captured_path.parent == self.data and file_hash(captured_path) == receipt['sha256']
        captured = json.loads(captured_path.read_text())
        assert captured['raw_sha256'] == before['raw_database_sha256']
        assert sql_hash(captured['sql']) == before['database_sha256']
        assert captured['ledger'] == before['capacity_ledger']
        prior = self.proc.pid
        self.stop()
        assert self.proc.poll() in (0, -signal.SIGTERM), 'Native lifespan must close successfully, not be killed'
        observed = self.readonly(captured, identifier, prior, audit=before)
        if copy_to is not None:
            copy_to = local_file(copy_to)
            assert copy_to.parent == self.data and not copy_to.exists()
            shutil.copyfile(self.path, copy_to)
            assert file_hash(copy_to) == captured['raw_sha256']
        self.start()
        assert self.proc.pid != prior
        status, boot = self.call('/fixture/private-choice/bootstrap')
        assert status == 200 and boot['pid'] == self.proc.pid
        boot_path = local_file(Path(boot['path']))
        assert boot_path.parent == self.data and file_hash(boot_path) == boot['sha256']
        boot = json.loads(boot_path.read_text())
        assert boot['before'] == captured
        bootstrap_transition(captured, boot['after'], boot['owner_epoch'])
        restored = self.audit(identifier)
        assert audit_identity(restored) == audit_identity(before)
        assert restored['raw_database_sha256'] == boot['after']['raw_sha256']
        assert restored['database_sha256'] == sql_hash(boot['after']['sql'])
        assert restored['capacity_ledger'] == boot['after']['ledger']
        (self.data / f'restart-{self.proc.pid}.json').write_text(json.dumps(
            {'previous_pid': prior, 'pid': self.proc.pid, 'readonly_pid': observed['pid'],
             'previous_raw_sha256': captured['raw_sha256'], 'raw_sha256': restored['raw_database_sha256'],
             'previous_epoch': captured['ledger'][0]['owner_epoch'], 'owner_epoch': boot['owner_epoch'],
             'complete_gameplay_sql_preserved': True, 'authorized_bootstrap_only': True}))
        # Explicit new-epoch baseline; never pretend writeful bootstrap kept raw bytes.
        return restored
