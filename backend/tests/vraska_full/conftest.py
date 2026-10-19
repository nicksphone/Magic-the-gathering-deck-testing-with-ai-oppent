"""Only disposable media-resource paths change; actual token creation is untouched."""
from pathlib import Path
import pytest


@pytest.fixture(autouse=True)
def owned_media(tmp_path, monkeypatch):
    from card_data import placeholders, sync, token_images
    cache = tmp_path / 'media'
    for module in (placeholders, sync, token_images):
        monkeypatch.setattr(module, 'CACHE_DIR', cache)
    monkeypatch.setattr(token_images, '_INDEX_FILE', cache / 'token-index.json')
