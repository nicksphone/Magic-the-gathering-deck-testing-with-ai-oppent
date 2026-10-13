"""Pure actual-state checks; test helpers projected without importing HTTP modules."""
import ast
from pathlib import Path

import pytest

from game_state.state import MatchFactory, Step, Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot


def function(path, name, namespace):
    node = next(n for n in ast.parse(path.read_text()).body
                if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace[name]


def helpers():
    here = Path(__file__).parent
    from tests.controlled_basic_game_support import controlled_basic_game
    namespace = {'MatchFactory': MatchFactory, 'Step': Step, 'Zone': Zone,
                 'controlled_basic_game': controlled_basic_game}
    function(here/'test_ai_recurring_engines.py', 'fixture', namespace)
    function(here/'test_combat_payments_requirements.py', 'zero_mana', namespace)
    function(here/'test_activation_modifiers.py', 'board', namespace)
    function(here/'test_activated_ability_timing.py', '_state', namespace)
    function(here/'test_activated_ability_timing.py', '_crypt_rats', namespace)
    return namespace


@pytest.mark.parametrize('seat', [1, 2])
def test_http_board_identity_is_fixed_at_factory_birth(seat):
    state = helpers()['board'](seat, game_id=f'actual-controller-{seat}')
    assert state.id == state.sideboard_facts['game_id'] == f'actual-controller-{seat}'
    assert state.active_player == state.priority_player == seat
    assert serialize_match_snapshot(state)['sideboard_facts']['game_id'] == state.id


@pytest.mark.parametrize('kind', ['artifact', 'rats'])
def test_repurposed_primitive_is_uncaptured_from_birth_and_cold_compatible(kind):
    ns = helpers()
    state, source = (ns['_state']('{T}: Draw a card.') if kind == 'artifact' else ns['_crypt_rats']())
    assert state.sideboard_facts == {}
    snapshot = serialize_match_snapshot(state)
    restored = deserialize_match_snapshot(snapshot)
    assert restored.sideboard_facts == {}
    assert serialize_match_snapshot(restored) == snapshot
    assert restored.cards[source].oracle_text == state.cards[source].oracle_text


def test_genuine_factory_printed_stock_mutation_still_rejected():
    deck = [{'quantity': 60, 'card_name': 'Island'}]
    state = MatchFactory.from_decks(deck, deck, seed=7)
    state.cards[next(iter(state.cards))].name = 'Crypt Rats'
    with pytest.raises(ValueError, match='physical printed source'):
        serialize_match_snapshot(state)


def test_invalid_requested_factory_identity_still_rejected():
    with pytest.raises(ValueError, match='game_id'):
        helpers()['board'](1, game_id='invalid identity')
