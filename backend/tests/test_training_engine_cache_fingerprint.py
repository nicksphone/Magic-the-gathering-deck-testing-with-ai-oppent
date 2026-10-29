"""Synthetic filesystem protocol only; no actual image cache or game fixtures."""
from hashlib import sha256

import pytest

from training import environment


SOURCE_FILES = (
    'api_contracts.py',
    'decks/builtin_decks.py',
    'training/environment.py',
    'training/schema.json',
    'rules_engine/canonical.json',
    'effects/effect.py',
    'game_state/canonical.json',
    'ai/policy.py',
    'ai/image_cache/token-index.json',
    'rules_engine/image_cache/token-index.json',
    'card_data/builtin_oracle_seed.json',
    'card_data/builtin_token_seed.json',
    'card_data/nested/image_cache/token-index.json',
    'card_data/image_cache_backup/token-index.json',
    'card_data/image_cache/generated.py',
    'card_data/image_cache/nested/generated.py',
)


@pytest.fixture
def synthetic_backend(tmp_path, monkeypatch):
    root = tmp_path / 'backend'
    for relative in SOURCE_FILES:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('# Synthetic source\n' if path.suffix == '.py'
                        else '{"synthetic_source": 1}\n')
    monkeypatch.setattr(environment, '__file__', str(root / 'training/environment.py'))
    return root


def golden_hash(root):
    digest = sha256()
    # Explicit fixture inventory, independent of the production traversal/filter.
    for relative in sorted(SOURCE_FILES):
        digest.update(relative.encode('ascii') + b'\0')
        digest.update((root / relative).read_bytes() + b'\0')
    return digest.hexdigest()


@pytest.mark.parametrize('relative', ['token-index.json', 'nested/token-index.json'])
@pytest.mark.parametrize('operation', ['create', 'edit', 'delete'])
def test_generated_cache_json_lifecycle_is_not_engine_source(
        synthetic_backend, relative, operation):
    root = synthetic_backend
    path = root / 'card_data/image_cache' / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if operation != 'create':
        path.write_text('{"synthetic_generated_index": 1}\n')
    before = environment._engine_hash()
    if operation == 'delete':
        path.unlink()
    else:
        path.write_text('{"synthetic_generated_index": 2}\n')
    assert environment._engine_hash() == before
    assert environment._engine_hash() == golden_hash(root)


@pytest.mark.parametrize('relative', SOURCE_FILES)
def test_every_explicit_source_still_changes_fingerprint(synthetic_backend, relative):
    root = synthetic_backend
    path = root / relative
    original = path.read_bytes()
    before = environment._engine_hash()
    path.write_bytes(original + b'\n')
    assert environment._engine_hash() != before
    path.write_bytes(original)
    assert environment._engine_hash() == before == golden_hash(root)


def test_golden_inventory_preserves_paths_bytes_and_order(synthetic_backend):
    assert environment._engine_hash() == golden_hash(synthetic_backend)


def test_fingerprint_is_deterministic_and_not_memoized(synthetic_backend):
    before = environment._engine_hash()
    assert environment._engine_hash() == before
    path = synthetic_backend / 'api_contracts.py'
    original = path.read_bytes()
    path.write_bytes(b'# Changed synthetic API\n')
    assert environment._engine_hash() != before
    path.write_bytes(original)
    assert environment._engine_hash() == before
