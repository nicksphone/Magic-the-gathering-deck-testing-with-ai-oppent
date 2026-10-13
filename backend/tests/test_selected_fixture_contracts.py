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


def test_publication_accepts_exact_declared_false_keyword_only():
    publish, calls = publication_function()
    state, deck = object(), [{'quantity': 60, 'card_name': 'Island'}]
    try:
        result = publish(state, deck, capture_original_stock=False)
    except TypeError:
        pytest.fail('Original publication keyword is not accepted')
    assert result is state and calls == [(state, deck)]


@pytest.mark.parametrize('value', (True, None, 0, 'False'))
def test_publication_rejects_any_other_capture_value(value):
    publish, calls = publication_function()
    try:
        publish(object(), [], capture_original_stock=value)
    except AssertionError:
        pass
    except TypeError:
        pytest.fail('Keyword missing; strictFalse predicate not reached')
    else:
        pytest.fail('Unsupported capture flag accepted')
    assert not calls
