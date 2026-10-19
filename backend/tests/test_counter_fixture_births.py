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
    from tests.cycling_timing_canonical_022758 import rats_state
    namespace = {'MatchFactory': MatchFactory, 'Step': Step, 'Zone': Zone,
                 'controlled_basic_game': controlled_basic_game, 'rats_state': rats_state}
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
    if kind == 'rats':
        from collections import Counter
        from tests.cycling_timing_canonical_022758 import raw_card
        raw = raw_card('Crypt Rats')
        assert raw['keywords'] == []
        header = raw['type_line'].replace('\u2014', '-').split(' - ', 1)[0].split()
        expected = dict(name=raw['name'], mana_cost=raw['mana_cost'],
                        type_line=raw['type_line'], oracle_text=raw['oracle_text'],
                        types=[word for word in header if word in {
                            'Artifact', 'Battle', 'Creature', 'Enchantment', 'Instant',
                            'Kindred', 'Land', 'Planeswalker', 'Sorcery', 'Tribal'}],
                        keywords=[], colors=raw['colors'],
                        power=int(raw['power']), toughness=int(raw['toughness']),
                        printed_power=raw['power'], printed_toughness=raw['toughness'],
                        loyalty=None)
        assert raw.get('loyalty') is None
        card = state.cards[source]
        assert source == 'p1-053' and card.owner == card.controller == 1
        assert card.zone == Zone.BATTLEFIELD and card.selected_face_index is None
        assert {key: getattr(card, key) for key in expected} == expected
        assert card.card_faces == raw.get('card_faces', []) and card.layout == raw['layout']
        record = card.characteristic_record
        assert set(record) == {'version', 'physical', 'values'} and record['version'] == 1
        assert record['values'] == expected
        assert card.image_uri in raw['image_uris'].values()
        assert record['physical'] == {
            **expected, 'card_faces': raw.get('card_faces', []), 'layout': raw['layout'],
            'selected_face_index': None, 'image_uri': card.image_uri}
        inventory = state.sideboard_facts['inventory']
        assert set(inventory) == set(state.cards) and len(inventory) == 120
        assert inventory[source] == {'owner': 1, 'stock_key': 'Crypt Rats'}
        assert Counter(row['owner'] for row in inventory.values()) == {1: 60, 2: 60}
        assert Counter(row['stock_key'] for row in inventory.values()) == {'Island': 119, 'Crypt Rats': 1}
        assert all(row['owner'] == state.cards[cid].owner for cid, row in inventory.items())
        assert Counter({seat: sum(row['quantity'] for row in deck)
                        for seat, deck in state.starting_decks.items()}) == {1: 60, 2: 60}
        rats_entries = [row for row in state.starting_decks[1] if row['card_name'] == 'Crypt Rats']
        assert len(rats_entries) == 1 and rats_entries[0]['quantity'] == 1
        assert all(rats_entries[0][key] == raw[key]
                   for key in ('name', 'oracle_text', 'type_line', 'mana_cost', 'id', 'oracle_id'))
        snapshot = serialize_match_snapshot(state)
        restored = deserialize_match_snapshot(snapshot)
        assert serialize_match_snapshot(restored) == snapshot
        assert restored.sideboard_facts == state.sideboard_facts
        assert restored.starting_decks == state.starting_decks
        assert restored.cards[source].characteristic_record == record
        assert {key: getattr(restored.cards[source], key) for key in expected} == expected
        return
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
