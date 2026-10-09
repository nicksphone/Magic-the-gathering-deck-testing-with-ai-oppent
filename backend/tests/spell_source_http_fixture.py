"""Explicit leased source-overlap acceptance with a native owned local file."""
from pathlib import Path
import os

import pytest

from tests.temporary_characteristics_http_fixture import source_lease, api_context


@pytest.fixture
def isolated_api(monkeypatch, request):
    root = source_lease() / 'backend'
    monkeypatch.setenv('MTG_COST_OVERLAP_ROOT', str(root))
    approved = os.environ.get('MTG_COST_OVERLAP_ROOT')
    assert approved and Path(approved).resolve() == root
    with api_context(monkeypatch, request, 'file') as api:
        assert Path(api.main.__file__).resolve().parent == root
        yield api.main, api.engine, api.client
