"""Exact fixture-body projection with public trees and inert process/socket inputs."""
import ast
from copy import deepcopy
import importlib
import json
import os
from pathlib import Path
import shutil
import signal
from types import SimpleNamespace

import pytest


MODULES = (
    ('test_private_choice_http_restart.py', 'Server'),
    ('test_library_choice_http_audit.py', 'LibraryServer'),
    ('test_land_consumer_variants_http.py', 'VariantServer'),
    ('test_activated_handland_http_audit.py', 'ActivatedServer'),
    ('test_optional_land_choice_http_stage.py', 'LandServer'),
)


def projected_caller(tmp_path, monkeypatch, module, server_name, *, override, startup_error=None):
    base = tmp_path / (module.removesuffix('.py') + ('-ci' if override else '-local'))
    base.mkdir()
    source = base / 'public-source/backend'
    (source / 'tests').mkdir(parents=True)
    fake_file = source / 'tests' / module
    fake_file.write_text('PUBLIC FAKE SOURCE, NOT A BACKEND\n')
    (source / 'public.txt').write_bytes(b'PUBLIC FAKE PAYLOAD\x00\xff')
    stage = base / 'declared-stage'
    stage.mkdir()
    monkeypatch.setenv('MTG_LAND_CHOICE_STAGE_EVIDENCE', str(stage))
    runtime = stage / 'owned-runtime'
    runtime.mkdir()
    pytest_base = base / 'pytest-base'
    pytest_base.mkdir()
    ci = base / 'ci-evidence'
    ci.mkdir()
    if override:
        monkeypatch.setenv('MTG_CI_EVIDENCE', str(ci))
    else:
        monkeypatch.delenv('MTG_CI_EVIDENCE', raising=False)
    observations = {'helper_calls': [], 'factory_calls': 0, 'stop_calls': 0, 'instances': []}
    helper = importlib.import_module('tests.closed_http_runtime')

    class Factory:
        def getbasetemp(self):
            observations['factory_calls'] += 1
            assert not override, 'Explicit CI override must not consult fallback factory'
            return pytest_base

    class Socket:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def bind(self, address):
            assert address == ('127.0.0.1', 0)

        def getsockname(self):
            return ('127.0.0.1', 18413)

    class Process:
        pid = 41
        returncode = None

        def poll(self):
            return self.returncode

        def wait(self, timeout):
            assert timeout == 0
            return self.returncode

    class Server:
        def __init__(self, root, port):
            assert root == runtime and port == 18413
            self.root, self.port = root, port
            self.proc, self.starts, self.token = None, [], 'PUBLIC FAKE TOKEN'
            (root / '.private-choice-owned').write_text(self.token)
            if server_name != 'Server':
                self.data = root.parent / 'cold-restart-data' / root.name
                self.data.mkdir(parents=True)
                (self.data / 'public.txt').write_text('PUBLIC FAKE DATA, NOT SQLITE\n')
            observations['instances'].append(self)

        def start(self):
            if startup_error is not None:
                raise startup_error
            self.proc = Process()
            self.starts.append(self.proc.pid)

        def stop(self):
            observations['stop_calls'] += 1
            if self.proc is not None:
                self.proc.returncode = -signal.SIGTERM
                if hasattr(self, 'data'):
                    (self.data / 'closure-41.json').write_text(json.dumps(
                        {'pid': 41, 'registered_owners': 0, 'pool_checkedout': 0}))

    def archive(server, **kwargs):
        observations['helper_calls'].append(kwargs)
        return helper.archive_closed_http_runtime(server, **kwargs)

    def allocate(*, prefix, dir=None):
        assert prefix in {'mtg-private-choice-http-', 'mtg-library-choice-http-',
                          'mtg-land-consumer-http-', 'http-local-'}
        assert dir is None or Path(dir) == stage
        return str(runtime)

    def filesystem(command, *, text):
        assert command == ['stat', '-f', '-c', '%T', str(runtime)] and text
        return 'ext4\n'

    actual = Path(__file__).with_name(module)
    tree = ast.parse(actual.read_text(), filename=str(actual))
    definition = deepcopy(next(node for node in tree.body
                               if isinstance(node, ast.FunctionDef) and node.name == 'server'))
    definition.decorator_list = []
    namespace = {'__file__': str(fake_file), 'Path': Path, 'json': json, 'os': os,
                 'shutil': shutil, 'tempfile': SimpleNamespace(mkdtemp=allocate),
                 'subprocess': SimpleNamespace(check_output=filesystem),
                 'socket': SimpleNamespace(socket=Socket), server_name: Server,
                 'archive_closed_http_runtime': archive}
    exec(compile(ast.Module(body=[definition], type_ignores=[]), str(actual), 'exec'), namespace)
    args = {'tmp_path_factory': Factory()} if definition.args.args else {}
    return namespace['server'](**args), observations, runtime, ci, pytest_base


def test_actual_private_caller_startup_none_preserves_exception_and_roots(tmp_path, monkeypatch):
    failure = OSError('PUBLIC FAKE STARTUP FAILURE')
    caller, seen, runtime, ci, _ = projected_caller(
        tmp_path, monkeypatch, *MODULES[0], override=True, startup_error=failure)
    with pytest.raises(OSError) as caught:
        next(caller)
    assert caught.value is failure
    assert seen['stop_calls'] == 1 and seen['helper_calls'] == []
    assert seen['factory_calls'] == 0 and seen['instances'][0].proc is None
    assert json.loads((runtime / 'process-receipt.json').read_text())['stopped'] is False
    assert runtime.is_dir() and not list(ci.iterdir())
    assert (runtime / 'backend/public.txt').read_bytes() == b'PUBLIC FAKE PAYLOAD\x00\xff'


def test_all_actual_callers_fallback_and_explicit_ci_evidence_are_outside_roots(tmp_path, monkeypatch):
    failures = {}
    for module, name in MODULES:
        for override in (False, True):
            caller, seen, runtime, ci, pytest_base = projected_caller(
                tmp_path, monkeypatch, module, name, override=override)
            owned = next(caller)
            assert owned is seen['instances'][0]
            try:
                next(caller)
            except StopIteration:
                pass
            except Exception as exc:
                failures[(module, override)] = type(exc).__name__
                continue
            else:
                raise AssertionError('Actual finalizer must finish')
            expected = ci if override else pytest_base / 'closed-http-evidence'
            assert seen['stop_calls'] == 1 and len(seen['helper_calls']) == 1
            assert seen['helper_calls'][0]['evidence_root'] == expected
            assert seen['factory_calls'] == (0 if override else 1)
            assert not expected.is_relative_to(runtime)
            assert not runtime.is_relative_to(expected)
            assert not runtime.exists()
            if hasattr(owned, 'data'):
                assert not expected.is_relative_to(owned.data) and not owned.data.exists()
            receipt = json.loads((expected / 'closed-http-runtime/owned-runtime/VERIFIED.json').read_text())
            assert receipt['byte_member_inode_verified'] is True
            assert Path(receipt['archive']).is_relative_to(expected)
    assert not failures, failures
