"""Actual Factory/serde with inert controller and publication projections; no SQL."""
import ast
from copy import deepcopy
from pathlib import Path
import pickle
from types import SimpleNamespace

import pytest

from game_state.serializers import serialize_match_snapshot
from game_state.state import MatchFactory


ROOT = Path(__file__).parent


def retain_function(calls):
    path = ROOT/'test_selected_mana_http.py'
    tree = ast.parse(path.read_text())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'retain')

    def persist(controller):
        snapshot = serialize_match_snapshot(controller.state)
        calls.append(snapshot)

    def adopt(controller, state):
        snapshot = serialize_match_snapshot(state)
        controller.state = state
        calls.append(snapshot)
        return controller

    namespace = {'deepcopy': deepcopy, 'persist': persist, 'adopt_fixture_state': adopt}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace['retain']


@pytest.mark.parametrize('seat', (1, 2))
def test_actual_factory_birth_identity_retained_not_transplanted(seat):
    deck = [{'quantity': 60, 'card_name': 'Swamp'}]
    state = MatchFactory.from_decks(deck, deck, seed=19, game_id='environment-'+str(seat))
    state.active_player = state.priority_player = seat
    controller = SimpleNamespace(state=MatchFactory.from_decks(deck, deck, seed=23), mode='unchanged')
    before = pickle.dumps(state, protocol=5)
    calls = []
    try:
        identifier = retain_function(calls)(controller, SimpleNamespace(_state=state))
    except ValueError as exc:
        pytest.fail('Postbirth transplantation rejected by genuine validator: '+type(exc).__name__)
    assert identifier == state.id == controller.state.id == state.sideboard_facts['game_id']
    assert controller.mode == 'unchanged' and controller.state is not state
    assert calls == [serialize_match_snapshot(state)]
    assert pickle.dumps(state, protocol=5) == before


@pytest.mark.parametrize('corruption', ('identity', 'printed_stock'))
def test_bad_factory_capture_is_never_repaired_or_published(corruption):
    deck = [{'quantity': 60, 'card_name': 'Swamp'}]
    state = MatchFactory.from_decks(deck, deck, seed=19, game_id='environment')
    controller = SimpleNamespace(state=MatchFactory.from_decks(deck, deck, seed=23))
    if corruption == 'identity':
        state.sideboard_facts['game_id'] = 'forged'
    else:
        next(iter(state.cards.values())).printed_characteristics['name'] = 'forged'
    old_controller = controller.state
    before = pickle.dumps(state, protocol=5)
    calls = []
    with pytest.raises(ValueError):
        retain_function(calls)(controller, SimpleNamespace(_state=state))
    assert not calls
    assert controller.state is old_controller
    assert pickle.dumps(state, protocol=5) == before


def publication_function():
    path = ROOT/'test_spell_type_caller_projection.py'
    tree = ast.parse(path.read_text())
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'publish')
    calls = []
    namespace = {'publications': calls}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace['publish'], calls


@pytest.mark.parametrize('mode', ('default', 'explicit-true', 'per-seat'))
def test_publication_accepts_exact_true_default_and_matching_mainboards(mode):
    """Mock publication protocol only, not a native game or stock certificate."""
    publish, calls = publication_function()
    deck = [{'quantity': 60, 'card_name': 'Island'}]
    boards = {1: deepcopy(deck), 2: [{'quantity': 60, 'card_name': 'Swamp'}]
              if mode == 'per-seat' else deepcopy(deck)}
    state = SimpleNamespace(starting_decks=deepcopy(boards))
    keywords = {} if mode == 'default' else {'capture_original_stock': True}
    if mode == 'per-seat':
        keywords['mainboards'] = boards
    before = pickle.dumps((state, deck, boards), protocol=5)
    result = publish(state, deck, **keywords)
    assert result is state and calls == [(state, deck, boards)]
    recorded_state, recorded_deck, recorded_boards = calls[0]
    assert recorded_state is state and recorded_deck is deck
    assert type(recorded_boards) is dict and set(recorded_boards) == {1, 2}
    assert all(type(seat) is int for seat in recorded_boards)
    assert recorded_boards == state.starting_decks and recorded_boards[1] == deck
    if mode == 'per-seat':
        assert recorded_boards is boards and recorded_boards[1] != recorded_boards[2]
    else:
        assert recorded_boards[1] is deck and recorded_boards[2] is deck
    assert pickle.dumps((state, deck, boards), protocol=5) == before


@pytest.mark.parametrize('value', (False, None, 0, 'False', 1),
                         ids=('false', 'none', 'zero', 'string-false', 'one'))
def test_publication_rejects_any_other_capture_value(value):
    """Otherwise-valid mock arguments isolate the exact-True boundary."""
    publish, calls = publication_function()
    deck = [{'quantity': 60, 'card_name': 'Island'}]
    state = SimpleNamespace(starting_decks={1: deepcopy(deck), 2: deepcopy(deck)})
    before = pickle.dumps((state, deck), protocol=5)
    with pytest.raises(AssertionError):
        publish(state, deck, capture_original_stock=value)
    assert not calls
    assert pickle.dumps((state, deck), protocol=5) == before


def test_publication_rejects_unknown_keyword_before_recording():
    """Python keyword binding stays strict; no fallback publication is accepted."""
    publish, calls = publication_function()
    deck = [{'quantity': 60, 'card_name': 'Island'}]
    state = SimpleNamespace(starting_decks={1: deepcopy(deck), 2: deepcopy(deck)})
    before = pickle.dumps((state, deck), protocol=5)
    with pytest.raises(TypeError, match='unexpected keyword argument'):
        publish(state, deck, capture_original_stock=True, unknown_publication_flag=True)
    assert not calls
    assert pickle.dumps((state, deck), protocol=5) == before


@pytest.mark.parametrize('fault', ('keys', 'record', 'seat-one-deck'))
def test_publication_rejects_mismatched_mainboards_without_mutation(fault):
    """Mock shape/record/deck contradictions are not native fixture states."""
    publish, calls = publication_function()
    deck = [{'quantity': 60, 'card_name': 'Island'}]
    boards = {1: deepcopy(deck), 2: [{'quantity': 60, 'card_name': 'Swamp'}]}
    state = SimpleNamespace(starting_decks=deepcopy(boards))
    if fault == 'keys':
        boards = {str(seat): rows for seat, rows in boards.items()}
    elif fault == 'record':
        boards[2] = [{'quantity': 60, 'card_name': 'Forest'}]
    else:
        deck = [{'quantity': 60, 'card_name': 'Plains'}]
    before = pickle.dumps((state, deck, boards), protocol=5)
    with pytest.raises(AssertionError):
        publish(state, deck, capture_original_stock=True, mainboards=boards)
    assert not calls
    assert pickle.dumps((state, deck, boards), protocol=5) == before
