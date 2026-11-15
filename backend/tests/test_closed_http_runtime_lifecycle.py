"""Controlled public roots only; no backend, SQL, network or native process."""
import importlib
import json
import os
from pathlib import Path
import signal
import sys
import tarfile
from contextlib import contextmanager
from types import SimpleNamespace

import pytest


def helper():
    path = Path(__file__).with_name('closed_http_runtime.py')
    assert path.is_file(), 'closed runtime helper not implemented'
    return importlib.import_module('tests.closed_http_runtime')


class Process:
    pid = 41
    returncode = -signal.SIGTERM

    def poll(self):
        return self.returncode

    def wait(self, timeout):
        assert timeout == 0
        return self.returncode


def roots(tmp_path, cold=True):
    runtime = tmp_path / 'runtime-owned'
    runtime.mkdir()
    (runtime / 'backend').mkdir()
    (runtime / 'backend/empty').mkdir()
    (runtime / 'backend/public.txt').write_bytes(b'PUBLIC FAKE\x00\xff')
    (runtime / '.private-choice-owned').write_text('PUBLIC FAKE TOKEN')
    evidence = tmp_path / 'evidence'
    evidence.mkdir()
    server = SimpleNamespace(root=runtime, token='PUBLIC FAKE TOKEN', proc=Process())
    data = None
    if cold:
        data = tmp_path / 'cold-restart-data' / runtime.name
        data.mkdir(parents=True)
        server.data = data
        (data / 'state.sqlite3').write_bytes(b'FAKE BYTES, NOT SQLITE')
        closure = {'pid': 41, 'registered_owners': 0, 'pool_checkedout': 0}
        (data / 'closure-41.json').write_text(json.dumps(closure))
    return server, runtime, data, evidence


@pytest.mark.parametrize('cold', [False, True])
def test_full_members_bytes_empty_dirs_proven_before_both_roots_removed(tmp_path, cold):
    h = helper()
    server, runtime, data, evidence = roots(tmp_path, cold)
    receipt = h.archive_closed_http_runtime(server, runtime=runtime, data=data, evidence_root=evidence)
    assert not runtime.exists()
    assert data is None or not data.exists()
    archive = Path(receipt['archive'])
    assert archive.is_relative_to(evidence)
    with tarfile.open(archive) as tar:
        assert tar.extractfile('runtime/backend/public.txt').read() == b'PUBLIC FAKE\x00\xff'
        assert tar.getmember('runtime/backend/empty').isdir()
        if cold:
            assert tar.extractfile('data/state.sqlite3').read() == b'FAKE BYTES, NOT SQLITE'
    assert receipt['byte_member_inode_verified'] is True
    assert receipt['closure_kind'] == ('native-owner-and-process' if cold else 'terminal-process')


@pytest.mark.parametrize('returncode', [None, -signal.SIGKILL, 1, False])
def test_unknown_live_forced_or_bad_exit_retains_all_originals(tmp_path, returncode):
    h = helper()
    server, runtime, data, evidence = roots(tmp_path)
    server.proc.returncode = returncode
    with pytest.raises(RuntimeError, match='HTTP_RUNTIME_NOT_CLOSED'):
        h.archive_closed_http_runtime(server, runtime=runtime, data=data, evidence_root=evidence)
    assert runtime.is_dir() and data.is_dir() and not list(evidence.iterdir())


@pytest.mark.parametrize('fault', ['missing', 'owner', 'pool', 'pid'])
def test_missing_or_unclosed_native_receipt_retains_both_roots(tmp_path, fault):
    h = helper()
    server, runtime, data, evidence = roots(tmp_path)
    path = data / 'closure-41.json'
    row = json.loads(path.read_text())
    if fault == 'missing':
        path.unlink()
    else:
        row[{'owner': 'registered_owners', 'pool': 'pool_checkedout', 'pid': 'pid'}[fault]] += 1
        path.write_text(json.dumps(row))
    with pytest.raises(RuntimeError, match='HTTP_RUNTIME_CLOSURE_RECEIPT'):
        h.archive_closed_http_runtime(server, runtime=runtime, data=data, evidence_root=evidence)
    assert runtime.is_dir() and data.is_dir()


def test_archive_write_failure_retains_originals_and_fails_teardown(tmp_path, monkeypatch):
    h = helper()
    server, runtime, data, evidence = roots(tmp_path)
    def fail(*args, **kwargs):
        raise OSError('PUBLIC FAKE ARCHIVE FAILURE')
    monkeypatch.setattr(h.tarfile, 'open', fail)
    with pytest.raises(OSError, match='PUBLIC FAKE ARCHIVE FAILURE'):
        h.archive_closed_http_runtime(server, runtime=runtime, data=data, evidence_root=evidence)
    assert runtime.is_dir() and data.is_dir()


