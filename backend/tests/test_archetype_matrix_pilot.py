"""Synthetic child-process lifecycle checks; no measured game/pilot launched."""
import importlib
import importlib.util
import os
from pathlib import Path
import sys
import threading

import pytest


def pilot():
    name = 'scripts.archetype_matrix_pilot'
    assert importlib.util.find_spec(name) is not None, 'Bounded pilot driver is missing'
    return importlib.import_module(name)


def test_private_publish_is_exclusive_and_refuses_existing_output(tmp_path):
    module = pilot()
    path = tmp_path / 'result.json'
    module.publish(path, {'complete': False})
    assert path.stat().st_mode & 0o777 == 0o600
    before = path.read_bytes()
    with pytest.raises(FileExistsError): module.publish(path, {'complete': True})
    assert path.read_bytes() == before


def test_owned_child_timeout_and_wait(tmp_path):
    module = pilot()
    stop = threading.Event()
    result = module.run_process([sys.executable, '-c', 'import time; time.sleep(5)'],
        directory=tmp_path, name='sleep', environment=os.environ.copy(),
        seconds=0.1, stop=stop)
    assert result['termination'] == 'wall_limit' and result['waited'] is True
    assert result['returncode'] is not None


def test_completed_child_records_actual_wait_and_opaque_logs(tmp_path):
    module = pilot()
    result = module.run_process([sys.executable, '-c', 'print("synthetic stdout")'],
        directory=tmp_path, name='done', environment=os.environ.copy(),
        seconds=2, stop=threading.Event())
    assert result['returncode'] == 0 and result['waited'] is True
    assert result['termination'] is None
    assert (tmp_path/'done.stdout').read_text().strip() == 'synthetic stdout'


def test_cancelled_batch_does_not_start_a_new_child(tmp_path):
    module = pilot()
    stop = threading.Event(); stop.set()
    result = module.run_process([sys.executable, '-c', 'raise RuntimeError("must not run")'],
        directory=tmp_path, name='never', environment=os.environ.copy(), seconds=1, stop=stop)
    assert result['termination'] == 'cancelled' and result['started'] is False
    assert not list(tmp_path.iterdir())


def test_pilot_report_keeps_limits_in_denominator_and_never_accepts_matrix():
    module = pilot()
    rows = [{'status': 'resolved', 'seconds': 1.0, 'cpu_seconds': .5, 'peak_rss_bytes': 100,
             'trace_bytes': 1000, 'replay_seconds': .2},
            {'status': 'timeout', 'seconds': 120.0, 'cpu_seconds': None, 'peak_rss_bytes': None,
             'trace_bytes': 500, 'replay_seconds': None}]
    report = module.pilot_report(rows, scheduled=36)
    assert report['scheduled'] == 36 and report['accounted'] == 2
    assert report['complete'] is False and report['accepts_matrix_or_strength'] is False
    assert report['statuses'] == {'resolved': 1, 'timeout': 1}
    assert report['forecast_1440_games_seconds'] is None


def test_forecast_uses_all_36_cells_including_timeouts():
    module = pilot()
    rows = [{'status': 'timeout', 'seconds': 120.0, 'cpu_seconds': None, 'peak_rss_bytes': None,
             'trace_bytes': 500, 'replay_seconds': None} for _ in range(36)]
    report = module.pilot_report(rows, scheduled=36)
    assert report['complete'] is True
    assert report['forecast_1440_games_seconds'] == 1440 * 120 / 2
    assert report['statuses'] == {'timeout': 36}
    assert report['accepts_matrix_or_strength'] is False


def test_worker_environment_drops_private_and_app_settings(monkeypatch):
    module = pilot()
    monkeypatch.setenv('MTG_PRIVATE_TEST_CANARY', 'do-not-forward')
    monkeypatch.setenv('PYTHONPATH', '/untrusted')
    value = module.worker_environment(Path('/owned/backend'))
    assert not any(k.startswith('MTG_') for k in value)
    assert value['PYTHONPATH'] == '/owned/backend'
    assert value['PYTHONHASHSEED'] == '0' and value['OMP_NUM_THREADS'] == '1'


def make_pilot():
    from scripts.archetype_matrix_plan import build_plan
    from scripts.archetype_matrix_execution import build_pilot
    matrix = build_plan('a'*40, (Path(__file__).parents[1]/'decks/builtin_decks.py').read_text())
    return build_pilot(matrix, 'archetype-pilot-20261116-v2-unit-driver')


