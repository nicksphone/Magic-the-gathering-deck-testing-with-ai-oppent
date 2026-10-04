"""Submitted composition is known; hidden current instances and order are not."""
from copy import deepcopy

import pytest

from ai.agent import AIAgent
from ai.information import decision_view, known_search_land_count
from game_state.serializers import serialize_match, serialize_match_snapshot, deserialize_match_snapshot
from game_state.state import MatchFactory, Zone
from rules_engine.engine import RulesEngine
from tests.test_linked_discard import setup


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('level', ['casual', 'strong', 'master'])
def test_linked_search_uses_own_list_not_hidden_instances(seat, level):
    state, _, hand = setup('Rites of Spring', seat)
    engine = RulesEngine()
    agent = AIAgent(level)
    action = agent.choose_action(state, engine.legal_moves(state, seat), seat).action
    assert action['card_ids'] == [hand[-1].id]
    other = 3-seat
    state.starting_decks[other] = [{'card_name': 'Island', 'quantity': 60}]
    for player in state.players.values():
        player.library.reverse()
        for cid in player.library:
            state.cards[cid].name = 'Counterspell'
            state.cards[cid].types = ['Instant']
            state.cards[cid].type_line = 'Instant'
    assert agent.choose_action(state, engine.legal_moves(state, seat), seat).action == action
    state.starting_decks[seat] = [{'card_name': 'Counterspell', 'quantity': 60}]
    assert agent.choose_action(state, engine.legal_moves(state, seat), seat).action['card_ids'] == []


@pytest.mark.parametrize('seat', [1, 2])
def test_composition_persists_privately_and_does_not_alias_input(seat):
    deck = [{'card_name': 'Swamp', 'quantity': 60}]
    state = MatchFactory.from_decks(deck, deck, seed=32)
    expected = deepcopy(state.starting_decks)
    deck[0]['quantity'] = 1
    assert state.starting_decks == expected
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert restored.starting_decks == expected
    assert 'starting_decks' not in serialize_match(state)
    view, _ = decision_view(restored, seat, [])
    assert view.starting_decks == {seat: expected[seat]}
    view.starting_decks[seat][0]['quantity'] = 1
    assert restored.starting_decks == expected


def test_legacy_snapshot_does_not_recover_composition_from_hidden_cards():
    state, _, _ = setup('Rites of Spring')
    snapshot = serialize_match_snapshot(state)
    snapshot.pop('starting_decks')
    restored = deserialize_match_snapshot(snapshot)
    assert restored.starting_decks == {}
    assert known_search_land_count(restored, 1, 'basic_land') == 0


def test_known_search_count_subtracts_visible_copies_and_caps_by_library():
    state, _, _ = setup('Rites of Spring')
    state.starting_decks[1] = [{'card_name': 'Swamp', 'quantity': 1},
                              {'card_name': 'Swamp', 'quantity': 2}]
    assert known_search_land_count(state, 1, 'basic_land') == 2
    state.players[1].library = state.players[1].library[:1]
    assert known_search_land_count(state, 1, 'basic_land') == 1
    state.players[1].library = []
    assert known_search_land_count(state, 1, 'basic_land') == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_known_inventory_counts_owned_lands_under_opponent_control_and_excludes_copied_tokens(seat):
    deck = [{'card_name': 'Forest', 'quantity': 20}, {'card_name': 'Island', 'quantity': 40}]
    state = MatchFactory.from_decks(deck, deck, seed=32)
    forest = next(state.cards[cid] for cid in state.players[seat].hand if state.cards[cid].name == 'Forest')
    expected = known_search_land_count(state, seat, 'forest')
    state.players[seat].hand.remove(forest.id)
    state.players[3-seat].battlefield.append(forest.id)
    forest.move_to_zone(Zone.BATTLEFIELD)
    forest.controller = 3-seat
    assert known_search_land_count(state, seat, 'forest') == expected
    token = deepcopy(forest)
    token.id = 'copied-forest-token'
    token.is_token = True
    token.controller = seat
    state.cards[token.id] = token
    state.players[seat].battlefield.append(token.id)
    assert known_search_land_count(state, seat, 'forest') == expected
