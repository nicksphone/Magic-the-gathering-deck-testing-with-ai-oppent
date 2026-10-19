"""Actual fixture-branch fragments and real rules, not HTTP/browser acceptance."""
import ast
from copy import deepcopy
from pathlib import Path

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.counter_family_canonical091 import raw_card


NAME = 'The Phasing of Zhalfir'
SUBJECT = Path(__file__).with_name('browser_fixture_server.py')


def captured_branch():
    tree = ast.parse(SUBJECT.read_text())
    original = next(node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == 'fixture')
    branch = next(node for node in original.body
                  if isinstance(node, ast.If)
                  and ast.dump(node.test) == ast.dump(ast.parse(
                      "face_kind == 'read_ahead_entry'", mode='eval').body))
    fragment = deepcopy(original)
    fragment.decorator_list = []
    fragment.body = [deepcopy(branch)]
    captured = []

    def publish(state, deck):
        captured.append((state, deck))
        return state

    namespace = {'publish': publish}
    exec(compile(ast.Module(body=[fragment], type_ignores=[]), str(SUBJECT), 'exec'), namespace)
    state = namespace['fixture'](face_kind='read_ahead_entry')
    assert len(captured) == 1
    assert captured[0][0] is state
    assert captured[0][1] == [{'quantity': 60, 'card_name': 'Island'}]
    return state


def test_actual_branch_reaches_publisher_with_complete_canonical_pending_saga():
    raw = raw_card(NAME)
    assert raw['object'] == 'card'
    assert 'power' not in raw and 'toughness' not in raw
    state = captured_branch()
    cards = [card for card in state.cards.values() if card.name == NAME]
    assert len(cards) == 1
    card = cards[0]
    assert card.owner == card.controller == 2
    assert card.zone == Zone.STACK
    assert card.id not in state.players[2].battlefield
    assert state.pending_mechanic_choice['kind'] == 'saga_entry'
    assert state.pending_mechanic_choice['player_id'] == 2
    assert card.oracle_text == raw['oracle_text']
    assert card.type_line == raw['type_line']
    assert card.mana_cost == raw['mana_cost']
    assert card.power is None and card.toughness is None
    assert card.card_faces == raw.get('card_faces', [])
    snapshot = serialize_match_snapshot(state)
    saved = snapshot['cards'][card.id]
    for field in ('name', 'oracle_text', 'type_line', 'mana_cost'):
        assert saved[field] == raw[field]
    assert saved['card_faces'] == raw.get('card_faces', [])
    assert saved['power'] is None and saved['toughness'] is None
    assert serialize_match_snapshot(deserialize_match_snapshot(snapshot)) == snapshot


@pytest.mark.parametrize('restart', [False, True])
def test_actual_branch_chapter_two_checked_choice_commits_once_with_or_without_restart(restart):
    state = captured_branch()
    card = next(card for card in state.cards.values() if card.name == NAME)
    card_id = card.id
    before = serialize_match_snapshot(state)
    if restart:
        state = deserialize_match_snapshot(before)
    final = checked_action(state, RulesEngine(), 2,
                           {'type': 'choose_mechanic', 'choice_id': '2'})
    assert serialize_match_snapshot(state) == before
    assert final.pending_mechanic_choice is None
    assert final.cards[card_id].zone == Zone.BATTLEFIELD
    assert final.players[2].battlefield.count(card_id) == 1
    assert final.cards[card_id].counters['__lore'] == 2
    assert final.cards[card_id].oracle_text == raw_card(NAME)['oracle_text']
    assert sorted(item.payload['__chapter_number'] for item in final.stack) == [2]
    snapshot = serialize_match_snapshot(final)
    assert serialize_match_snapshot(deserialize_match_snapshot(snapshot)) == snapshot
