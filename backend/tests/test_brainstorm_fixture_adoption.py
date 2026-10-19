"""Genuine Factory/serde, inert repository transport; not HTTP qualification."""
import ast
from copy import deepcopy
from pathlib import Path
import pickle
import sys
from types import ModuleType, SimpleNamespace

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from tests.fixture_state_support import adopt_fixture_state
from tests import pending_source_privacy_support as causal
import test_brainstorm_desired as brain


SUBJECT = Path(__file__).with_name('test_brainstorm_http_ordering_goldens.py')


def position(family, seat):
    if family == 'ordinary':
        return brain.position(seat)
    return causal.setup(seat, 'sniper')[0]


def transport(monkeypatch):
    original = brain.position(1)
    controller = SimpleNamespace(state=original, mode='retained', revision=9)
    main = ModuleType('main')
    main.ACTIVE_MATCHES = {original.id: controller}
    calls = []

    def persist(repo, current):
        calls.append(('persist', serialize_match_snapshot(current.state)))

    main._persist_active_match = persist
    monkeypatch.setitem(sys.modules, 'main', main)
    repo = SimpleNamespace(delete_active_match=lambda identifier: calls.append(('delete', identifier)))
    namespace = {
        'persist': lambda current: persist(repo, current),
        # Real shared helper, with an explicit inert repository instead of a Session.
        'adopt_fixture_state': lambda current, state: adopt_fixture_state(current, state, repo),
    }
    node = next(n for n in ast.parse(SUBJECT.read_text()).body
                if isinstance(n, ast.FunctionDef) and n.name == 'install_position')
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(SUBJECT), 'exec'), namespace)
    return main, controller, calls, namespace['install_position']


@pytest.mark.parametrize('family', ['ordinary', 'channel'])
@pytest.mark.parametrize('seat', [1, 2])
def test_original_producers_keep_real_capture_through_installer(monkeypatch, family, seat):
    main, controller, calls, install = transport(monkeypatch)
    state = position(family, seat)
    assert state.id == state.sideboard_facts['game_id']
    packet = serialize_match_snapshot(state)
    before = pickle.dumps(state, 5)
    old_id = controller.state.id
    try:
        result = install(controller, state)
    except ValueError as error:
        pytest.fail(f'original installer corrupts genuine Factory capture: {error}')
    assert result == packet['id'] == state.id
    assert pickle.dumps(state, 5) == before
    assert controller.state is state and controller.mode == 'retained' and controller.revision == 9
    assert main.ACTIVE_MATCHES == {state.id: controller}
    assert calls == [('persist', packet), ('delete', old_id)]
    assert serialize_match_snapshot(deserialize_match_snapshot(deepcopy(packet))) == packet


@pytest.mark.parametrize('family', ['ordinary', 'channel'])
def test_forged_capture_rejects_before_binding_or_persistence(monkeypatch, family):
    main, controller, calls, install = transport(monkeypatch)
    state = position(family, 1)
    state.sideboard_facts['game_id'] = 'forged-capture'
    before = pickle.dumps(state, 5)
    old_state, registry = controller.state, dict(main.ACTIVE_MATCHES)
    with pytest.raises(ValueError, match='Invalid private sideboard facts'):
        install(controller, state)
    assert controller.state is old_state and main.ACTIVE_MATCHES == registry
    assert calls == [] and pickle.dumps(state, 5) == before


@pytest.mark.parametrize('family', ['ordinary', 'channel'])
def test_foreign_target_controller_is_not_overwritten(monkeypatch, family):
    main, controller, calls, install = transport(monkeypatch)
    state = position(family, 2)
    foreign = SimpleNamespace(state=state)
    main.ACTIVE_MATCHES[state.id] = foreign
    old_state, registry = controller.state, dict(main.ACTIVE_MATCHES)
    before = pickle.dumps(state, 5)
    with pytest.raises(ValueError, match='Fixture identity already registered'):
        install(controller, state)
    assert main.ACTIVE_MATCHES == registry and main.ACTIVE_MATCHES[state.id] is foreign
    assert controller.state is old_state and calls == []
    assert pickle.dumps(state, 5) == before


@pytest.mark.parametrize('family', ['ordinary', 'channel'])
def test_adoption_preserves_unrelated_binding_and_real_canonical_cards(monkeypatch, family):
    main, controller, calls, install = transport(monkeypatch)
    state = position(family, 1)
    other = brain.position(2)
    other_controller = SimpleNamespace(state=other)
    main.ACTIVE_MATCHES[other.id] = other_controller
    other_packet = serialize_match_snapshot(other)
    stock, capture = deepcopy(state.starting_decks), deepcopy(state.sideboard_facts)
    rng = state.rng.getstate()
    printed = {cid: (card.oracle_text, card.mana_cost, deepcopy(card.card_faces),
                     deepcopy(card.printed_characteristics), card.zone, card.zone_change_sequence)
               for cid, card in state.cards.items()}
    install(controller, state)
    assert main.ACTIVE_MATCHES[other.id] is other_controller
    assert serialize_match_snapshot(other) == other_packet
    assert state.starting_decks == stock and state.sideboard_facts == capture
    assert state.rng.getstate() == rng
    assert printed == {cid: (card.oracle_text, card.mana_cost, card.card_faces,
                            card.printed_characteristics, card.zone, card.zone_change_sequence)
                       for cid, card in state.cards.items()}
    assert len(calls) == 2
