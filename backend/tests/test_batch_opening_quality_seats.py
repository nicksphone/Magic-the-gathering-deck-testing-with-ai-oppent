"""Batch attribution uses deck identity, not the alternating physical seat."""
import pytest

from analytics.service import AnalyticsService
from tests.pure_snapshot_support import PureSnapshotRepository, pure_snapshot_storage


class SnapshotRepo(PureSnapshotRepository):
    def record_snapshot(self, label, result):
        self.saved = (label, result)


@pytest.mark.parametrize('matches', [2, 3, 4])
def test_opening_quality_stays_with_deck_when_seats_alternate(monkeypatch, matches):
    repo = SnapshotRepo()
    service = AnalyticsService(repo)
    queried = []

    def score(state, player_id):
        # Controlled score markers isolate report attribution, not AI quality.
        name = state.players[player_id].name
        queried.append(name)
        return {'Deck A': 1.25, 'Deck B': 8.75}[name]

    monkeypatch.setattr(service, '_opening_hand_quality', score)
    deck = [{'quantity': 60, 'card_name': 'Island'}]
    result = service.run_batch(deck, deck, matches=matches, max_ticks=1)
    assert result['mulligan_stats'] == {
        'deck_a_avg_opening_hand_quality': 1.25,
        'deck_b_avg_opening_hand_quality': 8.75,
    }
    assert queried == ['Deck A', 'Deck B'] * matches
    assert [game['deck_a_on_play'] for game in result['game_results']] == [
        i % 2 == 0 for i in range(matches)
    ]
    assert result['resolved_games'] == 0 and result['timeouts'] == matches
    assert repo.saved == ('batch_simulation', result)
