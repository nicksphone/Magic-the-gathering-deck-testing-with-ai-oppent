"""Relative pure fixture bootstrap; strict native guard remains the gate runner's duty."""
from pathlib import Path
import hashlib
import json
import sys
import pytest

REPO = Path(__file__).resolve().parents[2]
SUPPORT = REPO/'audit/gate2-granted-target'
PINS = json.loads((Path(__file__).parent/'DEPENDENCY.json').read_text())['files']
for name, digest in PINS.items():
    assert hashlib.sha256((SUPPORT/name).read_bytes()).hexdigest() == digest, name
sys.path[:0] = [str(REPO/'backend'), str(Path(__file__).parent), str(SUPPORT)]

@pytest.fixture(scope='session', autouse=True)
def _owned_media_output(tmp_path_factory):
    import card_data.placeholders
    previous = card_data.placeholders.CACHE_DIR
    card_data.placeholders.CACHE_DIR = tmp_path_factory.mktemp('ai-granted-media')
    try:
        yield
    finally:
        card_data.placeholders.CACHE_DIR = previous

@pytest.fixture(autouse=True)
def _owned_test_evidence(tmp_path, monkeypatch):
    monkeypatch.setenv('NADU_EVIDENCE', str(tmp_path))
