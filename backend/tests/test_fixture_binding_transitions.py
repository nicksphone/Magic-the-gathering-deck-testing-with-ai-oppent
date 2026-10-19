"""Real Factory/serde with inert HTTP/repository callbacks; no SQL or HTTP proof."""
import ast
from copy import deepcopy
import json
from pathlib import Path
import pickle
from types import ModuleType, SimpleNamespace
import sys

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Zone
from tests import ai_knowledge_consumer_fixture as knowledge
from tests.extra_sequence_support import position
from tests.fixture_state_support import adopt_fixture_state
from tests.test_linked_damage_targets import raw_card


ROOT = Path(__file__).parent


def definition(filename, name, namespace, *, method=None):
    tree = ast.parse((ROOT / filename).read_text())
    node = next(n for n in tree.body if getattr(n, 'name', None) == name)
    if method:
        node = next(n for n in node.body if getattr(n, 'name', None) == method)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(ROOT / filename), 'exec'), namespace)
    return namespace[node.name]


def transport(monkeypatch):
    calls = []
    server_state = position(1, game_id='existing-http-fixture')
    controller = SimpleNamespace(state=server_state, mode='unchanged', revision=9)
    main = ModuleType('main')
    main.ACTIVE_MATCHES = {server_state.id: controller}

    def persist(repo, current):
        calls.append(('persist', serialize_match_snapshot(current.state)))

    main._persist_active_match = persist
    monkeypatch.setitem(sys.modules, 'main', main)
    repo = SimpleNamespace(upsert_card=lambda row: None,
                           delete_active_match=lambda identifier: calls.append(('delete', identifier)))
    client = SimpleNamespace(post=lambda *args, **kwargs: SimpleNamespace(
        status_code=200, text='inert protocol', json=lambda: {'id': server_state.id}))
    return main, repo, client, controller, calls


def assert_adopted(main, controller, state, calls, old_id):
    assert controller.state is state
    assert controller.mode == 'unchanged' and controller.revision == 9
    assert main.ACTIVE_MATCHES == {state.id: controller}
    assert calls == [('persist', serialize_match_snapshot(state)), ('delete', old_id)]
    assert state.id == state.sideboard_facts['game_id']


@pytest.mark.parametrize('seat', [1, 2])
def test_knowledge_identity_is_supplied_before_real_factory_capture(monkeypatch, seat):
    native = MatchFactory.from_decks
    births = []

    def observed(*args, **kwargs):
        result = native(*args, **kwargs)
        births.append((deepcopy(args), deepcopy(kwargs), result.sideboard_facts['game_id']))
        return result

    monkeypatch.setattr(MatchFactory, 'from_decks', staticmethod(observed))
    state = knowledge.position('Tempo', 'Ramp', seat)
    expected = f'knowledge-audit-Tempo-Ramp-{seat}-{knowledge.SEED}'
    assert births[0][1]['game_id'] == births[0][2] == state.id == expected
    assert births[0][1]['seed'] == knowledge.SEED == 701
    assert all(row['quantity'] > 0 for deck in births[0][0] for row in deck)
    assert set(state.sideboard_facts['inventory']) == set(state.cards)
    snapshot = serialize_match_snapshot(state)
    assert serialize_match_snapshot(deserialize_match_snapshot(snapshot)) == snapshot
    replica = knowledge.position('Tempo', 'Ramp', seat)
    assert serialize_match_snapshot(replica) == snapshot
    assert replica.rng.getstate() == state.rng.getstate()


@pytest.mark.parametrize('seat', [1, 2])
def test_overridden_noncreature_http_constructor_binds_before_position(monkeypatch, seat):
    main, repo, client, controller, calls = transport(monkeypatch)
    rows = {row['name']: row for row in map(json.loads, (
        ROOT / 'fixtures/noncreature_sba_caller/canonical.jsonl').read_text().splitlines())}
    births = []

    def birth(*args, **kwargs):
        state = position(*args, **kwargs)
        births.append((kwargs.get('game_id'), state.sideboard_facts['game_id']))
        return state

    harness = SimpleNamespace(persist=lambda: main._persist_active_match(repo, harness))
    initialize = definition('test_noncreature_sba_caller_audit.py', 'Harness', {
        'position': birth, 'ROWS': rows, 'normalize': lambda row: row,
        'raw_card': raw_card, 'Zone': Zone}, method='__init__')
    initialize(harness, seat, 'walker', False, client, repo)
    assert births == [(controller.state.id, controller.state.id)]
    assert harness.state.id == harness.state.sideboard_facts['game_id']
    assert len(calls) == 1 and calls[0][0] == 'persist'
    serialize_match_snapshot(harness.state)


