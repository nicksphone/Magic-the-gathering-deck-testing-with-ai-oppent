"""Real Factory birth/capture consistency; no post-birth facts repair."""
from copy import deepcopy
import json
from uuid import UUID

import pytest

from ai.sideboard_facts import copy_facts
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory
from training.environment import TrainingEnvironment, _deck


class StringSubclass(str):
    pass


@pytest.mark.parametrize('decks', [
    ('Mono Red Aggro', 'Blue Control'), ('Blue Control', 'Mono Red Aggro'),
])
def test_reset_final_identity_exists_at_real_factory_capture(monkeypatch, decks):
    original = MatchFactory.from_decks
    births = []

    def observe(*args, **kwargs):
        state = original(*args, **kwargs)
        births.append((state, state.id, deepcopy(state.sideboard_facts)))
        return state

    monkeypatch.setattr(MatchFactory, 'from_decks', staticmethod(observe))
    environment = TrainingEnvironment()
    environment.reset(*decks, seed=17)
    assert len(births) == 1
    state, birth_id, capture = births[0]
    assert state is environment._state
    assert capture['game_id'] == birth_id
    assert capture['inventory'] and capture['capture_version'] == 3
    assert state.sideboard_facts == capture
    assert state.id == birth_id, 'Reset changed identity after genuine Factory capture'


@pytest.mark.parametrize('decks', [
    ('Mono Red Aggro', 'Blue Control'), ('Blue Control', 'Mono Red Aggro'),
])
def test_reset_snapshot_retains_bound_capture_and_round_trips(decks):
    environment = TrainingEnvironment()
    environment.reset(*decks, seed=17)
    snapshot = environment.snapshot()
    assert snapshot['state']['sideboard_facts']['game_id'] == environment._state.id
    assert snapshot['state']['sideboard_facts']['inventory']
    restored = deserialize_match_snapshot(snapshot['state'])
    assert json.loads(json.dumps(serialize_match_snapshot(restored))) == snapshot['state']


def test_default_factory_uuid_and_foreign_or_invalid_identity_stay_protected():
    rows = [_deck('Mono Red Aggro'), _deck('Blue Control')]
    state = MatchFactory.from_decks(*rows, seed=17)
    foreign = MatchFactory.from_decks(*rows, seed=17)
    assert str(UUID(state.id)) == state.id
    assert state.id != foreign.id
    before = json.dumps(serialize_match_snapshot(state), sort_keys=True)
    assert copy_facts(state.sideboard_facts, state) == state.sideboard_facts
    with pytest.raises(ValueError, match='Invalid private sideboard facts'):
        copy_facts(foreign.sideboard_facts, state)
    for invalid in (None, True, 1, '', ' invalid '):
        candidate = deepcopy(state)
        candidate.id = invalid
        with pytest.raises(ValueError, match='Invalid private sideboard facts'):
            copy_facts(candidate.sideboard_facts, candidate)
    assert json.dumps(serialize_match_snapshot(state), sort_keys=True) == before


def test_same_seed_determinism_includes_real_nonempty_capture():
    first, second = TrainingEnvironment(), TrainingEnvironment()
    first.reset(seed=17)
    second.reset(seed=17)
    assert first._state.id == second._state.id
    assert first._state.sideboard_facts['inventory']
    assert second._state.sideboard_facts['inventory']
    assert first.snapshot() == second.snapshot()


@pytest.mark.parametrize('game_id', [
    False, True, 0, 17.0, '', ' ', ' padded', 'inside space',
    'line\nbreak', '\0', StringSubclass('not-plain'),
])
def test_invalid_game_id_rejects_before_allocation_or_capture(monkeypatch, game_id):
    from ai import sideboard_facts
    from game_state import state as state_module

    calls = []

    def forbidden(*args, **kwargs):
        calls.append('constructor-or-capture')
        raise AssertionError('Invalid ID reached allocation or capture')

    monkeypatch.setattr(state_module, 'CardInstance', forbidden)
    monkeypatch.setattr(state_module, 'MatchState', forbidden)
    monkeypatch.setattr(sideboard_facts, 'initialize', forbidden)
    with pytest.raises(ValueError, match='game_id'):
        MatchFactory.from_decks([], [], seed=17, game_id=game_id)
    assert calls == []


@pytest.mark.parametrize('game_id', [None, 'prepared-internal-id'])
def test_game_id_is_final_at_constructor_and_initialize(monkeypatch, game_id):
    from ai import sideboard_facts
    from game_state import state as state_module

    original_state, original_initialize = state_module.MatchState, sideboard_facts.initialize
    seen = []

    def construct(*args, **kwargs):
        seen.append(('constructor', kwargs['id']))
        return original_state(*args, **kwargs)

    def capture(state, inventory):
        seen.append(('initialize', state.id))
        return original_initialize(state, inventory)

    monkeypatch.setattr(state_module, 'MatchState', construct)
    monkeypatch.setattr(sideboard_facts, 'initialize', capture)
    state = MatchFactory.from_decks(_deck('Mono Red Aggro'), _deck('Blue Control'),
                                   seed=17, game_id=game_id)
    assert seen == [('constructor', state.id), ('initialize', state.id)]
    assert state.sideboard_facts['game_id'] == state.id
    assert state.sideboard_facts['inventory']
    if game_id is None:
        assert str(UUID(state.id)) == state.id
    else:
        assert state.id == game_id
