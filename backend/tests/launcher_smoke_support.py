"""Disposable application-only source and explicit child environment for smoke tests."""
import os
from pathlib import Path
import shutil


EXCLUDED = {'.git', '.venv', 'venv', '__pycache__', '.pytest_cache', '.cache',
            'node_modules', 'tests', 'image_cache', 'diagnostics', 'training_runs',
            'runtime', 'generated', 'evidence', 'logs'}


def copy_application(source, destination):
    source, destination = Path(source), Path(destination)
    destination.mkdir(mode=0o700)
    backend = source/'backend'
    for directory, names, files in os.walk(backend, followlinks=False):
        base = Path(directory)
        names[:] = [name for name in names if name not in EXCLUDED
                    and not (base/name).is_symlink()
                    and (base/name).relative_to(backend).parts != ('knowledge', 'data')]
        for name in files:
            path = base/name
            if path.suffix not in ('.py', '.json', '.svg') or path.is_symlink() or not path.is_file():
                continue
            target = destination/'backend'/path.relative_to(backend)
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with path.open('rb') as src, target.open('xb') as dst:
                shutil.copyfileobj(src, dst)


def worker_environment(backend, database):
    return {'PATH': os.environ.get('PATH', '/usr/bin:/bin'), 'LANG': 'C.UTF-8',
            'PYTHONPATH': str(backend), 'PYTHONDONTWRITEBYTECODE': '1',
            'PYTHONNOUSERSITE': '1', 'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1',
            'MTG_DATABASE_PATH': str(database),
            'MTG_TRUSTED_ORIGINS': 'http://testserver'}
