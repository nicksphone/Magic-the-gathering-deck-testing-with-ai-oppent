"""CI-only passed startup scratch reclamation, NOT global/kernel FD proof.

Only an observed real owner in a fresh serial CI workspace can qualify. All
unknowns retain; default databases and preexisting/failed artifacts never enter.
"""
import hashlib
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

import pytest


def canonical(path):
    if not path.is_absolute() or path.resolve(strict=True) != path:
        raise ValueError('Noncanonical workspace path')
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError('Linked workspace path')
    return path


def file_pin(path):
    canonical(path)
    before = path.stat(follow_symlinks=False)
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise ValueError('Not a single-link regular file')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            digest.update(block)
    after = path.stat(follow_symlinks=False)
    fields = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
    if any(getattr(before, field) != getattr(after, field) for field in fields):
        raise ValueError('File changed while pinning')
    return (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns,
            after.st_ctime_ns, digest.hexdigest())


def owned_children():
    children = set()
    for task in Path('/proc/self/task').iterdir():
        try:
            children.update(int(pid) for pid in (task / 'children').read_text().split())
        except FileNotFoundError:
            continue  # A thread ended during observation, not a visibility grant.
    return children


def owned_children_closed(known):
    if owned_children():
        return False
    for pid in known:
        try:
            Path(f'/proc/{pid}').stat()
        except FileNotFoundError:
            continue
        return False
    return True


class SnapshotCleanup:
    def __init__(self):
        self.states = {}
        self.root = None
        try:
            if os.environ.get('MTG_CI_PASSED_SNAPSHOT_CLEANUP') != '1':
                return
            root = canonical(Path(os.environ['MTG_ISOLATED_TEST_ROOT']))
            runner = canonical(Path(os.environ['RUNNER_TEMP']))
            if (root.name != 'source' or root.parent.parent != runner or
                    not re.fullmatch(r'mtg-backend-work-[A-Za-z0-9]{6}', root.parent.name) or
                    os.path.lexists(root / '.git') or os.environ.get('PYTEST_XDIST_WORKER')):
                return
            for name in ('.private', '.private-choice-audit-source'):
                marker = root / name
                file_pin(marker)
                if marker.read_text() != str(root):
                    return
            self.database = canonical(root / 'backend') / 'mtg_lab.db'
            self.root = root
        except Exception:
            return

    def before_setup(self, item):
        if self.root is None:
            return
        try:
            # Names, not just regular files: links/odd preexisting entries stay protected.
            existing = {p.name for p in self.database.parent.iterdir()}
            self.states[item.nodeid] = {'existing': existing, 'phases': {},
                                       'children': owned_children(), 'candidate': None}
        except Exception:
            self.states.pop(item.nodeid, None)

    def bind_owner(self, state):
        db = sys.modules.get('persistence.db')
        capacity = sys.modules.get('persistence.capacity')
        if db is None or capacity is None:
            return
        for module, name in ((db, 'db.py'), (capacity, 'capacity.py')):
            if canonical(Path(module.__file__)) != self.root / 'backend' / 'persistence' / name:
                return
        if (db.DATABASE_PATH != self.database or db.DEFAULT_DATABASE_PATH != self.database or
                db.engine.url.database != str(self.database)):
            return
        owner = capacity.owner_for_engine(db.engine)
        if (type(owner) is not capacity.DatabaseOwner or owner.path != self.database or
                owner.pid != os.getpid() or not owner.ready or owner.uncertain or
                type(owner.epoch) is not str or not re.fullmatch('[0-9a-f]{32}', owner.epoch)):
            return
        candidate = self.database.with_name(self.database.name + '.before-capacity-' + owner.epoch + '.db')
        if candidate.name in state['existing']:
            return
        state['children'].update(owned_children())
        state['candidate'] = (candidate, file_pin(candidate), owner, capacity, db, owner.epoch)

    def remove_if_closed(self, state):
        candidate, pin, owner, capacity, db, epoch = state['candidate']
        with owner.mutex, capacity._OWNER_LOCK:
            if (type(owner) is not capacity.DatabaseOwner or owner.engine is not db.engine or
                    owner.path != self.database or owner.pid != os.getpid() or owner.epoch != epoch or
                    owner.fd is not None or owner.ready or owner.uncertain or owner.admissions_open or
                    owner.producers or any(row.path == self.database for row in capacity._OWNERS.values()) or
                    owner.pool.checkedout() != 0 or owner.engine.pool.checkedout() != 0):
                return
            if not owned_children_closed(state['children']) or file_pin(candidate) != pin:
                return
            paths = [candidate, self.database]
            for path in tuple(paths):
                file_pin(path)
                for suffix in ('-wal', '-shm', '-journal'):
                    journal = Path(str(path) + suffix)
                    if os.path.lexists(journal):
                        file_pin(journal)
                        paths.append(journal)
            canonical(Path('/usr/bin/fuser'))
            result = subprocess.run(['/usr/bin/fuser', *map(str, paths)],
                env={'PATH': '/usr/bin:/bin', 'LANG': 'C'}, capture_output=True, timeout=5)
            if result.returncode != 1 or result.stdout or result.stderr:
                return
            # Cooperative serial CI only: no claim of an atomic kernel-wide lease.
            if file_pin(candidate) == pin and owned_children_closed(state['children']):
                candidate.unlink()

    def after_report(self, item, report):
        state = self.states.get(item.nodeid)
        if state is None:
            return
        try:
            if report.when in state['phases']:
                state['candidate'] = None
                state['duplicate'] = True
            state['phases'][report.when] = (report.outcome, hasattr(report, 'wasxfail'))
            if report.when == 'setup' and report.outcome == 'passed' and not state.get('duplicate'):
                self.bind_owner(state)
            if report.when == 'teardown' and state['candidate'] is not None:
                if state['phases'] == {p: ('passed', False) for p in ('setup', 'call', 'teardown')}:
                    self.remove_if_closed(state)
        except Exception:
            pass  # Cleanup must not alter tests, outcomes or mandatory evidence.
        finally:
            if report.when == 'teardown':
                self.states.pop(item.nodeid, None)


_cleanup = None


def pytest_configure(config):
    global _cleanup
    _cleanup = None if getattr(config.option, 'numprocesses', 0) else SnapshotCleanup()


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtest_setup(item):
    if _cleanup is not None:
        _cleanup.before_setup(item)
    return (yield)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item, call):
    report = yield
    if _cleanup is not None:
        _cleanup.after_report(item, report)
    return report