def test_controller_accounts_for_all_36_authored_cells_with_at_most_two_in_flight(tmp_path, monkeypatch):
    module = pilot()
    plan, active, peak, observed = make_pilot(), 0, 0, []
    lock = threading.Lock()
    rendezvous = threading.Barrier(2, timeout=5)
    monkeypatch.setattr(module, 'source_identity', lambda revision: {'revision': revision})
    monkeypatch.setattr(module, 'verify_sources', lambda source: None)
    monkeypatch.setattr(module, 'runtime_identity', lambda: {'authored': True})
    monkeypatch.setattr(module.os, 'sched_getaffinity', lambda pid: {0, 1, 2})
    monkeypatch.setattr(module, 'available_memory', lambda: 10*1024**3)
    def authored(plan, cell, directory, **kwargs):
        nonlocal active, peak
        with lock:
            active += 1; peak = max(peak, active); observed.append(cell['cell_id'])
        rendezvous.wait()
        with lock: active -= 1
        return {'cell_id': cell['cell_id'], 'status': 'timeout', 'seconds': 120.,
                'cpu_seconds': None, 'peak_rss_bytes': None, 'trace_bytes': 0,
                'replay_seconds': None, 'run_invalid': False}
    monkeypatch.setattr(module, 'run_cell', authored)
    report = module.run_pilot(plan, tmp_path/'pilot')
    assert report['complete'] is True and report['accounted'] == 36
    assert set(observed) == {cell['cell_id'] for cell in plan['cells']}
    assert len(observed) == 36 and peak == 2
    assert report['statuses'] == {'timeout': 36}
    assert report['accepts_matrix_or_strength'] is False
    with pytest.raises(FileExistsError): module.run_pilot(plan, tmp_path/'pilot')


def test_controller_failure_cannot_publish_complete_or_refill_after_stop(tmp_path, monkeypatch):
    module = pilot()
    plan, calls = make_pilot(), []
    monkeypatch.setattr(module, 'source_identity', lambda revision: {})
    monkeypatch.setattr(module, 'verify_sources', lambda source: None)
    monkeypatch.setattr(module, 'runtime_identity', lambda: {})
    monkeypatch.setattr(module.os, 'sched_getaffinity', lambda pid: {0, 1, 2})
    monkeypatch.setattr(module, 'available_memory', lambda: 10*1024**3)
    def fail(plan, cell, directory, **kwargs):
        calls.append(cell['cell_id'])
        kwargs['stop'].set()
        raise OSError('authored controller failure')
    monkeypatch.setattr(module, 'run_cell', fail)
    report = module.run_pilot(plan, tmp_path/'broken')
    assert not report['complete'] and 1 <= len(calls) <= 2
    assert (tmp_path/'broken/PILOT-INCOMPLETE.json').exists()
    assert not (tmp_path/'broken/PILOT-COMPLETE.json').exists()


def test_insufficient_host_affinity_refuses_before_creating_output(tmp_path, monkeypatch):
    module = pilot()
    monkeypatch.setattr(module, 'source_identity', lambda revision: {})
    monkeypatch.setattr(module, 'runtime_identity', lambda: {})
    monkeypatch.setattr(module.os, 'sched_getaffinity', lambda pid: {0, 1})
    monkeypatch.setattr(module, 'run_cell', lambda *a, **kw: pytest.fail('No worker should launch'))
    with pytest.raises(ValueError): module.run_pilot(make_pilot(), tmp_path/'not-created')
    assert not (tmp_path/'not-created').exists()


@pytest.mark.parametrize('fault', ['partial_timeout', 'missing_result', 'unwaited', 'runtime_pin', 'replay_status', 'verify_failure', 'verify_missing', 'verify_unwaited', 'verify_crash', 'none'])
def test_cell_protocol_failure_is_not_success_and_never_retries(tmp_path, monkeypatch, fault):
    import json
    import signal
    from scripts.archetype_matrix_plan import digest
    module = pilot()
    plan, stop, calls = make_pilot(), threading.Event(), []
    cell, source, runtime = plan['cells'][0], {'authored': 'source'}, {'authored': 'runtime'}
    monkeypatch.setattr(module, 'verify_sources', lambda value: None)
    monkeypatch.setattr(module, 'runtime_identity', lambda: runtime)
    def authored(command, *, directory, name, environment, seconds, stop):
        calls.append(name)
        request = json.loads((directory/f'{name}-request.json').read_text())
        target = directory/f'{name}-result.json'
        if fault == 'partial_timeout':
            target.write_text('{')
            return {'started': True, 'waited': True, 'returncode': -signal.SIGALRM, 'termination': None}
        result = {'cell_id': cell['cell_id'], 'mode': name, 'source_sha256': digest(source),
            'runtime_sha256': digest(runtime), 'cpu_seconds': 2.5, 'peak_rss_bytes': 1000,
            'controls': {'affinity': [0], 'memory_bytes': 2147483648,
                         'cpu_soft_seconds': request['cpu_seconds']}}
        if name == 'game':
            trace = directory/'trace.jsonl'; trace.write_text('authored worker fixture\n')
            result.update(trace_sha256=module.file_sha(trace),
                outcome={'status': 'resolved', 'winner': 1, 'termination': 'life', 'accepted_actions': 1})
        else:
            result.update(replay={'matched': True, 'actions': 1,
                'status': 'draw' if fault == 'replay_status' else 'resolved'},
                handler_boundaries=[], replay_seconds=.1)
        if fault == 'runtime_pin': result['runtime_sha256'] = 'b'*64
        if fault != 'missing_result' and not (fault == 'verify_missing' and name == 'verify'):
            target.write_text(json.dumps(result))
        return {'started': True,
                'waited': fault != 'unwaited' and not (fault == 'verify_unwaited' and name == 'verify'),
                'returncode': (-signal.SIGSEGV if fault == 'verify_crash' and name == 'verify' else
                               1 if fault == 'verify_failure' and name == 'verify' else 0), 'termination': None}
    monkeypatch.setattr(module, 'run_process', authored)
    result = module.run_cell(plan, cell, tmp_path/'cell', cpu=0,
                              source=source, runtime=runtime, stop=stop)
    if fault == 'partial_timeout':
        assert result['status'] == 'timeout' and result['termination'] == 'wall_limit'
        assert result['run_invalid'] is False and calls == ['game']
    elif fault in ('missing_result', 'unwaited', 'runtime_pin'):
        assert result['status'] == 'error' and result['termination'] == 'worker_protocol'
        assert calls == ['game']
    elif fault in ('verify_failure', 'verify_missing', 'verify_unwaited'):
        assert result['status'] == 'error' and result['winner'] is None
        assert result['parity_checked'] is False and calls == ['game', 'verify']
    elif fault == 'verify_crash':
        assert result['status'] == 'error' and result['winner'] is None
        assert result['run_invalid'] is True and stop.is_set()
        assert result['termination'] == 'worker_crash' and calls == ['game', 'verify']
    elif fault == 'replay_status':
        assert result['status'] == 'replay_divergence' and calls == ['game', 'verify']
    else:
        assert result['status'] == 'resolved' and calls == ['game', 'verify']
        verify_request = json.loads((tmp_path/'cell/verify-request.json').read_text())
        assert verify_request['cpu_seconds'] == 87  # remaining cumulative budget rounded down
        assert 0 < verify_request['wall_seconds'] < 120


