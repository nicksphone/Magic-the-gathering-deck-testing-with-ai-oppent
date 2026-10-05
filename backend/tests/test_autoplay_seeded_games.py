"""Bounded natural-game legality smoke, not balance or expert-play evidence."""
import pytest

from ai.agent import AIAgent
from ai.deck_analysis import guess_archetype
from game_state.state import MatchFactory
from tests.test_api_input_contracts import game, persist
from training.environment import _deck


@pytest.mark.parametrize("names", [
    ("Burn", "Mono Red Aggro"),
    ("Tempo", "Dimir Control"),
])
@pytest.mark.parametrize("reverse", [False, True])
def test_seeded_strong_ai_game_accepts_complete_actions(game, names, reverse):
    client, match = game
    decks = [_deck(name) for name in (names[::-1] if reverse else names)]
    state = MatchFactory.from_decks(*decks, seed=6105 + int(reverse))
    state.id = match.state.id
    match.state = state
    match.controllers = {1: "ai", 2: "ai"}
    match.mode = "ai_vs_ai"
    match.mainboards = {1: decks[0], 2: decks[1]}
    match.ai = {pid: AIAgent(difficulty="strong", archetype=guess_archetype(decks[pid - 1]),
                            opponent_archetype=guess_archetype(decks[2 - pid]))
                for pid in (1, 2)}
    persist(match)
    path = f"/matches/{state.id}/autoplay?ticks=20"
    for _ in range(60):
        response = client.post(path)
        assert response.status_code == 200, response.text
        if any(match.state.score.values()):
            break
    assert any(match.state.score.values()), "No completed game within 1200 accepted ticks"
