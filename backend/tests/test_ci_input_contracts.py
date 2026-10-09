"""Pure checks for portable CI ownership and exact canonical deck inputs."""
from collections import Counter
import ast
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from tests import ci_input_contracts as inputs


@pytest.fixture
def ci_root(tmp_path, monkeypatch):
    root = tmp_path / 'source'
    (root / 'backend/tests').mkdir(parents=True)
    for marker in ('.private', '.private-choice-audit-source'):
        (root / marker).write_text(str(root))
    monkeypatch.setattr(inputs, '__file__', str(root / 'backend/tests/ci_input_contracts.py'))
    monkeypatch.setenv('GITHUB_ACTIONS', 'true')
    monkeypatch.setenv('RUNNER_TEMP', str(tmp_path))
    monkeypatch.setenv('MTG_ISOLATED_TEST_ROOT', str(root))
    return root


def test_owned_source_requires_real_archive_and_exact_markers(ci_root):
    assert inputs.assert_github_owned_source() == ci_root


@pytest.mark.parametrize('invalid', ['not-ci', 'different-root', 'outside-temporary',
                                     'git', 'private-marker', 'choice-marker', 'db-symlink'])
def test_invalid_ownership_never_admits_protected_inputs(ci_root, monkeypatch, invalid):
    if invalid == 'not-ci':
        monkeypatch.setenv('GITHUB_ACTIONS', 'false')
    elif invalid == 'different-root':
        monkeypatch.setenv('MTG_ISOLATED_TEST_ROOT', str(ci_root.parent / 'other'))
    elif invalid == 'outside-temporary':
        monkeypatch.setenv('RUNNER_TEMP', str(ci_root / 'unrelated'))
    elif invalid == 'git':
        (ci_root / '.git').touch()
    elif invalid in ('private-marker', 'choice-marker'):
        marker = '.private' if invalid == 'private-marker' else '.private-choice-audit-source'
        (ci_root / marker).write_text(str(ci_root.parent))
    else:
        (ci_root / 'backend/mtg_lab.db').symlink_to(ci_root.parent / 'absent.sqlite')
    with pytest.raises(AssertionError):
        inputs.assert_github_owned_source()


def test_bo3_deck_projection_is_sealed_and_not_a_preflight_certificate():
    directory = Path(__file__).parent / 'fixtures'
    path = directory / 'human_bo3_selected_decks.json'
    provenance = json.loads((directory / 'human_bo3_selected_decks.provenance.json').read_text())
    assert hashlib.sha256(path.read_bytes()).hexdigest() == provenance['fixture_sha256']
    assert set(json.loads(path.read_text())) == {'decks'}
    decks = inputs.human_bo3_decks()
    assert len(decks) == 2
    for number, lines in enumerate(decks):
        quantities = Counter()
        for line in lines:
            assert type(line['quantity']) is int and line['quantity'] > 0
            quantities[line['card_name']] += line['quantity']
        assert sum(quantities.values()) == 60
        assert quantities['Shock'] == 4 and quantities['Searing Blaze'] == 0
        assert quantities['Soul-Scar Mage' if number == 0 else 'Goblin Guide'] == 4
        assert quantities['Goblin Guide' if number == 0 else 'Soul-Scar Mage'] == 0
    decks[0].clear()
    assert sum(line['quantity'] for line in inputs.human_bo3_decks()[0]) == 60


def test_private_receipt_assertions_remain_active_without_payload_messages():
    for name in ('test_natural_heat_target_audit.py', 'test_friendly_damage_materialization.py'):
        tree = ast.parse(Path(__file__).with_name(name).read_text())
        assert 'PYTEST_DONT_REWRITE' in ast.get_docstring(tree)
        assertions = [node for node in ast.walk(tree) if isinstance(node, ast.Assert)]
        assert assertions
        assert all(node.msg is None or isinstance(node.msg, ast.Constant)
                   and isinstance(node.msg.value, str) for node in assertions)


def cold_functions(database):
    path = Path(__file__).with_name('human_bo3_cold_worker.py')
    tree = ast.parse(path.read_text())
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    namespace = {'Path': Path, 'database': database}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace


def test_cold_connection_contract_requires_exact_owned_readonly_uri(tmp_path):
    database = tmp_path / 'owned.sqlite'
    namespace = cold_functions(database)
    valid = 'file:' + str(database) + '?mode=ro'
    assert namespace['require_readonly_database'](valid) is None
    assert namespace['require_readonly_database'](valid + '&uri=true') is None
    for invalid in (str(database), ':memory:', 'file:relative?mode=ro',
                    'file:' + str(tmp_path / 'foreign.sqlite') + '?mode=ro',
                    valid.replace('mode=ro', 'mode=rw'), valid + '&mode=rw',
                    valid + '&mode=ro', valid + '&%6dode=rw'):
        with pytest.raises(RuntimeError):
            namespace['require_readonly_database'](invalid)
    namespace['native_connect'] = lambda *args, **kwargs: ('validated', args, kwargs)
    with pytest.raises(RuntimeError):
        namespace['readonly_connect'](valid)
    assert namespace['readonly_connect'](valid, uri=True)[0] == 'validated'


@pytest.mark.parametrize('event', ['socket.connect', 'socket.bind', 'socket.getaddrinfo',
                                   'socket.sendto', 'socket.sendmsg', 'socket.gethostbyname',
                                   'socket.gethostbyaddr', 'socket.getnameinfo',
                                   'subprocess.Popen', 'os.system', 'os.posix_spawn',
                                   'os.exec', 'os.fork', 'os.forkpty'])
def test_cold_child_boundary_rejects_network_and_descendants(tmp_path, event):
    namespace = cold_functions(tmp_path / 'owned.sqlite')
    with pytest.raises(RuntimeError):
        namespace['audit'](event, ())


def private_input_module():
    path = Path(__file__).resolve().parents[2] / '.github/scripts/prepare-backend-private-inputs.py'
    spec = importlib.util.spec_from_file_location('private_input_fixture', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def synthetic_chunks(module, monkeypatch):
    import base64
    import gzip
    payload = b'{"synthetic":true}\n'
    encoded = base64.b64encode(gzip.compress(payload, mtime=0)).decode()
    parts = [encoded[index:index + 4] for index in range(0, 48, 4)] + [encoded[48:]]
    assert len(parts) == 13 and all(parts)
    monkeypatch.setattr(module, 'WITNESS_SHA256', hashlib.sha256(payload).hexdigest())
    return payload, {f'MTG_HEAT_WITNESS_{index:02d}': part for index, part in enumerate(parts, 1)}


def test_private_input_roundtrip_is_exclusive_and_owner_only(tmp_path, monkeypatch):
    module = private_input_module()
    payload, chunks = synthetic_chunks(module, monkeypatch)
    directory = tmp_path / 'private-inputs'
    result = module.restore_witness(chunks, directory)
    assert result.name == 'sealed-self-removal-witness.json'
    assert result.read_bytes() == payload
    assert directory.stat().st_mode & 0o777 == 0o700
    assert result.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        module.restore_witness(chunks, directory)
    assert result.read_bytes() == payload


@pytest.mark.parametrize('invalid', ['missing', 'oversized', 'base64', 'gzip', 'hash'])
def test_private_input_refuses_invalid_parts_before_writing(tmp_path, monkeypatch, invalid):
    module = private_input_module()
    _, chunks = synthetic_chunks(module, monkeypatch)
    if invalid == 'missing':
        chunks['MTG_HEAT_WITNESS_05'] = ''
    elif invalid == 'oversized':
        chunks['MTG_HEAT_WITNESS_01'] = 'a' * 48_001
    elif invalid == 'base64':
        chunks['MTG_HEAT_WITNESS_01'] = '!!!!'
    elif invalid == 'gzip':
        chunks['MTG_HEAT_WITNESS_01'] = 'AAAA'
    else:
        monkeypatch.setattr(module, 'WITNESS_SHA256', '0' * 64)
    destination = tmp_path / 'not-created'
    with pytest.raises(ValueError) as failure:
        module.restore_witness(chunks, destination)
    if invalid in ('base64', 'gzip'):
        assert failure.value.__cause__ is None and failure.value.__suppress_context__
    assert not destination.exists()