def test_verification_failure_retains_originals(tmp_path, monkeypatch):
    h = helper()
    server, runtime, data, evidence = roots(tmp_path)
    def fail(*args, **kwargs):
        raise RuntimeError('PUBLIC FAKE VERIFY FAILURE')
    monkeypatch.setattr(h, '_verify_archive', fail)
    with pytest.raises(RuntimeError, match='PUBLIC FAKE VERIFY FAILURE'):
        h.archive_closed_http_runtime(server, runtime=runtime, data=data, evidence_root=evidence)
    assert runtime.is_dir() and data.is_dir()


def test_late_inode_substitution_prevents_any_original_deletion(tmp_path, monkeypatch):
    h = helper()
    server, runtime, data, evidence = roots(tmp_path)
    verify = h._verify_archive
    def replaced(*args):
        verify(*args)
        path = runtime / 'backend/public.txt'
        replacement = runtime / 'replacement'
        replacement.write_bytes(path.read_bytes())
        replacement.replace(path)
    monkeypatch.setattr(h, '_verify_archive', replaced)
    with pytest.raises(RuntimeError, match='HTTP_RUNTIME_CHANGED'):
        h.archive_closed_http_runtime(server, runtime=runtime, data=data, evidence_root=evidence)
    assert runtime.is_dir() and data.is_dir()


def test_late_archive_mutation_cannot_be_resealed_as_verified(tmp_path, monkeypatch):
    h = helper()
    server, runtime, data, evidence = roots(tmp_path)
    verify = h._verify_archive
    def changed(archive, *args):
        verify(archive, *args)
        with archive.open('ab') as stream:
            stream.write(b'PUBLIC FAKE UNVERIFIED TAIL')
    monkeypatch.setattr(h, '_verify_archive', changed)
    with pytest.raises(RuntimeError, match='HTTP_RUNTIME_CHANGED'):
        h.archive_closed_http_runtime(server, runtime=runtime, data=data, evidence_root=evidence)
    assert runtime.is_dir() and data.is_dir()


def test_receipt_write_failure_retains_both_originals(tmp_path, monkeypatch):
    h = helper()
    server, runtime, data, evidence = roots(tmp_path)
    write = Path.write_text
    def stopped(path, *args, **kwargs):
        if path.name == 'VERIFIED.json':
            raise OSError('PUBLIC FAKE RECEIPT FAILURE')
        return write(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'write_text', stopped)
    with pytest.raises(OSError, match='PUBLIC FAKE RECEIPT FAILURE'):
        h.archive_closed_http_runtime(server, runtime=runtime, data=data, evidence_root=evidence)
    assert runtime.is_dir() and data.is_dir()


@pytest.mark.parametrize('fault', ['foreign-data', 'symlink', 'missing-token', 'archive-inside'])
def test_foreign_or_unsupported_roots_are_never_deleted(tmp_path, fault):
    h = helper()
    server, runtime, data, evidence = roots(tmp_path)
    foreign = tmp_path / 'foreign'
    foreign.mkdir()
    (foreign / 'sentinel').write_bytes(b'PRESERVE PUBLIC USER DATA')
    if fault == 'foreign-data':
        data = foreign
    elif fault == 'symlink':
        (runtime / 'foreign-link').symlink_to(foreign)
    elif fault == 'missing-token':
        (runtime / '.private-choice-owned').unlink()
    else:
        evidence = runtime / 'backend'
    with pytest.raises((RuntimeError, FileNotFoundError)):
        h.archive_closed_http_runtime(server, runtime=runtime, data=data, evidence_root=evidence)
    assert runtime.exists() and foreign.is_dir()
    assert (foreign / 'sentinel').read_bytes() == b'PRESERVE PUBLIC USER DATA'


def _empty_protected_file(path):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    os.close(descriptor)


@contextmanager
def _no_protected_body_open(*paths):
    active, attempts = [True], []
    protected = set(paths)
    def guard(event, args):
        if active[0] and event == 'open' and isinstance(args[0], (str, bytes)) and Path(os.fsdecode(args[0])) in protected:
            attempts.append('body-open')
            raise AssertionError('Protected fixture body must never be opened')
    sys.addaudithook(guard)
    try:
        yield attempts
    finally:
        active[0] = False


@pytest.mark.parametrize('cold', [False, True])
def test_owner_lock_is_metadata_only_and_never_opened_before_closed_roots_removed(tmp_path, cold):
    h = helper()
    server, runtime, data, evidence = roots(tmp_path, cold)
    lock = (data if cold else runtime / 'backend') / 'state.sqlite3.capacity-owner.lock'
    _empty_protected_file(lock)
    before = lock.lstat()
    with _no_protected_body_open(lock) as attempts:
        receipt = h.archive_closed_http_runtime(server, runtime=runtime, data=data, evidence_root=evidence)
    assert attempts == []
    assert not runtime.exists() and (data is None or not data.exists())
    member = 'data/state.sqlite3.capacity-owner.lock' if cold else 'runtime/backend/state.sqlite3.capacity-owner.lock'
    assert receipt['metadata_only_members'] == [member]
    with tarfile.open(receipt['archive']) as tar:
        assert member not in tar.getnames(), 'A lock must have no copied tar payload'
        inventory = json.loads(tar.extractfile('OWNED_INVENTORY.json').read())
        label, relative = member.split('/', 1)
        assert inventory[label][relative] == ['owner-lock-metadata', before.st_dev, before.st_ino,
            before.st_mode, 0, before.st_mtime_ns, before.st_ctime_ns, None]
        assert tar.extractfile('runtime/backend/public.txt').read() == b'PUBLIC FAKE\x00\xff'
        if cold:
            assert tar.extractfile('data/state.sqlite3').read() == b'FAKE BYTES, NOT SQLITE'
        assert receipt['byte_members'] == sum(node.isfile() for node in tar.getmembers()) - 1
    assert receipt['byte_member_inode_verified'] is True


