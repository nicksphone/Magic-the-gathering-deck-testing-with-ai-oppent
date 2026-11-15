"""Optional archive availability uses metadata only, never archived game bodies."""
import errno

import pytest

from tests import test_ai_opaque_top_choose_horizon as original


class MetadataOnlyArchive:
    def __init__(self, available=False, error=None):
        self.available = available
        self.error = error

    def exists(self):
        if self.error is not None:
            raise self.error
        return self.available

    def read_text(self, *args, **kwargs):
        raise AssertionError('Archive availability must not read a body')

    read_bytes = read_text


def _skip_decision(monkeypatch, archive):
    monkeypatch.setattr(original, 'NATURAL', archive)
    subject = original.test_saved_turn16_live_agent_restored_roots_and_opportunity_count
    marker = next(mark for mark in subject.pytestmark if mark.name == 'skipif')
    condition = marker.args[0]
    return eval(condition, vars(original)) if isinstance(condition, str) else condition


def test_optional_archive_permission_denial_still_fails_loudly(monkeypatch):
    # Matches test_optional_archive_collection: an unreadable archive is not silently skipped.
    error = PermissionError(errno.EACCES, 'Inert metadata denial')
    with pytest.raises(PermissionError) as caught:
        _skip_decision(monkeypatch, MetadataOnlyArchive(error=error))
    assert caught.value is error


@pytest.mark.parametrize('available,expected', [(False, True), (True, False)], ids=['missing', 'present'])
def test_optional_archive_presence_controls_skip(monkeypatch, available, expected):
    assert _skip_decision(monkeypatch, MetadataOnlyArchive(available=available)) is expected


@pytest.mark.parametrize('error', [OSError(errno.EIO, 'Inert IO error'), RuntimeError('Inert runtime error')],
                         ids=['os-error', 'runtime-error'])
def test_optional_archive_unexpected_probe_errors_propagate(monkeypatch, error):
    with pytest.raises(type(error)) as caught:
        _skip_decision(monkeypatch, MetadataOnlyArchive(error=error))
    assert caught.value is error
