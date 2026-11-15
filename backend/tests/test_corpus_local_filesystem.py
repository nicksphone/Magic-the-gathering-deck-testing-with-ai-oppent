"""Local-storage admission against controlled host metadata, not real mounts."""
import json
from pathlib import Path
import subprocess

import pytest

from scripts import corpus_knowledge_readiness as corpus
from tests.stage_metadata import mark as _stage_metadata


def mount_metadata(monkeypatch, root, filesystem, *, unavailable=False):
    original = Path.read_text

    def read(path, *args, **kwargs):
        if str(path) == '/proc/self/mountinfo':
            if unavailable:
                raise OSError('Mount metadata unavailable')
            return f'1 0 0:1 / {root} rw - {filesystem} fixture rw\n'
        return original(path, *args, **kwargs)

    def legacy_probe(command, *, text):
        assert command[:5] == ['findmnt', '-n', '-o', 'FSTYPE', '-T']
        assert text is True
        return filesystem + '\n'

    monkeypatch.setattr(Path, 'read_text', read)
    monkeypatch.setattr(subprocess, 'check_output', legacy_probe)


def mark_returned_unsupported_mount():
    _stage_metadata('remote-or-unrecognized-mount-returned-successfully')


@pytest.mark.parametrize('filesystem', ['ext4', 'tmpfs', 'overlay'])
def test_known_local_mount_accepts_state_path(tmp_path, monkeypatch, filesystem):
    mount_metadata(monkeypatch, tmp_path, filesystem)
    destination = tmp_path / 'checkpoint.db'
    assert corpus.local_path(destination) == destination
    assert not destination.exists()


@pytest.mark.parametrize('filesystem', [
    'fuse.sshfs', '9p', 'ceph', 'fuse.rclone', 'unknown_test_fs',
])
def test_remote_or_unrecognized_mount_is_rejected(tmp_path, monkeypatch, filesystem):
    mount_metadata(monkeypatch, tmp_path, filesystem)
    with pytest.raises(ValueError):
        corpus.local_path(tmp_path / 'checkpoint.db')
        mark_returned_unsupported_mount()


def test_local_check_works_without_findmnt(tmp_path, monkeypatch):
    mount_metadata(monkeypatch, tmp_path, 'overlay')

    def absent(*args, **kwargs):
        raise FileNotFoundError('findmnt is not installed')

    monkeypatch.setattr(subprocess, 'check_output', absent)
    destination = tmp_path / 'checkpoint.db'
    try:
        result = corpus.local_path(destination)
    except FileNotFoundError:
        result = None
    assert result == destination


def test_unavailable_mount_table_refuses_admission(tmp_path, monkeypatch):
    mount_metadata(monkeypatch, tmp_path, 'overlay', unavailable=True)
    with pytest.raises(OSError):
        corpus.local_path(tmp_path / 'checkpoint.db')


def test_relative_path_normalization_is_preserved(tmp_path, monkeypatch):
    mount_metadata(monkeypatch, tmp_path, 'overlay')
    monkeypatch.chdir(tmp_path)
    assert corpus.local_path(Path('checkpoint.db')) == tmp_path / 'checkpoint.db'