@pytest.mark.parametrize('name', ['MODEL.private.json', 'FEATURES.private.json'])
def test_protected_model_names_fail_before_body_access_or_original_deletion(tmp_path, name):
    h = helper()
    server, runtime, data, evidence = roots(tmp_path)
    protected = runtime / 'backend' / name
    _empty_protected_file(protected)
    with _no_protected_body_open(protected) as attempts:
        with pytest.raises(RuntimeError, match='HTTP_RUNTIME_PROTECTED_MEMBER'):
            h.archive_closed_http_runtime(server, runtime=runtime, data=data, evidence_root=evidence)
    assert attempts == []
    assert runtime.is_dir() and data.is_dir() and not list(evidence.iterdir())


@pytest.mark.parametrize('fault', ['mode', 'size', 'links'])
def test_unsafe_owner_lock_metadata_fails_without_body_access_or_cleanup(tmp_path, fault):
    h = helper()
    server, runtime, data, evidence = roots(tmp_path)
    lock = data / 'state.sqlite3.capacity-owner.lock'
    _empty_protected_file(lock)
    if fault == 'mode':
        lock.chmod(0o644)
    elif fault == 'size':
        os.truncate(lock, 1)
    else:
        os.link(lock, tmp_path / 'owned-empty-hardlink')
    with _no_protected_body_open(lock) as attempts:
        with pytest.raises(RuntimeError, match='HTTP_RUNTIME_UNSAFE_OWNER_LOCK'):
            h.archive_closed_http_runtime(server, runtime=runtime, data=data, evidence_root=evidence)
    assert attempts == []
    assert runtime.is_dir() and data.is_dir() and not list(evidence.iterdir())


def test_late_owner_lock_inode_substitution_retains_both_roots_without_body_access(tmp_path, monkeypatch):
    h = helper()
    server, runtime, data, evidence = roots(tmp_path)
    lock = data / 'state.sqlite3.capacity-owner.lock'
    _empty_protected_file(lock)
    before = lock.lstat()
    verify = h._verify_archive
    def replaced(*args):
        verify(*args)
        replacement = data / 'replacement.capacity-owner.lock'
        _empty_protected_file(replacement)
        replacement.replace(lock)
    monkeypatch.setattr(h, '_verify_archive', replaced)
    with _no_protected_body_open(lock) as attempts:
        with pytest.raises(RuntimeError, match='HTTP_RUNTIME_CHANGED'):
            h.archive_closed_http_runtime(server, runtime=runtime, data=data, evidence_root=evidence)
    assert attempts == [] and lock.lstat().st_ino != before.st_ino
    assert runtime.is_dir() and data.is_dir()


@pytest.mark.parametrize('name,error', [
    ('late.capacity-owner.lock', 'HTTP_RUNTIME_CHANGED'),
    ('MODEL.private.json', 'HTTP_RUNTIME_PROTECTED_MEMBER'),
    ('FEATURES.private.json', 'HTTP_RUNTIME_PROTECTED_MEMBER'),
    ('unlisted-public.txt', 'HTTP_RUNTIME_CHANGED'),
])
def test_late_unlisted_member_is_rejected_before_tar_body_access_or_cleanup(tmp_path, monkeypatch, name, error):
    h = helper()
    server, runtime, data, evidence = roots(tmp_path)
    late = runtime / 'backend' / name
    add = h.tarfile.TarFile.add
    observed = []
    def inserted(tar, path, *args, **kwargs):
        if Path(path) == runtime:
            # First inventory is complete; the new member is not authorized.
            _empty_protected_file(late)
            with _no_protected_body_open(late) as attempts:
                observed.append(attempts)
                return add(tar, path, *args, **kwargs)
        return add(tar, path, *args, **kwargs)
    monkeypatch.setattr(h.tarfile.TarFile, 'add', inserted)
    with pytest.raises(RuntimeError, match=error):
        h.archive_closed_http_runtime(server, runtime=runtime, data=data, evidence_root=evidence)
    assert observed == [[]]
    assert runtime.is_dir() and data.is_dir()
    assert not list(evidence.rglob('VERIFIED.json'))