@pytest.mark.parametrize('seat', [1, 2])
def test_direct_install_retains_real_birth_id_and_rekeys_callback_binding(monkeypatch, seat):
    main, repo, client, controller, calls = transport(monkeypatch)
    state = position(seat, game_id=f'genuine-direct-{seat}')
    before = pickle.dumps(state, 5)
    old_id = controller.state.id
    install = definition('test_direct_graveyard_bypass_audit.py', 'install', {
        'ROWS': {}, 'normalize': lambda row: row, 'adopt_fixture_state': adopt_fixture_state})
    assert install(repo, client, state) is controller
    assert_adopted(main, controller, state, calls, old_id)
    assert pickle.dumps(state, 5) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_multi_target_install_returns_the_retained_genuine_http_path(monkeypatch, seat):
    main, repo, client, controller, calls = transport(monkeypatch)
    state = position(seat, game_id=f'genuine-multi-{seat}')
    before = pickle.dumps(state, 5)
    old_id = controller.state.id
    targets, spell = ['protocol-target'], 'protocol-spell'
    install = definition('test_multi_target_immediate_return_http.py', 'install', {
        'http_position': lambda *args: (controller, None, None, '/matches/' + old_id),
        'case': lambda *args, **kwargs: (state, targets, spell),
        'adopt_fixture_state': adopt_fixture_state})
    result = install(repo, client, seat)
    assert result == (state, targets, spell, '/matches/' + state.id)
    assert_adopted(main, controller, state, calls, old_id)
    assert pickle.dumps(state, 5) == before


@pytest.mark.parametrize('corruption', ['identity', 'stock'])
def test_bad_direct_install_rejects_before_controller_registry_or_callbacks(monkeypatch, corruption):
    main, repo, client, controller, calls = transport(monkeypatch)
    state = position(1, game_id='genuine-corrupt-control')
    if corruption == 'identity':
        state.sideboard_facts['game_id'] = 'forged'
    else:
        next(iter(state.cards.values())).printed_characteristics['name'] = 'forged'
    before = pickle.dumps(state, 5)
    old_state, old_registry = controller.state, dict(main.ACTIVE_MATCHES)
    install = definition('test_direct_graveyard_bypass_audit.py', 'install', {
        'ROWS': {}, 'normalize': lambda row: row, 'adopt_fixture_state': adopt_fixture_state})
    with pytest.raises(ValueError):
        install(repo, client, state)
    assert controller.state is old_state and main.ACTIVE_MATCHES == old_registry
    assert calls == [] and pickle.dumps(state, 5) == before


@pytest.mark.parametrize('name', [
    'test_actual_http_admission_preflight_and_public_root_diagnostics_parity',
    'test_actual_http_second_spell_bounded_execution_matches_settled_helper'])
def test_readiness_callsite_protocol_adopts_without_postbirth_identity_assignment(name):
    tree = ast.parse((ROOT / 'test_readiness_rules_seam.py').read_text())
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    assert not any(isinstance(n, ast.Assign) and any(
        isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name)
        and target.value.id == 'state' and target.attr == 'id' for target in n.targets)
        for n in ast.walk(function))
    assert any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
               and n.func.id == 'adopt_fixture_state' for n in ast.walk(function))


@pytest.mark.parametrize('seat', [1, 2])
def test_existing_multiword_archetype_birth_is_clean_and_cold_valid(seat):
    state = knowledge.position('Tokens', 'Dimir Control', seat)
    assert not any(c.isspace() for c in state.id)
    assert state.id == state.sideboard_facts['game_id']
    snapshot = serialize_match_snapshot(state)
    assert serialize_match_snapshot(deserialize_match_snapshot(snapshot)) == snapshot