def test_measured_source_identity_refuses_dirty_untracked_and_foreign_revision(tmp_path, monkeypatch):
    import subprocess
    module = pilot()
    root = tmp_path/'source'; backend = root/'backend'; backend.mkdir(parents=True)
    (backend/'sample.py').write_text('VALUE = 1\n')
    (backend/'data.json').write_text('{"unit":true}\n')
    (root/'.gitignore').write_text('*.db\n')
    def git(*args):
        return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()
    git('init', '-q'); git('add', '.')
    git('-c', 'user.name=Unit fixture', '-c', 'user.email=fixture@localhost', 'commit', '-qm', 'unit source')
    revision = git('rev-parse', 'HEAD')
    monkeypatch.setattr(module, 'BACKEND', backend)
    source = module.source_identity(revision)
    assert set(source['files']) == {'backend/sample.py', 'backend/data.json'}
    module.verify_sources(source)
    (backend/'mtg_lab.db').write_bytes(b'unit file must never be opened by measurement')
    with pytest.raises(ValueError, match='source-local'): module.source_identity(revision)
    (backend/'mtg_lab.db').unlink()
    with pytest.raises(ValueError): module.source_identity('b'*40)
    (root/'untracked.txt').write_text('unit')
    with pytest.raises(ValueError): module.source_identity(revision)
    (root/'untracked.txt').unlink()
    (backend/'sample.py').write_text('VALUE = 2\n')
    with pytest.raises(ValueError): module.verify_sources(source)
    with pytest.raises(ValueError): module.source_identity(revision)


def test_locked_runtime_inventory_requires_all_28_exact_versions(tmp_path, monkeypatch):
    from types import SimpleNamespace
    module = pilot()
    names = [f'unit-package-{i}' for i in range(28)]
    (tmp_path/'requirements-py312-linux.lock').write_text(''.join(f'{n}==1.0\n' for n in names))
    monkeypatch.setattr(module, 'BACKEND', tmp_path)
    monkeypatch.setattr(module.importlib.metadata, 'version', lambda name: '1.0')
    monkeypatch.setattr(module.importlib.metadata, 'distributions', lambda: [
        SimpleNamespace(metadata={'Name': n}, version='1.0') for n in names])
    value = module.runtime_identity()
    assert value['application_packages'] == 28 and len(value['distributions']) == 28
    monkeypatch.setattr(module.importlib.metadata, 'version', lambda name: '2.0' if name == names[-1] else '1.0')
    with pytest.raises(ValueError): module.runtime_identity()


def test_insufficient_memory_headroom_refuses_before_creating_output(tmp_path, monkeypatch):
    module = pilot()
    assert callable(getattr(module, 'available_memory', None)), 'Host headroom admission is missing'
    monkeypatch.setattr(module, 'source_identity', lambda revision: {})
    monkeypatch.setattr(module, 'runtime_identity', lambda: {})
    monkeypatch.setattr(module.os, 'sched_getaffinity', lambda pid: {0, 1, 2})
    monkeypatch.setattr(module, 'available_memory', lambda: 10*1024**3)
    monkeypatch.setattr(module, 'available_memory', lambda: 4*1024**3)
    monkeypatch.setattr(module, 'run_cell', lambda *a, **kw: pytest.fail('No worker should launch'))
    with pytest.raises(ValueError): module.run_pilot(make_pilot(), tmp_path/'not-created')
    assert not (tmp_path/'not-created').exists()
