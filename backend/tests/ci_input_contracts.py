"""Portable inputs for the unchanged isolated backend acceptance scenarios."""
import json
import os
from pathlib import Path


def assert_github_owned_source():
    root = Path(__file__).resolve().parents[2]
    assert os.environ.get('GITHUB_ACTIONS') == 'true'
    assert Path(os.environ['MTG_ISOLATED_TEST_ROOT']).resolve() == root
    temporary = Path(os.environ['RUNNER_TEMP']).resolve()
    assert root != temporary and root.is_relative_to(temporary)
    assert not (root / '.git').exists()
    for marker in ('.private', '.private-choice-audit-source'):
        assert (root / marker).read_text() == str(root)
    assert not (root / 'backend/mtg_lab.db').is_symlink()
    return root


def human_bo3_decks():
    path = Path(__file__).parent / 'fixtures/human_bo3_selected_decks.json'
    return list(json.loads(path.read_text())['decks'].values())
