"""Pure environment controls, not native SQL/lock/bootstrap qualification."""
import inspect
from pathlib import Path

import pytest

from tests import test_capacity_bootstrap_policy as policy


@pytest.mark.parametrize('present', [False, True])
def test_policy_checks_accept_either_prior_default_file_state(present, tmp_path, monkeypatch):
    exists, read_bytes, stat = Path.exists, Path.read_bytes, Path.stat
    metadata_file = tmp_path / 'metadata-fixture'
    metadata_file.write_bytes(b'existing')
    metadata = metadata_file.stat()
    monkeypatch.setattr(Path, 'exists', lambda path: present if path == policy.DEFAULT else exists(path))
    monkeypatch.setattr(Path, 'read_bytes', lambda path: b'existing' if path == policy.DEFAULT else read_bytes(path))
    monkeypatch.setattr(Path, 'stat', lambda path, *a, **kw:
                        metadata if path == policy.DEFAULT else stat(path, *a, **kw))
    policy.test_exact_application_default_validates_without_creation()
    policy.test_default_owner_backup_requires_actual_acquisition_before_io(tmp_path, monkeypatch)


def test_network_mount_policy_does_not_depend_on_runner_mounts(monkeypatch):
    read_text = Path.read_text
    monkeypatch.setattr(Path, 'read_text', lambda path, *a, **kw:
                        '1 0 0:1 / / rw - ext4 fixture rw\n'
                        if path == Path('/proc/self/mountinfo') else read_text(path, *a, **kw))
    function = policy.test_application_seam_still_rejects_network_filesystem
    if inspect.signature(function).parameters:
        function(monkeypatch)
    else:
        function()
