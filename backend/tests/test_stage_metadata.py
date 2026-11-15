"""Stage receipts are optional test instrumentation, with explicit output only."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from tests.test_battle_characteristics import mark as battle_mark
from tests.battle_copy_native_support import mark as copy_mark
from tests.test_deferred_upkeep_payment import mark as deferred_mark
from tests.test_corpus_local_filesystem import mark_returned_unsupported_mount
from tests.test_knowledge_snapshot_imports import _mark_import_boundary


def _filesystem_mark(_stage):
    mark_returned_unsupported_mount()


def _import_mark(stage):
    request = SimpleNamespace(config=SimpleNamespace(getoption=lambda _name: '/unrelated/pytest'))
    _mark_import_boundary(request, stage)


WRITERS = [
    pytest.param(battle_mark, 'inert-stage', id='battle'),
    pytest.param(copy_mark, 'inert-stage', id='battle-copy'),
    pytest.param(deferred_mark, 'inert-stage', id='deferred'),
    pytest.param(_filesystem_mark, 'remote-or-unrecognized-mount-returned-successfully', id='filesystem'),
    pytest.param(_import_mark, 'inert-stage', id='knowledge-import'),
]


@pytest.mark.parametrize('writer,expected_stage', WRITERS)
def test_marker_does_not_write_without_explicit_output(monkeypatch, writer, expected_stage):
    monkeypatch.delenv('MTG_TEST_STAGE_METADATA_DIR', raising=False)
    # An incidental sibling directory must never enable instrumentation.
    with patch.object(Path, 'is_dir', return_value=True), patch.object(Path, 'write_text', autospec=True) as write:
        writer('inert-stage')
    assert not write.called


@pytest.mark.parametrize('writer,expected_stage', WRITERS)
def test_marker_writes_only_the_explicit_output(monkeypatch, writer, expected_stage):
    monkeypatch.setenv('MTG_TEST_STAGE_METADATA_DIR', '/explicit/inert-stage-output')
    with patch.object(Path, 'write_text', autospec=True) as write:
        writer('inert-stage')
    write.assert_called_once()
    args, kwargs = write.call_args
    assert args[0] == Path('/explicit/inert-stage-output/CONTROL.json')
    assert json.loads(args[1]) == {'stage': expected_stage, 'literal_stage_metadata_only': True}
    assert kwargs == {}


def test_marker_rejects_nonprimitive_stage_before_writing(monkeypatch):
    from tests.stage_metadata import mark
    monkeypatch.setenv('MTG_TEST_STAGE_METADATA_DIR', '/explicit/inert-stage-output')
    with patch.object(Path, 'write_text', autospec=True) as write:
        with pytest.raises(TypeError):
            mark({'not': 'a literal stage'})
    assert not write.called


def test_explicit_output_error_is_not_redirected(monkeypatch):
    from tests.stage_metadata import mark
    monkeypatch.setenv('MTG_TEST_STAGE_METADATA_DIR', '/explicit/inert-stage-output')
    with patch.object(Path, 'write_text', autospec=True, side_effect=OSError('inert output failure')) as write:
        with pytest.raises(OSError):
            mark('inert-stage')
    write.assert_called_once()
    assert write.call_args.args[0] == Path('/explicit/inert-stage-output/CONTROL.json')
