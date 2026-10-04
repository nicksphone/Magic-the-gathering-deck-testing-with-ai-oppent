"""Hard safety gate: source-relative SQLite must never touch a live worktree."""
from pathlib import Path
import os
import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRATCH = Path('/home/nick/.hermes/cache/scratch').resolve()
declared = os.environ.get('MTG_ISOLATED_TEST_ROOT')
explicit_copy = bool(declared and Path(declared).resolve() == ROOT)
if not (ROOT.is_relative_to(SCRATCH) or explicit_copy) or (ROOT / '.git').exists():
    raise pytest.UsageError(
        'Wave2 tests require a disposable git-archive source copy below '
        '/home/nick/.hermes/cache/scratch or an exact MTG_ISOLATED_TEST_ROOT '
        '(no .git), never either live worktree.'
    )
