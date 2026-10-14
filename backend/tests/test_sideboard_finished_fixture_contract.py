"""Checked unit producer controls; no SQL, natural game, or strength certificate."""
from copy import deepcopy

from ai import sideboard_facts
from card_data.hydration import ready_for_match
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from main import _ai_sideboard_for_next_game, _start_next_game_state
from tests.sideboard_finished_fixture_support import fixture, return_artifact, complete

MAIN = [{'card_name': 'Swamp', 'quantity': 26}, {'card_name': 'Forest', 'quantity': 26},
        {'card_name': 'Fatal Push', 'quantity': 8}]
SIDE = [{'card_name': 'Abrupt Decay', 'quantity': 4}]


def test_real_terminal_factory_stock_readiness_and_three_card_privacy():
    match = fixture(MAIN, SIDE, seed=71, artifact=True)
    assert len(match.state.sideboard_facts['inventory']) == len(match.state.cards) == 120
    summary = sideboard_facts.summary_for(match.state, 1)
    assert summary['qualified'] and summary['held_counts']['Fatal Push'] >= 3
    assert 'Lightning Bolt' in summary['protected_stock']
    assert summary['observed_types'] == ['Artifact']
    assert all(row['match_ready'] == ready_for_match(row) for row in match.mainboards[1] + match.sideboards[1])
    _start_next_game_state(match)
    swaps = [line for line in match.state.log if ' sideboards ' in line]
    assert any('sideboards 3 card(s)' in line for line in swaps)
    assert all('Abrupt Decay' not in line and 'Fatal Push' not in line for line in swaps)
    assert sum(row['quantity'] for row in match.mainboards[1]) == 60


def test_unfinished_real_capture_declines_without_board_or_fact_mutation():
    match = fixture(MAIN, SIDE, seed=71, artifact=True, finish=False)
    before = deepcopy((match.mainboards, match.sideboards, match.state.sideboard_facts))
    assert sideboard_facts.seal_game(match.state) is False
    assert sideboard_facts.summary_for(match.state, 1) == {'qualified': False}
    _ai_sideboard_for_next_game(match, None)
    assert (match.mainboards, match.sideboards, match.state.sideboard_facts) == before


def test_unknown_old_wire_cannot_authorize_even_source_validated_offline_rows():
    match = fixture(MAIN, SIDE, seed=71, artifact=True)
    wire = serialize_match_snapshot(match.state)
    wire.pop('sideboard_facts')  # Deliberate legacy unknown input, never a positive fixture.
    match.state = deserialize_match_snapshot(wire)
    before = deepcopy((match.mainboards, match.sideboards))
    assert sideboard_facts.summary_for(match.state, 1) == {'qualified': False}
    _ai_sideboard_for_next_game(match, None)
    assert (match.mainboards, match.sideboards) == before


def test_real_artifact_return_retains_public_observation_and_source_identity():
    match = fixture(MAIN, SIDE, seed=74, artifact=True, remember=True, finish=False)
    original = deepcopy(match.state.sideboard_facts['inventory'])
    cid = return_artifact(match)
    complete(match)
    assert match.state.sideboard_facts['inventory'] == original
    assert cid in match.state.players[2].hand
    assert sideboard_facts.summary_for(match.state, 1)['observed_types'] == ['Artifact']
