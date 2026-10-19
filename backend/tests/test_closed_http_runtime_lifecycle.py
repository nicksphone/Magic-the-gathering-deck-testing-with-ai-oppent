"""Controlled public roots only; no backend, SQL, network or native process."""
import importlib
import json
from pathlib import Path
import signal
import tarfile
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
