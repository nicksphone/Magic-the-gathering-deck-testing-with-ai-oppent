"""Simulation failures cannot silently become passes or mutate rejected roots."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from analytics import service
from game_state.serializers import serialize_match_snapshot
from game_state.state import MatchFactory
from rules_engine.action_validation import ActionRejected
from scripts import regression_matrix_replay as replay


DECK = [{'card_name': 'Island', 'quantity': 60}]


class Repository:
    def __init__(self):
        self.saved = []

    def save_snapshot(self, *args):
        self.saved.append(args)


@pytest.mark.parametrize('entry', ['batch', 'round_robin', 'replay'])
@pytest.mark.parametrize('action', [
    {'type': 'not_an_action'},
    {'type': 'play_land'},
    {'type': 'play_land', 'card_id': 'missing'},
    {'type': 'cast_spell', 'card_id': 'missing', 'targets': {}},
    {'type': 'pass_priority'},
])
def test_rejected_decision_preserves_complete_factory_state_and_storage(monkeypatch, entry, action):
    captured = []
    factory = MatchFactory.from_decks

    def create(*args, **kwargs):
        state = factory(*args, **kwargs)
        # Replay writes setup before choosing; all values match those assignments.
        state.mechanic_choice_players = {1, 2}
        captured.append((state, deepcopy(serialize_match_snapshot(state))))
        return state

    class InvalidAgent:
        def __init__(self, **kwargs):
            pass

        def choose_action(self, *args):
            return SimpleNamespace(action=deepcopy(action), reasoning='deliberate invalid decision')

    monkeypatch.setattr(MatchFactory, 'from_decks', create)
    module = replay if entry == 'replay' else service
    monkeypatch.setattr(module, 'AIAgent', InvalidAgent)
    repo = Repository()
    with pytest.raises(ActionRejected):
        if entry == 'batch':
            service.AnalyticsService(repo).run_batch(DECK, DECK, matches=1, max_ticks=1)
        elif entry == 'round_robin':
            service.AnalyticsService(repo).run_ai_diagnostics([
                {'name': 'A', 'mainboard': DECK}, {'name': 'B', 'mainboard': DECK},
            ], matches_per_pair=1, max_ticks=1)
        else:
            replay.run_game(DECK, DECK, seed=71, difficulty='strong', max_ticks=1)
    assert len(captured) == 1
    state, before = captured[0]
    assert serialize_match_snapshot(state) == before
    assert repo.saved == []


@pytest.mark.parametrize('entry', ['batch', 'round_robin', 'replay'])
def test_real_heuristic_pregame_actions_are_accepted_without_display_hints(entry):
    repo = Repository()
    if entry == 'batch':
        result = service.AnalyticsService(repo).run_batch(DECK, DECK, matches=1, difficulty='strong', max_ticks=4)
        assert result['matches'] == 1
        assert len(repo.saved) == 1
    elif entry == 'round_robin':
        result = service.AnalyticsService(repo).run_ai_diagnostics([
            {'name': 'A', 'mainboard': DECK}, {'name': 'B', 'mainboard': DECK},
        ], matches_per_pair=1, difficulty='strong', max_ticks=4)
        assert result['games'] == 1
    else:
        first = replay.run_game(DECK, DECK, seed=71, difficulty='strong', max_ticks=4)
        second = replay.run_game(DECK, DECK, seed=71, difficulty='strong', max_ticks=4)
        assert first == second
        assert first['ticks'] == 4
