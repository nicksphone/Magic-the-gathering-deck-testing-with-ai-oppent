"""Real combined factory/lifespan in fresh app processes, not browser evidence."""
import importlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]


def support():
    name = 'tests.launcher_smoke_support'
    assert importlib.util.find_spec(name) is not None, 'Launcher smoke copy support is missing'
    return importlib.import_module(name)


def test_copy_excludes_databases_caches_secrets_tests_and_aliases(tmp_path):
    source, target = tmp_path/'input', tmp_path/'copy'
    (source/'backend/card_data/assets').mkdir(parents=True)
    (source/'backend/card_data/assets/token.svg').write_text('<svg/>')
    (source/'backend/main.py').write_text('VALUE = 1\n')
    for relative in ('.venv/hidden.py', 'tests/hidden.py', 'knowledge/data/hidden.json',
                     'card_data/image_cache/hidden.json', 'diagnostics/hidden.json'):
        path = source/'backend'/relative
        path.parent.mkdir(parents=True, exist_ok=True); path.write_text('not an app input')
    (source/'backend/.env').write_text('not copied')
    (source/'backend/mtg_lab.db').write_bytes(b'not copied')
    (source/'backend/alias.py').symlink_to(source/'backend/main.py')
    support().copy_application(source, target)
    files = {p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_file()}
    assert files == {'backend/main.py', 'backend/card_data/assets/token.svg'}
    assert target.stat().st_mode & 0o777 == 0o700
    with pytest.raises(FileExistsError): support().copy_application(source, target)


def test_child_environment_is_explicit_and_drops_app_overrides(tmp_path, monkeypatch):
    monkeypatch.setenv('MTG_PRIVATE_TEST_CANARY', 'must-not-forward')
    monkeypatch.setenv('PYTHONPATH', '/untrusted')
    value = support().worker_environment(tmp_path/'source/backend', tmp_path/'state.db')
    assert value['MTG_DATABASE_PATH'] == str(tmp_path/'state.db')
    assert value['PYTHONPATH'] == str(tmp_path/'source/backend')
    assert value['MTG_TRUSTED_ORIGINS'] == 'http://testserver'
    assert 'MTG_PRIVATE_TEST_CANARY' not in value


def test_real_combined_app_restarts_and_retains_match_receipts(tmp_path):
    """Actual TestClient+lifespan, HTML fixture only; the CDP run is separate."""
    source = tmp_path/'source'
    support().copy_application(ROOT, source)
    dist = source/'frontend/dist'
    (dist/'assets').mkdir(parents=True)
    (dist/'index.html').write_text('<!doctype html><title>Launcher ASGI fixture</title>')
    (dist/'assets/probe.js').write_text('/* ASGI fixture asset, not a production bundle */')
    worker = source/'backend/launcher_real_app_worker.py'
    original = Path(__file__).with_name('launcher_real_app_worker.py')
    assert original.is_file(), 'Real launcher smoke worker is missing'
    worker.write_bytes(original.read_bytes())
    database, checkpoint = tmp_path/'state.db', tmp_path/'checkpoint.json'
    environment = support().worker_environment(source/'backend', database)
    summaries = []
    for phase in ('create', 'restore'):
        result = subprocess.run([sys.executable, '-B', str(worker), phase, str(checkpoint)],
            cwd=source/'backend', env=environment, capture_output=True, text=True, timeout=90)
        assert result.returncode == 0, result.stderr
        summaries.append(json.loads(result.stdout))
    assert summaries[0]['phase'] == 'create' and summaries[1]['phase'] == 'restore'
    assert summaries[0]['revision'] == summaries[1]['revision'] >= 3
    assert all(row['owner_released'] and row['local_media'] for row in summaries)
    assert summaries[1]['exact_restore'] is True
    assert summaries[1]['original_key_retry'] is True
    assert summaries[1]['stale_status'] == 409
    assert not (source/'backend/mtg_lab.db').exists()
