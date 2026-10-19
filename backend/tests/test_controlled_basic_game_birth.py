"""Finite uncaptured synthetic births; genuine Factory contracts remain strict."""
import copy
import importlib
import importlib.util
import json
import random
import uuid
from unittest.mock import patch

import pytest

from game_state.state import MatchFactory
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot

TEMPLATES = [
    {'quantity': 60, 'card_name': name} for name in ('Forest', 'Island', 'Swamp', 'Mountain')
] + [
    {'quantity': 60, 'card_name': 'Forest', 'type_line': 'Basic Land - Forest', 'oracle_text': '{T}: Add {G}.'},
    {'quantity': 60, 'card_name': 'Island', 'type_line': 'Basic Land - Island'},
]


def helper():
    name = 'tests.controlled_basic_game_support'
    assert importlib.util.find_spec(name) is not None, 'Missing uncaptured basic-game API'
    return importlib.import_module(name).controlled_basic_game


def wire(state):
    return json.loads(json.dumps(serialize_match_snapshot(state)))


@pytest.mark.parametrize('row', TEMPLATES)
@pytest.mark.parametrize('seed', [None, 17])
def test_all_non_capture_fields_match_real_factory(row, seed):
    build = helper()
    decks = ([copy.deepcopy(row)], [copy.deepcopy(TEMPLATES[1])])
    original = copy.deepcopy(decks)
    saved_global = random.getstate()
    actual_random = random.Random
    fixed = uuid.UUID('00000000-0000-4000-8000-000000000123')
    try:
        with patch('game_state.state.uuid.uuid4', return_value=fixed), patch(
            'random.Random', side_effect=lambda value=None: actual_random(913 if value is None else value)
        ):
            expected = MatchFactory.from_decks(*decks, seed=seed)
            random.setstate(saved_global)
            actual = build(*decks, seed=seed)
        a, b = wire(actual), wire(expected)
        assert a['sideboard_facts'] == {}
        assert b['sideboard_facts']['capture_version'] == 3
        del a['sideboard_facts'], b['sideboard_facts']
        assert a == b
        assert decks == original
        for pid in (1, 2):
            assert len(actual.players[pid].hand) == 7
            assert len(actual.players[pid].library) == 53
            assert set(cid for cid, card in actual.cards.items() if card.owner == pid) == {
                f'p{pid}-{index:03d}' for index in range(1, 61)}
            assert all(actual.cards[cid].zone_change_sequence == 1 for cid in actual.players[pid].hand)
        assert wire(deserialize_match_snapshot(wire(actual))) == wire(actual)
    finally:
        random.setstate(saved_global)


def test_never_calls_factory_or_initializes_or_erases_capture():
    build = helper()
    import game_state.state as states
    original = states.MatchState
    births = []
    def observe(*args, **kwargs):
        state = original(*args, **kwargs)
        births.append(state)
        assert state.sideboard_facts == {}
        return state
    with patch.object(states.MatchFactory, 'from_decks', side_effect=AssertionError('Factory birth forbidden')), \
         patch('ai.sideboard_facts.initialize', side_effect=AssertionError('Capture forbidden')), \
         patch.object(states, 'MatchState', side_effect=observe):
        state = build([TEMPLATES[0]], [TEMPLATES[1]], seed=7)
    assert births == [state]
    assert state.sideboard_facts == {}
    assert len(state.cards) == 120


INVALID_DECKS = [
    [], [{'quantity': 59, 'card_name': 'Forest'}], [{'quantity': True, 'card_name': 'Forest'}],
    [{'quantity': 60, 'card_name': 'Lightning Bolt'}], [{'quantity': 60, 'card_name': 'Forest', 'oracle_text': 'Draw seven cards.'}],
    [{'quantity': 60, 'card_name': 'Forest', 'type_line': 'Creature'}],
    [{'quantity': 60, 'card_name': 'Forest', 'card_faces': []}],
    [{'quantity': 60, 'card_name': 'Forest', 'knowledge_snapshot': {}}],
    [{'quantity': 30, 'card_name': 'Forest'}, {'quantity': 30, 'card_name': 'Forest'}],
    ({'quantity': 60, 'card_name': 'Forest'},),
]


@pytest.mark.parametrize('bad', INVALID_DECKS)
def test_unknown_templates_reject_before_birth(bad):
    build = helper()
    with patch('game_state.state.MatchState', side_effect=AssertionError('Birth before admission')), \
         patch('game_state.state.PlayerState', side_effect=AssertionError('Allocation before admission')):
        with pytest.raises(ValueError):
            build(bad, [TEMPLATES[0]], seed=7)


def test_independent_payloads_uuid_and_old_player_names():
    build = helper()
    row = copy.deepcopy(TEMPLATES[0])
    a = build([row], [row], 'Left', 'Right', seed=11)
    b = build([row], [row], 'Left', 'Right', seed=11)
    assert a.id != b.id
    assert uuid.UUID(a.id).version == uuid.UUID(b.id).version == 4
    assert [a.players[pid].name for pid in (1, 2)] == ['Left', 'Right']
    a.starting_decks[1][0]['card_name'] = 'Island'
    assert row['card_name'] == a.starting_decks[2][0]['card_name'] == b.starting_decks[1][0]['card_name'] == 'Forest'
    a.cards['p1-001'].keywords.append('haste')
    assert b.cards['p1-001'].keywords == []


@pytest.mark.parametrize('seat', [1, 2])
def test_uncaptured_repurpose_and_genuine_factory_stock_guards(seat):
    build = helper()
    deck = [TEMPLATES[1]]
    diagnostic = build(deck, deck, seed=31)
    real = MatchFactory.from_decks(deck, deck, seed=31)
    assert wire(real)['sideboard_facts']['capture_version'] == 3
    cid = diagnostic.players[seat].hand[0]
    diagnostic.cards[cid].name = 'Lightning Bolt'
    assert wire(deserialize_match_snapshot(wire(diagnostic))) == wire(diagnostic)
    real.cards[real.players[seat].hand[0]].name = 'Lightning Bolt'
    with pytest.raises(ValueError, match='physical printed source'):
        serialize_match_snapshot(real)
    real = MatchFactory.from_decks(deck, deck, seed=31)
    real.cards[real.players[seat].hand[0]].card_faces = [{'name': 'Lightning Bolt'}]
    with pytest.raises(ValueError, match='physical printed source'):
        serialize_match_snapshot(real)
    real = MatchFactory.from_decks(deck, deck, seed=31)
    real.sideboard_facts['game_id'] = 'foreign-capture'
    with pytest.raises(ValueError, match='Invalid private sideboard facts'):
        serialize_match_snapshot(real)
