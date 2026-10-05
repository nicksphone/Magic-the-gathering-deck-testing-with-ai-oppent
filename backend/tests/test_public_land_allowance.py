from unittest.mock import patch

import pytest

from game_state.serializers import serialize_match, serialize_match_snapshot, deserialize_match_snapshot
from game_state.state import MatchFactory, Step
from rules_engine.engine import RulesEngine


@pytest.mark.parametrize('seat', [1, 2])
def test_public_allowance_matches_legal_drop_and_restored_turn_records(seat):
    deck = [{'quantity': 60, 'card_name': 'Island'}]
    state = MatchFactory.from_decks(deck, deck, seed=19)
    state.pregame_pending = False
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    rules = RulesEngine()
    assert serialize_match(state)['players'][seat]['land_plays_remaining'] == 1
    land = next(move for move in rules.legal_moves(state, seat) if move['type'] == 'play_land')
    rules.take_action(state, seat, land)
    assert serialize_match(state)['players'][seat]['land_plays_remaining'] == 0
    assert not any(move['type'] == 'play_land' for move in rules.legal_moves(state, seat))
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert serialize_match(state)['players'][seat]['land_plays_remaining'] == 0
    with patch('rules_engine.land_rules.compute_max_land_plays_this_turn', return_value=3):
        assert serialize_match(state)['players'][seat]['land_plays_remaining'] == 2
    state.players[seat].land_plays_recorded_on_turn = 2
    assert serialize_match(state)['players'][seat]['land_plays_remaining'] == 0
    state.turn += 1
    before = serialize_match_snapshot(state)
    assert serialize_match(state)['players'][seat]['land_plays_remaining'] == 1
    assert serialize_match_snapshot(state) == before
