"""Genuine Factory/serde with inert callbacks; not HTTP or child acceptance."""
import ast
from contextlib import nullcontext
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone
from tests import spell_admission_safety_support as support
from tests import test_fixture_binding_transitions as protocol


ROOT = Path(__file__).parent


class PersistReached(Exception):
    pass


def boundary(monkeypatch):
    main, repo, client, controller, calls = protocol.transport(monkeypatch)
    identifier = controller.state.id
    births = []

    def position(*args, **kwargs):
        state = support.position(*args, **kwargs)
        births.append((deepcopy(kwargs), state.sideboard_facts['game_id'], state))
        return state

    def persist(repository, current):
        snapshot = serialize_match_snapshot(current.state)
        restored = deserialize_match_snapshot(snapshot)
        assert serialize_match_snapshot(restored) == snapshot
        assert current.state.id == current.state.sideboard_facts['game_id'] == identifier
        assert main.ACTIVE_MATCHES == {identifier: current}
        calls.append(('persist', snapshot))
        raise PersistReached

    main._persist_active_match = persist
    namespace = {'pytest': pytest, 'UNSUPPORTED': support.UNSUPPORTED,
        'seed_cache': support.seed_cache, 'position': position, 'add': support.add,
        'Zone': Zone, 'deepcopy': deepcopy, 'main': main,
        'Session': lambda engine: nullcontext(repo), 'Repository': lambda session: session,
        'db': SimpleNamespace(engine=None)}
    return namespace, repo, client, controller, births, calls


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', [
    'test_actual_http_full_unsupported_rejection_is_explicit_and_atomic',
    'test_invalid_real_face_choices_remain_structured_and_root_pure'])
def test_original_http_installer_birth_identity_reaches_genuine_serde(monkeypatch, seat, name):
    namespace, repo, client, controller, births, calls = boundary(monkeypatch)
    function = protocol.definition('test_spell_admission_safety_http.py', name, namespace)
    with pytest.raises(PersistReached):
        if name == 'test_invalid_real_face_choices_remain_structured_and_root_pure':
            function(repo, client, seat, -1)
        else:
            function(repo, client, seat, 'Temporal Mastery')
    assert births[0][0]['game_id'] == births[0][1] == controller.state.id
    assert len(calls) == 1 and calls[0][0] == 'persist'
    assert controller.revision == 9 and controller.mode == 'unchanged'
    assert all(binding['stock_key'] == 'Island'
               for binding in controller.state.sideboard_facts['inventory'].values())


def seed_definition(namespace):
    """Only original seed statements; no worker startup/import/SQL emulation."""
    path = ROOT / 'spell_admission_safety_restart_worker.py'
    tree = ast.parse(path.read_text())
    worker = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'run')
    seed = next(node for node in ast.walk(worker) if isinstance(node, ast.If)
                and ast.dump(node.test) == ast.dump(ast.parse("phase == 'seed'", mode='eval').body))
    function = ast.parse('def projected_seed(client, seat, name):\n    pass\n').body[0]
    function.body = deepcopy(seed.body)
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    exec(compile(module, str(path), 'exec'), namespace)
    return namespace['projected_seed']


@pytest.mark.parametrize('seat', [1, 2])
def test_original_worker_seed_birth_identity_reaches_genuine_serde(monkeypatch, seat):
    namespace, _, client, controller, births, calls = boundary(monkeypatch)
    seed = seed_definition(namespace)
    with pytest.raises(PersistReached):
        seed(client, seat, 'Temporal Mastery')
    assert births[0][0]['game_id'] == births[0][1] == controller.state.id
    assert len(calls) == 1 and calls[0][0] == 'persist'
    assert controller.revision == 9 and controller.mode == 'unchanged'


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_postcapture_id_transplant_is_still_rejected(seat):
    state = support.position(seat)
    original = state.sideboard_facts['game_id']
    state.id = 'different-controlled-controller'
    with pytest.raises(ValueError, match='Invalid private sideboard facts'):
        serialize_match_snapshot(state)
    assert state.sideboard_facts['game_id'] == original


@pytest.mark.parametrize('seat', [1, 2])
def test_supplied_birth_preserves_stock_rng_and_default_uuid(seat):
    state = support.position(seat, game_id='declared-controller')
    replica = support.position(seat, game_id='declared-controller')
    snapshot = serialize_match_snapshot(state)
    assert serialize_match_snapshot(replica) == snapshot
    assert serialize_match_snapshot(deserialize_match_snapshot(snapshot)) == snapshot
    assert state.rng.getstate() == replica.rng.getstate()
    assert len(state.sideboard_facts['inventory']) == len(state.cards) == 120
    default = support.position(seat)
    assert UUID(default.id).version == 4
    assert default.id == default.sideboard_facts['game_id']
    assert default.starting_decks == state.starting_decks
    assert default.rng.getstate() == state.rng.getstate()


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('corruption', ['facts_identity', 'printed_source'])
def test_genuine_capture_corruption_remains_failclosed(seat, corruption):
    state = support.position(seat, game_id='strict-captured-controller')
    if corruption == 'facts_identity':
        state.sideboard_facts['game_id'] = 'forged-controller'
    else:
        next(iter(state.cards.values())).printed_characteristics['name'] = 'forged-source'
    with pytest.raises(ValueError):
        serialize_match_snapshot(state)
