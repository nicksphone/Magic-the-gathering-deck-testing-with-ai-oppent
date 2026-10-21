"""Path-admission protocols only: no files, checkpoints, or training are written."""
from pathlib import Path

import pytest

from scripts import train_qv


@pytest.mark.parametrize('directory', [
    'rules_engine', 'effects', 'game_state', 'ai', 'card_data', 'training',
])
def test_output_cannot_add_json_below_any_engine_hashed_directory(directory):
    backend = Path(train_qv.__file__).resolve().parents[1]
    parent = backend / directory
    assert parent.is_dir(), 'Bind the actual full backend, not a sparse fake source'
    output = parent / 'qv-path-protocol-never-created.json'
    assert not output.exists() and not output.is_symlink()
    with pytest.raises(ValueError, match='hashed source'):
        train_qv._output_path(output, [])
    assert not output.exists() and not output.is_symlink()


def test_fresh_owned_external_path_is_admitted_without_creating_it(tmp_path):
    output = tmp_path / 'qv-path-protocol-never-created.json'
    assert train_qv._output_path(output, []) == output
    assert not output.exists() and not output.is_symlink()


def test_output_cannot_add_a_member_to_an_existing_sealed_dataset(tmp_path):
    output = tmp_path / 'qv-path-protocol-never-created.json'
    with pytest.raises(ValueError, match='sealed datasets'):
        train_qv._output_path(output, [tmp_path])
    assert not output.exists() and not output.is_symlink()
