"""Worker admission/lifecycle controls on synthetic stdlib subprocesses only."""
import importlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


def worker():
    name = 'scripts.archetype_matrix_worker'
    assert importlib.util.find_spec(name) is not None, 'Resource-bounded worker is missing'
    return importlib.import_module(name)


def test_resource_request_rejects_bool_and_unavailable_cpu_before_changes():
    module = worker()
    allowed = sorted(os.sched_getaffinity(0))
    for cpu, seconds, memory in ((True, 90, 2147483648), (max(allowed)+1, 90, 2147483648),
                                 (allowed[0], True, 2147483648), (allowed[0], 0, 2147483648),
                                 (allowed[0], 90, True), (allowed[0], 91, 2147483648)):
        with pytest.raises(ValueError): module.validate_limits(cpu, seconds, memory)
    assert list(sorted(os.sched_getaffinity(0))) == allowed


def test_real_resource_limits_and_descendant_denial_in_fresh_process(tmp_path):
    module = worker()
    cpu = min(os.sched_getaffinity(0))
    code = '''import json,os,resource,subprocess,sys
from scripts.archetype_matrix_worker import apply_limits, install_guard
x=apply_limits(int(sys.argv[1]),2,2147483648)
install_guard()
try:
 subprocess.Popen([sys.executable,"-c","print('must not run')"])
except RuntimeError:
 blocked=True
else:
 blocked=False
print(json.dumps(dict(x, blocked=blocked)))
'''
    value = subprocess.run([sys.executable, '-B', '-c', code, str(cpu)],
        cwd=Path(__file__).parents[1], text=True, capture_output=True, timeout=5)
    assert value.returncode == 0, value.stderr
    record = json.loads(value.stdout)
    assert record['affinity'] == [cpu] and record['memory_bytes'] == 2147483648
    assert record['cpu_soft_seconds'] == 2 and record['blocked'] is True


def test_selected_boundaries_include_first_last_and_every_100():
    assert worker().selected_steps(251) == {0, 100, 200, 250}
    assert worker().selected_steps(1) == {0}
    assert worker().selected_steps(0) == set()


def test_offline_token_cache_uses_only_the_private_cell_directory(tmp_path, monkeypatch):
    module = worker()
    assert callable(getattr(module, 'configure_cache', None)), 'Private worker cache binding is missing'
    from card_data import placeholders, sync, token_images
    for owner, attribute in ((placeholders, 'CACHE_DIR'), (sync, 'CACHE_DIR'),
                             (token_images, 'CACHE_DIR'), (token_images, '_INDEX_FILE')):
        monkeypatch.setattr(owner, attribute, getattr(owner, attribute))
    old_cache = token_images._TOKEN_IMAGE_CACHE.copy()
    try:
        module.configure_cache(tmp_path/'private-cache')
        uri = token_images.resolve_token_image_uri('unit unavailable token', 1, 1)
        assert uri == '/card-images/generic-token-creature.svg'
        assert (tmp_path/'private-cache/generic-token-creature.svg').is_file()
        assert placeholders.CACHE_DIR == sync.CACHE_DIR == token_images.CACHE_DIR == tmp_path/'private-cache'
        assert token_images._INDEX_FILE == tmp_path/'private-cache/token-index.json'
        assert not token_images._INDEX_FILE.exists()
    finally:
        token_images._TOKEN_IMAGE_CACHE.clear()
        token_images._TOKEN_IMAGE_CACHE.update(old_cache)


def test_module_imports_do_not_boot_application_or_database(tmp_path):
    import json
    code = '''import importlib,json,sys
for suffix in ('execution','game','api_check','pilot','worker'):
 importlib.import_module('scripts.archetype_matrix_'+suffix)
print(json.dumps({'main': 'main' in sys.modules, 'db': 'persistence.db' in sys.modules}))
'''
    result = subprocess.run([sys.executable, '-B', '-c', code], cwd=tmp_path,
        env={**os.environ, 'PYTHONPATH': str(Path(__file__).parents[1])},
        text=True, capture_output=True, timeout=5)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {'main': False, 'db': False}
    assert not list(tmp_path.iterdir())
