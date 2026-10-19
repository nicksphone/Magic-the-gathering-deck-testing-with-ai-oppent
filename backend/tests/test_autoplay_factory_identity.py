"""Native Factory/serde proof of the original source birth stage, not HTTP gameplay."""
import ast
from pathlib import Path

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory
from training.environment import _deck


SUBJECT = Path(__file__).with_name('test_autoplay_seeded_games.py')


class BirthCaptured(Exception):
    pass


def birth_body():
    # Preserve the actual body without importing its HTTP fixture or invoking it.
    node = next(n for n in ast.parse(SUBJECT.read_text()).body
                if isinstance(n, ast.FunctionDef)
                and n.name == 'test_seeded_strong_ai_game_accepts_complete_actions')
    node.decorator_list = []
    namespace = {'MatchFactory': MatchFactory, '_deck': _deck}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(SUBJECT), 'exec'), namespace)
    return namespace[node.name]


class CaptureController:
    """Trusted controller-assignment seam; stop before AI creation/persistence/HTTP."""
    def __init__(self, state):
        self.original = state
        self.captured = None

    @property
    def state(self):
        return self.original

    @state.setter
    def state(self, value):
        assert value.id == self.original.id
        assert value.sideboard_facts['game_id'] == value.id
        snapshot = serialize_match_snapshot(value)
        assert serialize_match_snapshot(deserialize_match_snapshot(snapshot)) == snapshot
        assert len(value.sideboard_facts['inventory']) == len(value.cards)
        self.captured = value
        raise BirthCaptured


@pytest.mark.parametrize('names', [('Burn', 'Mono Red Aggro'), ('Tempo', 'Dimir Control')])
@pytest.mark.parametrize('reverse', [False, True])
def test_original_autoplay_birth_retains_genuine_controller_identity(names, reverse):
    decks = [_deck(name) for name in (names[::-1] if reverse else names)]
    controller = CaptureController(MatchFactory.from_decks(*decks, seed=812))
    before = serialize_match_snapshot(controller.original)
    with pytest.raises(BirthCaptured):
        birth_body()((None, controller), names, reverse)
    assert serialize_match_snapshot(controller.original) == before
    assert controller.captured.starting_decks == {1: decks[0], 2: decks[1]}


def test_postbirth_identity_corruption_still_rejects_private_snapshot():
    decks = [_deck('Burn'), _deck('Mono Red Aggro')]
    state = MatchFactory.from_decks(*decks, seed=6105)
    original_id = state.id
    state.id = MatchFactory.from_decks(*decks, seed=812).id
    assert state.id != original_id
    assert state.sideboard_facts['game_id'] == original_id
    with pytest.raises(ValueError, match='Invalid private sideboard facts'):
        serialize_match_snapshot(state)
