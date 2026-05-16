from __future__ import annotations

from ai.agent import AIAgent
from game_state.state import MatchFactory
from main import ACTIVE_MATCHES, MatchController, get_match_replay
from rules_engine.engine import RulesEngine


def test_match_factory_seed_reproducible_openers() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    a = MatchFactory.from_decks(deck, deck, seed=123)
    b = MatchFactory.from_decks(deck, deck, seed=123)
    assert [a.cards[cid].name for cid in a.players[1].hand] == [b.cards[cid].name for cid in b.players[1].hand]
    assert [a.cards[cid].name for cid in a.players[2].hand] == [b.cards[cid].name for cid in b.players[2].hand]


def test_replay_endpoint_returns_entries() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=7)
    state.log.extend(["Turn 1.", "Player A plays Island.", "Turn 2.", "Player B plays Island."])
    ctrl = MatchController(
        state=state,
        rules=RulesEngine(),
        controllers={1: "ai", 2: "ai"},
        ai={1: AIAgent(difficulty="master"), 2: AIAgent(difficulty="master")},
        mode="ai_vs_ai",
        deck_ids=(None, None),
        mainboards={1: deck, 2: deck},
        sideboards={1: [], 2: []},
        game_number=1,
        current_game_recorded=False,
        match_complete=False,
        best_of=3,
    )
    ACTIVE_MATCHES[state.id] = ctrl
    body = get_match_replay(state.id)
    assert body["match_id"] == state.id
    assert isinstance(body["entries"], list)
    assert len(body["entries"]) >= 4
